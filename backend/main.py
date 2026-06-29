import base64
import json
import os
import sqlite3
from datetime import datetime, timezone

import requests
from fastapi import FastAPI, File, UploadFile
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

# Prompt optimizado para incluir la categoría de higiene
PROMPT = (
    "Eres un clasificador de donaciones humanitarias. Antes de clasificar, intenta leer cualquier texto, marca o etiqueta visible en el producto. "
    "Si la etiqueta dice shampoo, champú, Colgate, crema dental, jabón, cloro, detergente, desinfectante u otra palabra útil, usa ese texto para decidir.\n\n"
    "Clasifica el objeto en una sola de estas categorías:\n"
    "- 'medicamentos': Pastillas, cápsulas, jarabes, cajas de medicina, gasas, vendas, alcohol medicinal, agua oxigenada, botiquines, insumos médicos.\n"
    "- 'ropa': Camisas, pantalones, abrigos, suéteres, medias, ropa interior, sábanas, cobijas, paños, toallas, textiles.\n"
    "- 'calzado': Zapatos, tenis, botas, sandalias, cholas, zapatillas.\n"
    "- 'comida': Sardina, atún, enlatados, arroz, pasta, harina, granos, aceite, sal, azúcar, leche, jugos, gatorade, sueros bebibles, alimentos empacados.\n"
    "- 'higiene': Shampoo, champú, crema dental, Colgate, cepillo de dientes, jabón de baño, desodorante, papel higiénico, toallas sanitarias, pañales, productos de aseo personal.\n"
    "- 'limpieza': Cloro, detergente, lavaplatos, desinfectante, suavizante, jabón de lavar, limpiador de piso, productos de limpieza del hogar.\n"
    "- 'otros': Herramientas, juguetes, electrónicos u objetos que no entren claramente en lo anterior.\n\n"
    "Reglas importantes: cholas, sandalias, zapatos y calzado nunca son higiene. Si ves una botella o empaque pero la etiqueta dice shampoo/champú, clasifica como higiene; si dice cloro/detergente/desinfectante, clasifica como limpieza; si dice medicamento o farmacia, clasifica como medicamentos.\n"
    "Responde EXCLUSIVAMENTE con un objeto JSON plano, sin bloques de código, sin texto adicional.\n"
    "Estructura exacta del JSON:\n"
    "{\n"
    '  "categoria": "medicamentos" | "ropa" | "calzado" | "comida" | "higiene" | "limpieza" | "otros",\n'
    '  "subcategoria": "nombre específico del producto, por ejemplo: shampoo, pañales, atún, cloro, acetaminofén",\n'
    '  "descripcion_corta": "breve descripción del objeto en español, mencionando texto visible si lo puedes leer",\n'
    '  "conteo_estimado": 1,\n'
    '  "prioridad": "Alta" | "Media" | "Baja"\n'
    "}\n"
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
    conn.commit()
    conn.close()


def normalizar_subcategoria(categoria, nombre):
    """Devuelve el nombre canónico de una subcategoria, creándola si no existe."""
    if not nombre or not str(nombre).strip():
        return ""
    nombre_limpio = str(nombre).strip().lower()
    conn = _get_db_connection()
    row = conn.execute(
        "SELECT nombre FROM subcategorias WHERE categoria = ? AND lower(nombre) = ?",
        (categoria, nombre_limpio),
    ).fetchone()
    if row:
        canonical = row["nombre"]
    else:
        cursor = conn.execute(
            "INSERT INTO subcategorias (categoria, nombre) VALUES (?, ?)",
            (categoria, str(nombre).strip()),
        )
        conn.commit()
        canonical = str(nombre).strip()
    conn.close()
    return canonical


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
async def clasificar(imagen: UploadFile = File(...)):
    contenido = await imagen.read()
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
    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=180)
        respuesta.raise_for_status()
    except requests.exceptions.ConnectionError:
        return JSONResponse(
            status_code=503,
            content={"error": "No se puede conectar con Ollama. Verifica que 'ollama serve' esté corriendo."},
        )
    except requests.exceptions.Timeout:
        return JSONResponse(
            status_code=504,
            content={"error": "Ollama no respondió en 180 segundos. El modelo puede estar cargando o la PC saturada."},
        )
    except requests.exceptions.HTTPError as e:
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
async def listar_donaciones():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM donaciones ORDER BY id DESC").fetchall()
    conn.close()
    return [row_to_dict(row) for row in rows]


@app.get("/donaciones/resumen")
async def resumen_donaciones():
    conn = get_db_connection()
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


@app.get("/")
async def root():
    return {
        "mensaje": "API de Clasificación de Donaciones activa con Llava.",
        "clasificacion": "POST /clasificar",
        "subcategorias": "GET/POST/PUT/DELETE /subcategorias",
    }