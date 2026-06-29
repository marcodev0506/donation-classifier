# Clasificador de Donaciones

Sistema para clasificar donaciones humanitarias mediante fotos. Usa visión por computadora con modelos locales de IA (Ollama + llava) y mantiene el inventario en SQLite.

## Arquitectura

```
donation-classifier/
├── backend/          # API REST en Python (FastAPI)
│   ├── main.py
│   └── requirements.txt
├── frontend/         # App móvil en React Native con Expo
│   ├── App.js
│   ├── config.js     # Configura la IP del servidor
│   ├── app.json
│   ├── babel.config.js
│   └── package.json
└── README.md
```

## Categorías soportadas

| Categoría     | Prioridad |
|---------------|-----------|
| Ropa          | Media     |
| Agua          | Alta      |
| Medicamentos  | Alta      |
| Alimentos     | Alta      |
| Higiene       | Alta      |
| Limpieza      | Alta      |
| Calzado       | Media     |
| Otros         | Baja      |

### Ejemplos por categoría

| Categoría    | Ejemplos |
|--------------|----------|
| Agua         | Botellones, garrafones, agua embotellada |
| Alimentos    | Sardinas, atún, arroz, pasta, harina, granos, enlatados, leche, jugos, bebidas hidratantes |
| Higiene      | Crema dental, cepillos dentales, jabón, shampoo, papel higiénico, toallas sanitarias, pañales, desodorante |
| Limpieza     | Cloro, detergente, desinfectante, lavaplatos, suavizante, limpiador de piso |
| Medicamentos | Pastillas, jarabes, vendas, gasas, botiquines, alcohol medicinal, agua oxigenada |
| Ropa         | Camisas, pantalones, cobijas, sábanas, toallas |
| Calzado      | Zapatos, tenis, botas, sandalias, cholas, zapatillas |

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

### Endpoints

| Método | Ruta                    | Descripción                                    |
|--------|-------------------------|------------------------------------------------|
| POST   | `/clasificar`           | Clasifica una imagen con el modelo de IA       |
| POST   | `/donaciones`           | Guarda una donación confirmada                 |
| GET    | `/donaciones`           | Lista donaciones, filtradas por centro         |
| GET    | `/donaciones/resumen`   | Resumen de totales por categoría               |
| PATCH  | `/donaciones/{id}`      | Actualiza una donación                         |
| DELETE | `/donaciones/{id}`      | Elimina una donación                           |
| GET    | `/subcategorias`        | Lista subcategorías por categoría              |
| POST   | `/subcategorias`        | Agrega una subcategoría                        |
| GET    | `/centros`              | Lista centros de acopio                        |
| POST   | `/centros`              | Crea un centro de acopio                       |
| PATCH  | `/centros/{id}`         | Activa o desactiva un centro                   |
| DELETE | `/centros/{id}`         | Elimina un centro de acopio                    |

**Ejemplo con curl:**
```bash
curl -X POST http://localhost:8000/clasificar -F "imagen=@/ruta/a/foto.jpg"
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
export const SUBCATEGORIAS_URL = `${API_BASE_URL}/subcategorias`;
export const CENTROS_URL = `${API_BASE_URL}/centros`;
```

**Cómo encontrar la IP local:**
- **Windows:** PowerShell → `ipconfig` → buscar "Dirección IPv4"
- **macOS/Linux:** Terminal → `ifconfig` o `ip addr`

La app y el servidor deben estar en la misma red local.

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

## Flujo de uso

1. Iniciar Ollama: `ollama serve`
2. Iniciar el backend: `uvicorn main:app --host 0.0.0.0 --port 8000`
3. Iniciar Expo: `npx expo start` (desde `/frontend`)
4. Escanear el QR con Expo Go en el dispositivo móvil
5. Seleccionar el centro de acopio activo
6. Capturar el artículo con la cámara
7. Revisar y, si es necesario, corregir la categoría, descripción, cantidad y subcategoría
8. Guardar la donación en SQLite
9. Abrir el inventario para ver el resumen del centro seleccionado

---

## Dependencias principales

### Backend
| Paquete           | Versión  | Uso                          |
|-------------------|----------|------------------------------|
| fastapi           | 0.111.0  | Framework API REST           |
| uvicorn           | 0.30.1   | Servidor ASGI                |
| requests          | 2.32.3   | Llamadas HTTP a Ollama       |
| httpx             | 0.27.0   | Llamadas HTTP asíncronas     |
| python-multipart  | 0.0.9    | Parsing de archivos          |

### Frontend
| Paquete       | Versión  | Uso                         |
|---------------|----------|-----------------------------|
| expo          | ~54.0.0  | Framework base              |
| expo-camera   | ~17.0.10 | Acceso a cámara             |
| react-native  | 0.81.5   | UI móvil multiplataforma    |

---

## Licencia

MIT — Libre para uso humanitario y comercial.
