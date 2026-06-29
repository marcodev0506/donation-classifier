import asyncio
import base64
import json
import os
import sqlite3
from datetime import datetime, timezone

import httpx
import requests
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

# Prompt optimizado para clasificación de donaciones en Venezuela
PROMPT = (
    "Eres un sistema experto en clasificación de donaciones humanitarias para Venezuela. "
    "Tu tarea es analizar el texto, marcas, etiquetas o descripción de un producto y clasificarlo "
    "en una sola categoría con su respectiva información.\n\n"
    "=== DICCIONARIO DE PALABRAS CLAVE (CONTEXTO: FARMATODO / LOCATEL / VENEZUELA) ===\n"
    "- MEDICAMENTOS: Atamel, Tachipirin, Teragrip, Alival, Brugesic, Ibuprofeno, Acetaminofén, Paracetamol, "
    "Diclofenac, Buscapina, Gastrial, Nourgasin, Loperamida, LiFull, Alikal, "
    "Loratadina, Allegra, Sinutab, Amoxicilina, Ampollas, Jarabe, Gotas, Antialérgico, Antibiótico, "
    "Analgésico, Vitamina C, Cevalin, Redoxon, Complejo B, Ácido fólico, Calcio, Pastillas, Cápsulas, "
    "Blister, Gasas, Vendas, Adhesivo médico, Algodón, Alcohol medicinal, Agua oxigenada, Povidona, "
    "Betadine, Curitas, Inyectadoras, Jeringas, Tapabocas, Mascarillas, Guantes quirúrgicos.\n"
    "- HIGIENE: Every Night, Drene, Pantene, Head & Shoulders, Sedal, Shampoo, Champú, Acondicionador, "
    "Baño de crema, Jabón Las Llaves (baño), Protex, Palmolive, Dove, Rexona, Speed Stick, Mum, Gillette, "
    "Prestobarba, Crema dental, Colgate, Close-Up, Oral-B, Cepillo de dientes, Enjuague bucal, Listerine, "
    "Saba, Nosotras, Toallas sanitarias, Protectores diarios, Tampones, Pampers, Huggies, Pañales (infantiles/adultos), "
    "Toallitas húmedas, Desodorante, Papel higiénico, Cotones, Q-tips.\n"
    "- LIMPIEZA: Cloro, Nevex, Detergente, Ace, Ariel, Las Llaves (lavar), Mistolín, Más, Desinfectante, "
    "Lavaplatos, Axion, Limón, Suavizante, Downy, Azulillo, Jabón de panela, Limpiador de pocetas, Harpic, "
    "Desengrasante, Esponja de brillo, Paño amarillo (para limpiar).\n\n"
    "=== CATEGORÍAS DISPONIBLES ===\n"
    "- 'medicamentos': Todo lo listado en su sección del diccionario, insumos médicos, tratamientos y botiquines.\n"
    "- 'higiene': Todo lo relacionado al aseo y cuidado personal corporal e íntimo.\n"
    "- 'limpieza': Productos químicos y utensilios destinados estrictamente al mantenimiento del hogar u oficina.\n"
    "- 'ropa': Camisas, pantalones, shorts, interiores, panties, sostenes, medias, abrigos, suéteres, uniformes, "
    "sábanas, cobijas, edredones, toallas de baño, paños de cuerpo, textiles en general.\n"
    "- 'calzado': Zapatos, tenis, botas, sandalias, cholas, zapatillas, calzado deportivo.\n"
    "- 'comida': Alimentos no perecederos, enlatados (atún, sardina), arroz, pasta, harina pan, granos, aceite, "
    "azúcar, sal, leche en polvo, avena, toddy, jugos, gatorade, sueros orales (Pedialyte).\n"
    "- 'otros': Herramientas, juguetes, electrónicos o artículos que no pertenezcan a ninguna categoría anterior.\n\n"
    "=== REGLAS CRÍTICAS DE EXCLUSIÓN Y ENFOQUE ===\n"
    "1. REGLA DE LA TOALLA/PAÑO: Una 'toalla de baño' o 'paño de cuerpo' es ROPA. Una 'toalla sanitaria' o 'toallita húmeda' es HIGIENE. Un 'paño amarillo' o 'paño de cocina' es LIMPIEZA.\n"
    "2. REGLA DE LOS JABONES: Si dice 'jabón de baño', 'jabón líquido corporal' o marcas como Protex/Dove, es HIGIENE. Si dice 'jabón de panela', 'jabón de lavar' o marcas como Las Llaves/Ace, es LIMPIEZA.\n"
    "3. REGLA DE LOS SUEROS: Los sueros medicinales endovenosos o de hidratación extrema (ej. Ringer, Fisiológico) son MEDICAMENTOS. Los sueros de tomar (Pedialyte, Gluco-Oral) o bebidas deportivas son COMIDA.\n"
    "4. Si el empaque menciona marcas exclusivas de Farmatodo/Locatel de cuidado personal (ej. 'Formulaciones Farmatodo'), clasifícalo en HIGIENE, a menos que sea un fármaco activo, en cuyo caso es MEDICAMENTOS.\n\n"
    "=== FORMATO DE SALIDA ===\n"
    "Responde EXCLUSIVAMENTE con un objeto JSON plano, sin bloques de código (sin ```json ... ```), sin texto adicional.\n"
    "Estructura exacta del JSON:\n"
    "{\n"
    '  "categoria": "medicamentos" | "ropa" | "calzado" | "comida" | "higiene" | "limpieza" | "otros",\n'
    '  "subcategoria": "Nombre específico deducido (ej: acetaminofén, shampoo, franela, zapatos). Si no se lee, dejar cadena vacía \"\".",\n'
    '  "descripcion_corta": "Breve descripción del objeto en español.",\n'
    '  "conteo_estimado": 1,\n'
    '  "prioridad": "Alta" | "Media" | "Baja"\n'
    "}\n\n"
    "Prioridades: comida/medicamentos/higiene/limpieza = Alta; ropa/calzado = Media; otros = Baja."
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


@app.on_event("startup")
def on_startup():
    init_db()


@app.post("/clasificar")
async def clasificar(request: Request, imagen: UploadFile = File(...)):
    contenido = await imagen.read()
    if await request.is_disconnected():
        return JSONResponse(status_code=499, content={"error": "Cliente desconectado antes de procesar."})

    imagen_b64 = base64.b64encode(contenido).decode("utf-8")

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": PROMPT,
        "images": [imagen_b64],
        "format": "json",
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "temperature": 0.2,
            "num_predict": 120,
        },
    }

    print(f"[OLLAMA] Enviando imagen a {OLLAMA_MODEL}... ({len(imagen_b64) // 1024} KB)")

    async def llamar_ollama():
        async with httpx.AsyncClient(timeout=180.0) as client:
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
            content={"error": "Ollama no respondió en 180 segundos. El modelo puede estar cargando o la PC saturada."},
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