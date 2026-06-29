# 🤝 Clasificador de Donaciones — Sistema Open-Source

Sistema completo para la clasificación automatizada de donaciones humanitarias mediante escaneo de fotos, usando visión por computadora con modelos de IA local (Ollama + llava) e inventario compartido en SQLite.

## Arquitectura

```
donation-classifier/
├── backend/          # API REST en Python (FastAPI)
│   ├── main.py
│   └── requirements.txt
├── frontend/         # App móvil React Native (Expo Go)
│   ├── App.js
│   ├── config.js     ← Configura tu IP aquí
│   ├── app.json
│   ├── babel.config.js
│   └── package.json
└── README.md
```

## Categorías soportadas

| Icono | Categoría     | Prioridad sugerida |
|-------|---------------|--------------------|
| 👕    | Ropa          | Media              |
| 💧    | Agua          | Alta               |
| 💊    | Medicamentos  | Alta               |
| 🥫    | Alimentos     | Alta               |
| 🧼    | Higiene       | Alta               |
| 📦    | Otros         | Baja               |

### Ejemplos considerados

| Categoría | Ejemplos |
|-----------|----------|
| Agua | Agua potable, botellones, garrafones |
| Alimentos | Sardinas, atún, arroz, pasta, harina, granos, enlatados, leche, jugos, gatorade |
| Higiene | Crema dental, Colgate, cepillos dentales, jabón, shampoo, papel higiénico, toallas sanitarias, pañales, desodorante, detergente |
| Medicamentos | Pastillas, jarabes, vendas, gasas, botiquines, alcohol medicinal, agua oxigenada |
| Ropa | Camisas, pantalones, zapatos, cholas, sandalias, cobijas, sábanas, toallas |

---

## Paso 1 — Instalar y ejecutar Ollama con llava

1. Descarga Ollama desde [https://ollama.com/download](https://ollama.com/download) e instálalo.
2. Descarga y ejecuta el modelo de visión (solo la primera vez, ~7 GB):

```bash
ollama pull llava
```

3. Inicia el servidor Ollama (queda escuchando en `http://localhost:11434`):

```bash
ollama serve
```

> En macOS y Windows, Ollama se inicia automáticamente como servicio tras la instalación. Puedes verificarlo con:
> ```bash
> curl http://localhost:11434
> ```

---

## Paso 2 — Backend (Python / FastAPI)

### Requisitos previos
- Python 3.10 o superior
- pip

### Instalación

```bash
cd backend
pip install -r requirements.txt
```

### Iniciar el servidor

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

El servidor quedará disponible en `http://0.0.0.0:8000`.

Puedes verificarlo abriendo `http://localhost:8000` en tu navegador o con:

```bash
curl http://localhost:8000
```

### Endpoint

| Método | Ruta         | Descripción                                      |
|--------|--------------|--------------------------------------------------|
| POST   | `/clasificar`| Recibe una imagen y devuelve la clasificación IA |
| POST   | `/donaciones`| Guarda una donación confirmada en SQLite |
| GET    | `/donaciones`| Lista todas las donaciones guardadas |
| GET    | `/donaciones/resumen`| Devuelve totales por categoría |
| PATCH  | `/donaciones/{id}`| Actualiza una donación |
| DELETE | `/donaciones/{id}`| Elimina una donación |

**Ejemplo con curl:**
```bash
curl -X POST http://localhost:8000/clasificar \
  -F "imagen=@/ruta/a/foto.jpg"
```

**Respuesta esperada:**
```json
{
  "categoria": "Alimentos",
  "descripcion_corta": "Cajas de conservas de atún apiladas",
  "conteo_estimado": 12,
  "prioridad": "Alta"
}
```

---

## Paso 3 — Configurar la IP del servidor en el frontend

Antes de iniciar la app, edita `frontend/config.js` y reemplaza la IP por la dirección local de tu máquina:

```js
// frontend/config.js
export const API_BASE_URL = "http://192.168.1.100:8000";
export const CLASIFICAR_URL = `${API_BASE_URL}/clasificar`;
export const DONACIONES_URL = `${API_BASE_URL}/donaciones`;
export const RESUMEN_URL = `${API_BASE_URL}/donaciones/resumen`;
```

**Cómo encontrar tu IP local:**
- **Windows:** Abre PowerShell y ejecuta `ipconfig` → busca "Dirección IPv4"
- **macOS/Linux:** Ejecuta `ifconfig` o `ip addr` en la terminal

> ⚠️ La app y el servidor deben estar en la **misma red Wi-Fi local**.

---

## Paso 4 — Frontend (Expo Go)

### Requisitos previos
- Node.js 18 o superior
- npm o yarn
- App **Expo Go** instalada en tu teléfono ([Android](https://play.google.com/store/apps/details?id=host.exp.exponent) / [iOS](https://apps.apple.com/app/expo-go/id982107779))

### Instalación

```bash
cd frontend
npm install
```

### Iniciar el servidor de desarrollo

```bash
npx expo start
```

Se mostrará un código QR en la terminal. Escanéalo con:
- **Android:** la app Expo Go directamente
- **iPhone:** la cámara nativa del teléfono

---

## Flujo completo de uso

1. 🖥️ Inicia Ollama: `ollama serve`
2. 🐍 Inicia el backend: `uvicorn main:app --host 0.0.0.0 --port 8000`
3. 📱 Inicia Expo: `npx expo start` (desde `/frontend`)
4. Escanea el QR con Expo Go en tu teléfono
5. Apunta la cámara al artículo de donación y presiona el botón blanco
6. Espera el análisis del modelo local
7. Visualiza la tarjeta con los resultados de clasificación
8. Presiona **Guardar donación** para registrar el resultado en SQLite
9. Presiona **Ver inventario** para consultar el resumen compartido

---

## Dependencias principales

### Backend
| Paquete           | Versión  | Uso                          |
|-------------------|----------|------------------------------|
| fastapi           | 0.111.0  | Framework API REST           |
| uvicorn           | 0.30.1   | Servidor ASGI                |
| requests          | 2.32.3   | Llamadas HTTP a Ollama       |
| python-multipart  | 0.0.9    | Parsing de archivos (UploadFile) |

### Frontend
| Paquete       | Versión  | Uso                         |
|---------------|----------|-----------------------------|
| expo          | ~54.0.0  | Framework base              |
| expo-camera   | ~17.0.10 | Acceso a cámara             |
| react-native  | 0.81.5   | UI móvil multiplataforma    |

---

## Licencia

MIT — Libre para uso humanitario y comercial.
