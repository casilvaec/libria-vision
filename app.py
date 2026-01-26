# ============================================================
# IMPORTS
# ============================================================
import os
import json
import base64
import logging
import time
import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# ============================================================
# IMPORTS - RATE LIMITING
# ============================================================
from utils.rate_limiter import (
    get_device_fingerprint,
    check_rate_limit,
    increment_usage,
    mostrar_cuota
)


# ============================================================
# LOGGING CONFIGURATION
# ============================================================
# Configura el sistema de logging para guardar eventos importantes
# - level=INFO: Registra información general, advertencias y errores
# - FileHandler: Guarda logs en archivo 'libria.log' para análisis posterior
# - StreamHandler: Muestra logs en consola para debugging en tiempo real
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('libria.log'),  # Persiste logs en disco
        logging.StreamHandler()  # Muestra en terminal/consola
    ]
)
logger = logging.getLogger(__name__)
# __name__ asegura que el logger tenga el nombre del módulo actual


# ============================================================
# CARGA DE VARIABLES DE ENTORNO
# ============================================================
load_dotenv()
# Carga variables desde archivo .env (debe estar en .gitignore)
# SEGURIDAD: Nunca subas el .env a repositorios públicos
logger.info("Variables de entorno cargadas desde .env")


# ============================================================
# CONFIG GENERAL (APP + SEGURIDAD BÁSICA)
# ============================================================

# Límite de tamaño de imagen
# ¿Por qué? - Previene ataques DoS (subir archivos gigantes)
#           - Reduce costos API (imágenes grandes = más tokens)
#           - Mejora UX (uploads rápidos)
MAX_IMAGE_MB = 5
MAX_IMAGE_BYTES = MAX_IMAGE_MB * 1024 * 1024

# Control de visualización de errores técnicos
# MEJORA: Ahora se controla desde variable de entorno
# - En desarrollo: DEBUG=true en .env
# - En producción: DEBUG=false o sin definir
SHOW_DEBUG_ERRORS = os.getenv("DEBUG", "False").lower() == "true"
logger.info(f"Modo debug activado: {SHOW_DEBUG_ERRORS}")


# ============================================================
# PROMPTS COMO CONSTANTES
# ============================================================
# BUENA PRÁCTICA: Centralizar prompts facilita:
# - Ajustes rápidos sin tocar lógica
# - Experimentación con diferentes versiones
# - Reutilización en múltiples funciones

SYSTEM_PROMPT = (
    "Eres un extractor de datos de portadas de libros. "
    "Devuelve únicamente JSON válido, sin texto extra, sin Markdown."
)
# Define el "rol" del asistente: especialista en extraer datos de portadas

USER_PROMPT = """
Extrae SOLO:
- titulo
- autor

Reglas:
- Responde únicamente JSON estricto.
- Si no estás seguro, usa null.
- No inventes editorial, año, sinopsis, etc.

Formato exacto:
{
  "titulo": "…",
  "autor": "…"
}
"""
# Instrucciones específicas de la tarea
# - "SOLO titulo y autor": Evita campos extras innecesarios
# - "null si no estás seguro": Previene alucinaciones (datos inventados)
# - "JSON estricto": Facilita el parsing programático


# ============================================================
# CLIENTE OPENAI (CACHEADO PARA STREAMLIT)
# ============================================================

@st.cache_resource
def get_openai_client() -> OpenAI:
    """
    Crea y cachea el cliente de OpenAI.
    
    ¿Por qué cache?
    - Streamlit re-ejecuta el script completo en cada interacción
    - @st.cache_resource mantiene el cliente en memoria entre ejecuciones
    - Evita crear múltiples conexiones innecesarias
    - Mejora rendimiento y consistencia
    
    Returns:
        OpenAI: Cliente configurado y listo para usar
        
    Raises:
        ValueError: Si OPENAI_API_KEY no está en variables de entorno
    """
    api_key = os.getenv("OPENAI_API_KEY")
    
    # MEJORA: Validación temprana de API key
    # Falla rápido con mensaje claro en lugar de error críptico después
    if not api_key:
        logger.error("OPENAI_API_KEY no encontrada en variables de entorno")
        raise ValueError(
            "OPENAI_API_KEY no configurada. "
            "Por favor crea un archivo .env con tu clave de API."
        )
    
    logger.info("Cliente OpenAI inicializado correctamente")
    return OpenAI(api_key=api_key)


# ============================================================
# UI BÁSICA (CONFIGURACIÓN DE PÁGINA)
# ============================================================

# IMPORTANTE: set_page_config() DEBE ser el primer comando Streamlit
st.set_page_config(
    page_title="LibrIA – Escáner de Visión",  # Título en pestaña del navegador
    page_icon="📚",  # Emoji que aparece en la pestaña
    layout="centered",  # Alternativa: "wide" para usar todo el ancho
    initial_sidebar_state="collapsed"  # NUEVO: Oculta sidebar por defecto
)

st.title("📚 LibrIA – Escáner de Visión ")
st.markdown(
    "Sube una foto de la **portada del libro** y la IA extraerá "
    "el título y autor automáticamente."
)

# ============================================================
# RATE LIMITING - VERIFICACIÓN INICIAL
# ============================================================
# Obtener fingerprint del dispositivo
device_id = get_device_fingerprint()

# Verificar si puede hacer búsquedas
puede_buscar, restantes = check_rate_limit(device_id)

# Mostrar cuota restante
mostrar_cuota(restantes)

# Si llegó al límite, detener la app
if not puede_buscar:
    st.error(
        "❌ Has alcanzado tu límite de 3 búsquedas gratuitas.\n\n"
        
    )
    st.stop()
#st.write("Sube una foto de la portada. La IA devolverá **solo Título y Autor** (JSON estricto).")



# NUEVO: Info box con instrucciones
with st.expander("📖 ¿Cómo usarlo?", expanded=False):
    st.markdown("""
    1. 📸 Sube o toma foto de la portada
    2. ⚡ Presiona "Detectar Título y Autor"
    3. ✅ Recibe los datos en segundos
    
    **Tips para mejores resultados:**
    - Foto frontal y centrada
    - Buena iluminación
    - Texto legible
    """)

# Log de inicio de sesión (útil para analytics o debugging)
logger.info("Nueva sesión iniciada en LibrIA")


# ============================================================
# HELPERS (FUNCIONES AUXILIARES)
# ============================================================

def image_bytes_to_data_url(image_bytes: bytes, mime: str) -> str:
    """
    Convierte bytes de imagen en Data URL para OpenAI Vision API.
    
    ¿Por qué Data URL?
    - OpenAI Vision API requiere imágenes en formato base64 dentro de Data URLs
    - Permite enviar la imagen directamente sin subirla a un servidor externo
    - Más eficiente para imágenes de tamaño razonable
    
    Args:
        image_bytes (bytes): Bytes crudos de la imagen cargada
        mime (str): Tipo MIME (ej: "image/jpeg", "image/png", "image/webp")
    
    Returns:
        str: Data URL en formato estándar "data:{mime};base64,{datos_codificados}"
    
    Example:
        >>> data_url = image_bytes_to_data_url(img_bytes, "image/jpeg")
        >>> # Retorna: "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
    """
    # Codifica bytes a base64 y convierte a string UTF-8
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    # Retorna en formato Data URL estándar (RFC 2397)
    return f"data:{mime};base64,{b64}"


def safe_json_parse(content: str) -> dict:
    """
    Parse robusto de JSON con recuperación de errores.
    
    Estrategia de dos niveles:
    1. Intenta parsear directamente (caso ideal)
    2. Si falla, busca el primer objeto JSON válido dentro del texto
    
    ¿Por qué necesitamos esto?
    - A veces GPT responde con ```json {...} ``` a pesar de las instrucciones
    - Puede incluir texto antes/después del JSON
    - Queremos recuperarnos de estos casos sin fallar completamente
    
    Args:
        content (str): String que debería contener JSON
    
    Returns:
        dict: Objeto Python parseado desde el JSON
        
    Raises:
        json.JSONDecodeError: Si no se puede parsear ni recuperar JSON válido
    """
    content = content.strip()  # Elimina espacios en blanco al inicio/final

    try:
        # INTENTO 1: Parse directo (caso ideal, más rápido)
        return json.loads(content)
        
    except json.JSONDecodeError as e:
        # INTENTO 2: Recuperación - extraer JSON del texto
        logger.warning(f"JSON parse falló, intentando recuperación. Error: {e}")
        
        # Busca el primer '{' y último '}' para extraer el objeto JSON
        start = content.find("{")
        end = content.rfind("}")
        
        # Valida que encontramos ambos delimitadores en orden correcto
        if start != -1 and end != -1 and end > start:
            try:
                # Extrae el substring y parsealo
                recovered_json = json.loads(content[start:end + 1])
                logger.info("JSON recuperado exitosamente mediante extracción")
                return recovered_json
            except json.JSONDecodeError:
                # La recuperación también falló
                logger.error(f"Recuperación de JSON falló. Contenido: {content[:200]}...")
                raise
        
        # Si no pudimos recuperar, re-lanzamos el error original
        logger.error(f"No se pudo recuperar JSON. Contenido: {content[:200]}...")
        raise


def extract_title_author(client: OpenAI, image_bytes: bytes, mime: str) -> dict:
    """
    Extrae título y autor de una portada usando GPT-4o-mini Vision.
    
    Proceso:
    1. Convierte imagen a Data URL
    2. Envía a OpenAI con prompts específicos
    3. Parsea respuesta JSON de forma robusta
    
    Args:
        client (OpenAI): Cliente OpenAI configurado (inyección de dependencias)
        image_bytes (bytes): Bytes de la imagen de la portada
        mime (str): Tipo MIME de la imagen
    
    Returns:
        dict: Diccionario con estructura {"titulo": "...", "autor": "..."}
              Valores pueden ser None/null si no se detectaron
        
    Raises:
        Exception: Errores de API o parsing (manejados en el caller)
    """
    logger.info(f"Iniciando extracción de título/autor. Tamaño imagen: {len(image_bytes)} bytes")
    
    # Convierte la imagen al formato requerido por OpenAI Vision
    data_url = image_bytes_to_data_url(image_bytes, mime)

    # Llamada a la API de OpenAI
    # BUENA PRÁCTICA: Usar las constantes definidas al inicio
    resp = client.chat.completions.create(
        model="gpt-4o-mini",  
        # gpt-4o-mini: Modelo con visión, balance costo/rendimiento
        # Alternativas: gpt-4o (más preciso, más caro), gpt-4-vision-preview
        
        temperature=0,  
        # temperature=0: Respuestas determinísticas (siempre iguales)
        # CRUCIAL para extracción de datos: queremos precisión, no creatividad
        # Rango: 0 (determinístico) a 2 (muy aleatorio/creativo)
        timeout=30,
        messages=[
            # Estructura de mensajes del Chat Completions API
            {"role": "system", "content": SYSTEM_PROMPT},
            # "system": Define el comportamiento/personalidad del asistente
            
            {
                "role": "user",
                "content": [
                    # Contenido multimodal: texto + imagen
                    {"type": "text", "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                    # OpenAI Vision permite combinar múltiples tipos de contenido
                ],
            },
        ],
    )

    # Extrae el contenido de la respuesta
    content = resp.choices[0].message.content or ""
    # "or ''": Manejo defensivo, previene error si content es None
    
    logger.info(f"Respuesta recibida de OpenAI. Longitud: {len(content)} caracteres")

    # Parsea el JSON de forma robusta usando nuestro helper
    result = safe_json_parse(content)
    
    logger.info(f"Extracción exitosa - Título: {result.get('titulo')}, Autor: {result.get('autor')}")
    return result


# ============================================================
# UI PRINCIPAL (INTERFAZ DE USUARIO)
# ============================================================

# Widget para subir archivos
uploaded = st.file_uploader(
    "📷 Sube la portada (JPG/PNG/WebP)", 
    type=["jpg", "jpeg", "png", "webp"]
    # SEGURIDAD: Lista blanca de extensiones
    # Solo acepta formatos de imagen comunes y seguros
    # Previene subida de ejecutables, scripts, etc.
)

# Condicional: Solo procesar si hay un archivo subido
if uploaded:
    # Lee los bytes del archivo
    image_bytes = uploaded.read()
    # NOTA: .read() carga todo en memoria
    # Para archivos muy grandes (>100MB) considerar streaming
    
    mime = uploaded.type or "image/jpeg"
    # uploaded.type puede ser None en algunos casos
    # BUENA PRÁCTICA: Siempre tener un valor por defecto
    
    logger.info(f"Archivo subido: {uploaded.name}, Tamaño: {len(image_bytes)} bytes, MIME: {mime}")

    # --------------------------------------------------------
    # VALIDACIÓN DE TAMAÑO (SEGURIDAD + UX + COSTOS)
    # --------------------------------------------------------
    if len(image_bytes) > MAX_IMAGE_BYTES:
        # Calcula tamaño en MB para mostrar al usuario
        size_mb = len(image_bytes) / 1024 / 1024
        
        logger.warning(f"Imagen rechazada por tamaño: {size_mb:.2f} MB (límite: {MAX_IMAGE_MB} MB)")
        
        st.error(
            f"❌ La imagen es muy pesada ({size_mb:.2f} MB). "
            f"Por favor sube una imagen de máximo {MAX_IMAGE_MB} MB."
        )
        
        # Ayuda adicional al usuario
        st.info(
            "💡 **Tip:** Puedes reducir el tamaño de tu imagen en:\n"
            "- 🌐 [TinyPNG](https://tinypng.com) - Compresión sin pérdida visible\n"
            "- 🌐 [Squoosh](https://squoosh.app) - Control avanzado de compresión\n"
            "- 📱 Toma la foto en resolución media en lugar de alta"
        )
        
        st.stop()
        # st.stop(): Detiene la ejecución del script aquí
        # Previene procesamiento innecesario y ahorra recursos

    # Muestra preview de la imagen al usuario
    st.image(image_bytes, caption="Imagen cargada", use_container_width=True)
    # use_container_width=True: Ajusta imagen al ancho del contenedor (responsive)

    # Botón principal de acción
    if st.button("🔎 Detectar Título y Autor", type="primary"):
        # type="primary": Estilo visual destacado (color azul por defecto)
        # Indica la acción principal de la página
        
        logger.info("Usuario presionó botón 'Detectar Título y Autor'")
        
        # --------------------------------------------------------
        # VALIDACIÓN DE API KEY
        # --------------------------------------------------------
        if not os.getenv("OPENAI_API_KEY"):
            logger.error("Intento de uso sin OPENAI_API_KEY configurada")
            
            st.error("❌ Falta OPENAI_API_KEY en variables de entorno (.env).")
            
            # Instrucciones para el usuario
            st.info(
                "**¿Cómo configurar la API Key?**\n\n"
                "1. Crea un archivo `.env` en la raíz del proyecto\n"
                "2. Agrega la línea: `OPENAI_API_KEY=tu-clave-aqui`\n"
                "3. Obtén tu clave en: https://platform.openai.com/api-keys\n"
                "4. Reinicia la aplicación"
            )
            
            st.stop()

        # Spinner: Indicador visual durante procesamiento
        with st.spinner("Analizando portada..."):
            # Context manager: automáticamente muestra/oculta el spinner
            # UX: Crítico mostrar feedback en operaciones que toman >1 segundo
            
            try:
                # Obtiene el cliente OpenAI (cacheado)
                client = get_openai_client()
                
                # Llama a la función de extracción
                # result = extract_title_author(client, image_bytes, mime)
                # URL del webhook de n8n
                webhook_url = "https://carlossilvatech.app.n8n.cloud/webhook-test/libria/research"
                
                # Prepara los datos
                payload = {
                        "titulo": titulo,  # O el valor que tengas
                        "autor": autor,    # O el valor que tengas
                        "requestId": f"req-{int(time.time())}
                        
                    }
                
                # Llama al webhook
                    response = requests.post(webhook_url, json=payload, timeout=30)
                    response_data = response.json()
                
                # AQUÍ ESTÁ LA PARTE IMPORTANTE - Extrae solo el body
                    result = response_data.get("body", {})
                # Extrae los campos del resultado
                titulo = result.get("titulo")
                autor = result.get("autor")
                # .get(): Retorna None si la key no existe (seguro)
                # Alternativa: result["titulo"] lanzaría KeyError si no existe

                # ========================================
                # PRESENTACIÓN DE RESULTADOS
                # ========================================
                
                st.success("✅ Listo")
                # Mensaje de éxito para feedback positivo
                
                st.subheader("Resultado")
                st.write(f"**Título:** {titulo or 'No detectado'}")
                st.write(f"**Autor:** {autor or 'No detectado'}")
                # "or 'No detectado'": Maneja el caso None de forma user-friendly

                # Muestra el JSON crudo para usuarios avanzados/debugging
                st.subheader("JSON devuelto")
                st.json(result)
                # ============================================================
                # RATE LIMITING - INCREMENTAR CONTADOR
                # ============================================================
                # Solo incrementar si la búsqueda fue exitosa
                increment_usage()
                # st.json(): Formatea y colorea el JSON automáticamente
                
                logger.info("Resultados mostrados exitosamente al usuario")

            except ValueError as e:
                # Captura errores de validación (ej: API key no configurada)
                logger.error(f"Error de validación: {str(e)}", exc_info=True)
                st.error(f"❌ Error de configuración: {str(e)}")
                
            except Exception as e:
                # Captura cualquier otro error (API, red, parsing, etc.)
                logger.error(f"Error al extraer título/autor: {str(e)}", exc_info=True)
                # exc_info=True: Guarda el stacktrace completo en el log
                
                # ========================================
                # MANEJO DE ERRORES USER-FRIENDLY
                # ========================================
                
                st.error(
                    "❌ No se pudo extraer el título y autor. "
                    "Consejos: usa una foto frontal, con buena luz y sin reflejos."
                )
                # Mensaje amigable con consejos accionables
                
                # Tips adicionales para ayudar al usuario
                st.warning(
                    "**💡 Recomendaciones para mejores resultados:**\n\n"
                    "✓ Foto frontal de la portada (no en ángulo)\n"
                    "✓ Buena iluminación sin reflejos\n"
                    "✓ Texto claramente legible\n"
                    "✓ Portada completa en el encuadre\n"
                    "✓ Evita sombras o brillos en el texto"
                )

                # ========================================
                # DEBUG CONTROLADO (MEJORA PROFESIONAL)
                # ========================================
                
                if SHOW_DEBUG_ERRORS:
                    # Modo desarrollo: Muestra stacktrace completo
                    st.exception(e)
                    st.code(f"Error type: {type(e).__name__}")
                    # Útil para debugging durante desarrollo
                else:
                    # Modo producción: Oculta detalles técnicos
                    # SEGURIDAD: No expone información interna del sistema
                    # UX: Evita confundir al usuario con errores técnicos
                    
                    # Los errores ya están loggeados para análisis posterior
                    pass


# ============================================================
# FOOTER INFORMATIVO (OPCIONAL)
# ============================================================

st.divider()  # Línea separadora visual

st.caption(
    "🤖 Powered by OpenAI GPT-4o-mini Vision | "
    "📝 LibrIA v2.0 | "
    f"🐛 Debug mode: {'ON' if SHOW_DEBUG_ERRORS else 'OFF'}"
)
# Información de versión y estado para contexto

logger.info("Renderizado completo de la página")