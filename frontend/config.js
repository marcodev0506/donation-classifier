// Configuración del servidor backend
// Reemplaza la IP con la dirección local de tu máquina donde corre uvicorn.
// Puedes encontrarla ejecutando: ipconfig (Windows) o ifconfig (macOS/Linux)
// Ejemplo: http://192.168.1.45:8000

export const API_BASE_URL = "http://192.168.0.103:8000";
export const CLASIFICAR_URL = `${API_BASE_URL}/clasificar`;
export const DONACIONES_URL = `${API_BASE_URL}/donaciones`;
export const RESUMEN_URL = `${API_BASE_URL}/donaciones/resumen`;
export const SUBCATEGORIAS_URL = `${API_BASE_URL}/subcategorias`;
export const CENTROS_URL = `${API_BASE_URL}/centros`;
