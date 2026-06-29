import asyncio
import base64
import io
import json
import os
import sqlite3
from datetime import datetime, timezone

import httpx
import requests
from PIL import Image
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Donation Classifier API - Llava Optimized")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llava"  # Manteniendo estrictamente tu modelo actual
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "donaciones.db")

# Prompt compacto para clasificación de donaciones (Venezuela)
PROMPT = (
    "Clasifica la donación leyendo marcas/etiquetas o, si no hay texto, por su forma. "
    "Elige UNA categoría:\n"
    "- medicamentos: pastillas, jarabes, blisters, gasas, vendas, alcohol, agua oxigenada, jeringas. Marcas: Atamel, Ibuprofeno, Brugesic, Loratadina, Redoxon.\n"
    "- higiene: aseo personal. Shampoo, crema dental, jabón de baño, desodorante, papel higiénico, toallas sanitarias, pañales. Marcas: Pantene, Colgate, Protex, Dove, Pampers, Saba.\n"
    "- limpieza: aseo del hogar. Cloro, detergente, desinfectante, lavaplatos, suavizante, jabón de lavar/panela. Marcas: Nevex, Ariel, Ace, Mistolín, Axion, Las Llaves.\n"
    "- comida: enlatados (atún, sardina), arroz, pasta, harina, granos, aceite, azúcar, leche, jugos, gatorade, Pedialyte.\n"
    "- ropa: camisas, franelas, pantalones, blue jean, suéteres, medias, interiores, sábanas, cobijas, toallas de baño.\n"
    "- calzado: zapatos, tenis, botas, sandalias, cholas, zapatillas.\n"
    "- otros: lo que no encaje arriba.\n\n"
    "Reconocer ropa por forma: camisa=mangas+botones+cuello; franela=mangas sin botones; blue jean=denim azul con bolsillos; cobija/sábana=tela grande extendida sin mangas.\n"
    "Reglas: 'toalla de baño'=ropa, 'toalla sanitaria'=higiene, 'paño de cocina'=limpieza. "
    "Jabón de baño (Protex/Dove)=higiene; jabón de lavar/panela (Las Llaves/Ace)=limpieza. "
    "Suero de tomar (Pedialyte)=comida; suero endovenoso (Ringer)=medicamentos.\n\n"
    "Responde SOLO con JSON plano, sin markdown:\n"
    "{\n"
    '  "categoria": "medicamentos|ropa|calzado|comida|higiene|limpieza|otros",\n'
    '  "subcategoria": "nombre específico si se lee (ej: acetaminofén, shampoo, blue jean); si no, cadena vacía",\n'
    '  "descripcion_corta": "breve descripción en español",\n'
    '  "conteo_estimado": 1,\n'
    '  "prioridad": "Alta|Media|Baja"\n'
    "}\n"
    "Prioridad: comida/medicamentos/higiene/limpieza=Alta; ropa/calzado=Media; otros=Baja."
)


class DonacionCreate(BaseModel):
    categoria: str
    subcategoria: str = ""
    descripcion_corta: str
    conteo_estimado: int
    prioridad: str
    centro_acopio: str = "Centro principal"
    confirmado: bool = True


class DonacionUpdate(BaseModel):
    categoria: str | None = None
    subcategoria: str | None = None
    descripcion_corta: str | None = None
    conteo_estimado: int | None = None
    prioridad: str | None = None
    centro_acopio: str | None = None
    confirmado: bool | None = None


def _get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_connection():
    init_db()
    return _get_db_connection()


def init_db():
    conn = _get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS donaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            subcategoria TEXT NOT NULL DEFAULT '',
            descripcion_corta TEXT NOT NULL,
            conteo_estimado INTEGER NOT NULL,
            prioridad TEXT NOT NULL,
            centro_acopio TEXT NOT NULL,
            confirmado INTEGER NOT NULL DEFAULT 1,
            fecha_creacion TEXT NOT NULL
        )
        """
    )
    # Migrar tablas antiguas que no tengan subcategoria
    columnas = [row["name"] for row in conn.execute("PRAGMA table_info(donaciones)").fetchall()]
    if "subcategoria" not in columnas:
        conn.execute("ALTER TABLE donaciones ADD COLUMN subcategoria TEXT NOT NULL DEFAULT ''")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS subcategorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            nombre TEXT NOT NULL,
            UNIQUE(categoria, nombre)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS centros_acopio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            activo INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    # Sembrar centros iniciales si la tabla está vacía
    centros_existentes = conn.execute("SELECT COUNT(*) as total FROM centros_acopio").fetchone()["total"]
    if centros_existentes == 0:
        centros_iniciales = [
            "Centro principal",
            "Centro Norte",
            "Centro Sur",
            "Centro Este",
            "Centro Oeste",
            "Iglesia San José",
            "Escuela Bolívar",
            "Comedor comunitario",
        ]
        conn.executemany(
            "INSERT INTO centros_acopio (nombre) VALUES (?)",
            [(c,) for c in centros_iniciales],
        )
    conn.commit()
    conn.close()


def normalizar_subcategoria(categoria, nombre):
    """Devuelve el nombre canónico de una subcategoria si existe en el catálogo."""
    if not nombre or not str(nombre).strip():
        return ""
    nombre_limpio = str(nombre).strip().lower()
    conn = _get_db_connection()
    row = conn.execute(
        "SELECT nombre FROM subcategorias WHERE categoria = ? AND lower(nombre) = ?",
        (categoria, nombre_limpio),
    ).fetchone()
    conn.close()
    return row["nombre"] if row else ""


def row_to_dict(row):
    return {
        "id": row["id"],
        "categoria": row["categoria"],
        "subcategoria": row["subcategoria"],
        "descripcion_corta": row["descripcion_corta"],
        "conteo_estimado": row["conteo_estimado"],
        "prioridad": row["prioridad"],
        "centro_acopio": row["centro_acopio"],
        "confirmado": bool(row["confirmado"]),
        "fecha_creacion": row["fecha_creacion"],
    }


def normalizar_clasificacion(resultado):
    # Combinamos la categoría propuesta por Llava y su descripción para buscar palabras clave
    texto = f"{resultado.get('categoria', '')} {resultado.get('descripcion_corta', '')}".lower()

    # Mapeo flexible de palabras clave. Orden: lo más específico y con forma
    # reconocible va primero (calzado/ropa) para evitar que palabras ambiguas
    # como "toalla" o "higiene" de la descripción ganen sobre un zapato/chola.
    reglas = [
        ("calzado", ["zapato", "zapatos", "tenis", "bota", "botas", "sandalia", "sandalias", "chola", "cholas", "zapatilla", "zapatillas", "calzado"]),
        ("ropa", ["camisa", "camiseta", "pantalon", "pantalón", "abrigo", "sueter", "suéter", "cobija", "cobijas", "sabana", "sábana", "sabanas", "sábanas", "toalla de baño", "toalla de cocina", "toalla de mano", "textil", "textiles", "prenda", "prendas", "media", "medias"]),
        ("medicamentos", ["medicamento", "medicamentos", "pastilla", "pastillas", "cápsula", "capsula", "jarabe", "venda", "vendas", "gasa", "gasas", "botiquin", "botiquín", "farmacia", "medicina", "acetaminofen", "acetaminofén", "ibuprofeno", "antibiotico", "antibiótico", "antialergico", "antialérgico", "alcohol medicinal", "agua oxigenada", "solución fisiológica", "solucion fisiologica"]),
        ("higiene", ["colgate", "oral-b", "crema dental", "pasta dental", "dentifrico", "dentífrico", "cepillo dental", "cepillo de dientes", "jabon de baño", "jabón de baño", "jabon corporal", "jabón corporal", "shampoo", "champu", "champú", "acondicionador", "desodorante", "papel higienico", "papel higiénico", "pañal", "pañales", "toalla sanitaria", "toallas sanitarias", "tampon", "tampón", "higiene personal", "aseo personal"]),
        ("limpieza", ["cloro", "lejía", "lejia", "detergente", "desinfectante", "lavaplatos", "lava platos", "jabon de lavar", "jabón de lavar", "suavizante", "limpiador", "limpiador de piso", "limpieza del hogar", "aseo del hogar", "desengrasante", "multiuso", "multiusos", "ariel", "ace", "mistolin", "fabuloso"]),
        ("comida", ["comida", "alimento", "alimentos", "arroz", "pasta", "espagueti", "harina", "lata", "latas", "atun", "atún", "sardina", "sardinas", "enlatado", "enlatados", "conserva", "conservas", "agua embotellada", "botella de agua", "jugo", "jugos", "gatorade", "bebida hidratante", "suero oral", "suero bebible", "leche", "granos", "caraotas", "frijoles", "lentejas", "avena", "cereal", "galleta", "galletas", "aceite", "sal", "azucar", "azúcar"]),
    ]

    # Si encontramos una palabra clave en el texto, corregimos la categoría asignada
    for categoria, palabras in reglas:
        if any(palabra in texto for palabra in palabras):
            resultado["categoria"] = categoria
            break

    # Validación estricta contra las categorías permitidas
    categorias_validas = {"medicamentos", "ropa", "calzado", "comida", "higiene", "limpieza", "otros"}
    if resultado.get("categoria") not in categorias_validas:
        resultado["categoria"] = "otros"

    # Forzar la asignación lógica de prioridades incluyendo higiene en 'Media'
    if resultado["categoria"] in {"medicamentos", "comida", "higiene", "limpieza"}:
        resultado["prioridad"] = "Alta"
    elif resultado["categoria"] in {"ropa", "calzado"}:
        resultado["prioridad"] = "Media"
    else:
        resultado["prioridad"] = "Baja"

    return resultado


def optimizar_imagen(contenido, lado_max=768, calidad=70):
    """Redimensiona y comprime la imagen para acelerar la inferencia de visión."""
    try:
        img = Image.open(io.BytesIO(contenido))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((lado_max, lado_max), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=calidad, optimize=True)
        return buffer.getvalue()
    except Exception as e:
        print(f"[IMG] No se pudo optimizar la imagen: {e}. Se usa la original.")
        return contenido


@app.on_event("startup")
def on_startup():
    init_db()


@app.post("/clasificar")
async def clasificar(request: Request, imagen: UploadFile = File(...)):
    contenido = await imagen.read()
    if await request.is_disconnected():
        return JSONResponse(status_code=499, content={"error": "Cliente desconectado antes de procesar."})

    tam_original = len(contenido) // 1024
    contenido = optimizar_imagen(contenido)
    print(f"[IMG] Optimizada: {tam_original} KB -> {len(contenido) // 1024} KB")

    imagen_b64 = base64.b64encode(contenido).decode("utf-8")

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": PROMPT,
        "images": [imagen_b64],
        "format": "json",
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 120,
        },
    }

    print(f"[OLLAMA] Enviando imagen a {OLLAMA_MODEL}... ({len(imagen_b64) // 1024} KB)")

    async def llamar_ollama():
        async with httpx.AsyncClient(timeout=240.0) as client:
            return await client.post(OLLAMA_URL, json=payload)

    tarea = asyncio.create_task(llamar_ollama())
    while not tarea.done():
        if await request.is_disconnected():
            tarea.cancel()
            try:
                await tarea
            except asyncio.CancelledError:
                pass
            print("[OLLAMA] Petición cancelada: cliente desconectado.")
            return JSONResponse(status_code=499, content={"error": "Cliente desconectado. Petición cancelada."})
        await asyncio.sleep(0.5)

    try:
        respuesta = await tarea
    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={"error": "No se puede conectar con Ollama. Verifica que 'ollama serve' esté corriendo."},
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"error": "Ollama no respondió en 240 segundos. El modelo puede estar cargando o la PC saturada."},
        )
    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=502,
            content={"error": "Error HTTP en Ollama.", "detalle": str(e)},
        )

    datos_ollama = respuesta.json()
    texto_respuesta = datos_ollama.get("response", "{}")
    print(f"[OLLAMA] Respuesta recibida: {texto_respuesta[:100]}")

    try:
        resultado = json.loads(texto_respuesta)
    except json.JSONDecodeError:
        if "{" in texto_respuesta and "}" in texto_respuesta:
            try:
                inicio = texto_respuesta.find("{")
                fin = texto_respuesta.rfind("}") + 1
                resultado = json.loads(texto_respuesta[inicio:fin])
            except Exception:
                return JSONResponse(
                    status_code=422,
                    content={"error": "Llava no formateó un JSON limpio.", "cruda": texto_respuesta},
                )
        else:
            return JSONResponse(
                status_code=422,
                content={"error": "La respuesta no contiene estructura JSON.", "cruda": texto_respuesta},
            )

    for campo in ["categoria", "subcategoria", "descripcion_corta", "conteo_estimado", "prioridad"]:
        if campo not in resultado:
            if campo == "categoria":
                resultado[campo] = "otros"
            elif campo == "conteo_estimado":
                resultado[campo] = 1
            elif campo == "subcategoria":
                resultado[campo] = ""
            else:
                resultado[campo] = "Baja"

    resultado = normalizar_clasificacion(resultado)

    try:
        resultado["conteo_estimado"] = int(resultado.get("conteo_estimado", 1))
    except (TypeError, ValueError):
        resultado["conteo_estimado"] = 1

    return JSONResponse(content=resultado)


@app.post("/donaciones")
async def crear_donacion(donacion: DonacionCreate):
    fecha_creacion = datetime.now(timezone.utc).isoformat()
    subcategoria_canonica = normalizar_subcategoria(donacion.categoria, donacion.subcategoria)
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO donaciones (
            categoria, subcategoria, descripcion_corta, conteo_estimado, prioridad, centro_acopio, confirmado, fecha_creacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            donacion.categoria,
            subcategoria_canonica,
            donacion.descripcion_corta,
            donacion.conteo_estimado,
            donacion.prioridad,
            donacion.centro_acopio,
            int(donacion.confirmado),
            fecha_creacion,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM donaciones WHERE id = ?", (cursor.lastrowid,)).fetchone()
    conn.close()
    return row_to_dict(row)


@app.get("/donaciones")
async def listar_donaciones(centro_acopio: str | None = None):
    conn = get_db_connection()
    if centro_acopio:
        rows = conn.execute(
            "SELECT * FROM donaciones WHERE centro_acopio = ? ORDER BY id DESC",
            (centro_acopio,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM donaciones ORDER BY id DESC").fetchall()
    conn.close()
    return [row_to_dict(row) for row in rows]


@app.get("/donaciones/resumen")
async def resumen_donaciones(centro_acopio: str | None = None):
    conn = get_db_connection()
    if centro_acopio:
        rows = conn.execute(
            """
            SELECT categoria, SUM(conteo_estimado) AS total, COUNT(*) AS registros
            FROM donaciones
            WHERE centro_acopio = ?
            GROUP BY categoria
            ORDER BY categoria
            """,
            (centro_acopio,),
        ).fetchall()
        prioridad_alta = conn.execute(
            "SELECT COUNT(*) AS total FROM donaciones WHERE prioridad = 'Alta' AND centro_acopio = ?",
            (centro_acopio,),
        ).fetchone()
    else:
        rows = conn.execute(
            """
            SELECT categoria, SUM(conteo_estimado) AS total, COUNT(*) AS registros
            FROM donaciones
            GROUP BY categoria
            ORDER BY categoria
            """
        ).fetchall()
        prioridad_alta = conn.execute("SELECT COUNT(*) AS total FROM donaciones WHERE prioridad = 'Alta'").fetchone()
    conn.close()
    return {
        "totales_por_categoria": [dict(row) for row in rows],
        "registros_prioridad_alta": prioridad_alta["total"],
    }


@app.patch("/donaciones/{donacion_id}")
async def actualizar_donacion(donacion_id: int, cambios: DonacionUpdate):
    datos = cambios.model_dump(exclude_unset=True)
    if not datos:
        return JSONResponse(status_code=400, content={"error": "No se enviaron cambios."})

    columnas = []
    valores = []
    for key, value in datos.items():
        columnas.append(f"{key} = ?")
        valores.append(int(value) if key == "confirmado" else value)
    valores.append(donacion_id)

    conn = get_db_connection()
    conn.execute(f"UPDATE donaciones SET {', '.join(columnas)} WHERE id = ?", valores)
    conn.commit()
    row = conn.execute("SELECT * FROM donaciones WHERE id = ?", (donacion_id,)).fetchone()
    conn.close()

    if row is None:
        return JSONResponse(status_code=404, content={"error": "Donación no encontrada."})

    return row_to_dict(row)


@app.delete("/donaciones/{donacion_id}")
async def eliminar_donacion(donacion_id: int):
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM donaciones WHERE id = ?", (donacion_id,))
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return JSONResponse(status_code=404, content={"error": "Donación no encontrada."})

    return {"ok": True}


class SubcategoriaCreate(BaseModel):
    categoria: str
    nombre: str


class SubcategoriaUpdate(BaseModel):
    nombre: str


@app.get("/subcategorias")
async def listar_subcategorias(categoria: str | None = None):
    conn = get_db_connection()
    if categoria:
        rows = conn.execute(
            "SELECT * FROM subcategorias WHERE categoria = ? ORDER BY nombre",
            (categoria,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM subcategorias ORDER BY categoria, nombre").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/subcategorias")
async def crear_subcategoria(sub: SubcategoriaCreate):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO subcategorias (categoria, nombre) VALUES (?, ?)",
            (sub.categoria, sub.nombre.strip()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM subcategorias WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        conn.close()
        return JSONResponse(status_code=409, content={"error": "Ya existe esa subcategoría para esta categoría."})
    conn.close()
    return dict(row)


@app.put("/subcategorias/{subcategoria_id}")
async def actualizar_subcategoria(subcategoria_id: int, sub: SubcategoriaUpdate):
    nombre_nuevo = sub.nombre.strip()
    if not nombre_nuevo:
        return JSONResponse(status_code=400, content={"error": "El nombre no puede estar vacío."})

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM subcategorias WHERE id = ?", (subcategoria_id,)).fetchone()
    if row is None:
        conn.close()
        return JSONResponse(status_code=404, content={"error": "Subcategoría no encontrada."})

    nombre_anterior = row["nombre"]
    categoria = row["categoria"]

    try:
        conn.execute(
            "UPDATE subcategorias SET nombre = ? WHERE id = ?",
            (nombre_nuevo, subcategoria_id),
        )
        conn.execute(
            "UPDATE donaciones SET subcategoria = ? WHERE categoria = ? AND lower(subcategoria) = ?",
            (nombre_nuevo, categoria, nombre_anterior.lower()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return JSONResponse(status_code=409, content={"error": "Ya existe esa subcategoría para esta categoría."})

    row = conn.execute("SELECT * FROM subcategorias WHERE id = ?", (subcategoria_id,)).fetchone()
    conn.close()
    return dict(row)


@app.delete("/subcategorias/{subcategoria_id}")
async def eliminar_subcategoria(subcategoria_id: int):
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM subcategorias WHERE id = ?", (subcategoria_id,))
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return JSONResponse(status_code=404, content={"error": "Subcategoría no encontrada."})

    return {"ok": True}


class CentroCreate(BaseModel):
    nombre: str


class CentroUpdate(BaseModel):
    activo: bool


@app.get("/centros")
async def listar_centros(activo: bool | None = None):
    conn = get_db_connection()
    if activo is not None:
        rows = conn.execute(
            "SELECT * FROM centros_acopio WHERE activo = ? ORDER BY nombre",
            (int(activo),),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM centros_acopio ORDER BY nombre").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/centros")
async def crear_centro(centro: CentroCreate):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO centros_acopio (nombre) VALUES (?)",
            (centro.nombre.strip(),),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM centros_acopio WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        conn.close()
        return JSONResponse(status_code=409, content={"error": "Ya existe un centro de acopio con ese nombre."})
    conn.close()
    return dict(row)


@app.patch("/centros/{centro_id}")
async def actualizar_centro(centro_id: int, cambios: CentroUpdate):
    conn = get_db_connection()
    conn.execute(
        "UPDATE centros_acopio SET activo = ? WHERE id = ?",
        (int(cambios.activo), centro_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM centros_acopio WHERE id = ?", (centro_id,)).fetchone()
    conn.close()
    if row is None:
        return JSONResponse(status_code=404, content={"error": "Centro de acopio no encontrado."})
    return dict(row)


@app.delete("/centros/{centro_id}")
async def eliminar_centro(centro_id: int):
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM centros_acopio WHERE id = ?", (centro_id,))
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return JSONResponse(status_code=404, content={"error": "Centro de acopio no encontrado."})
    return {"ok": True}


@app.get("/")
async def root():
    return {
        "mensaje": "API de Clasificación de Donaciones activa con Llava.",
        "clasificacion": "POST /clasificar",
        "subcategorias": "GET/POST/PUT/DELETE /subcategorias",
        "centros": "GET/POST/PATCH/DELETE /centros",
    }