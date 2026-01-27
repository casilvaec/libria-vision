# ============================================================
# LIBRIA - APP PRINCIPAL
# ============================================================
# Aplicación de reseñas inteligentes de libros
# Versión 3.1 - Con campos condicionales reactivos y Telegram QR

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
# IMPORTS - RATE LIMITING Y UI
# ============================================================
from utils.rate_limiter import (
    get_device_fingerprint,
    check_rate_limit,
    increment_usage,
    mostrar_cuota
)
from utils.ui_components import (
    inject_mobile_css,
    validar_email,
    validar_telefono,
    mostrar_header,
    get_codigos_pais
)
from utils.pdf_generator import generar_pdf
from utils.email_sender import enviar_pdf_email


# ============================================================
# LOGGING CONFIGURATION
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('libria.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================
# CARGA DE VARIABLES DE ENTORNO
# ============================================================
load_dotenv()
logger.info("Variables de entorno cargadas desde .env")


# ============================================================
# CONFIG GENERAL
# ============================================================
MAX_IMAGE_MB = 5
MAX_IMAGE_BYTES = MAX_IMAGE_MB * 1024 * 1024
SHOW_DEBUG_ERRORS = os.getenv("DEBUG", "False").lower() == "true"
logger.info(f"Modo debug activado: {SHOW_DEBUG_ERRORS}")


# ============================================================
# PROMPTS COMO CONSTANTES
# ============================================================
SYSTEM_PROMPT = (
    "Eres un extractor de datos de portadas de libros. "
    "Devuelve únicamente JSON válido, sin texto extra, sin Markdown."
)

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


# ============================================================
# CLIENTE OPENAI (CACHEADO)
# ============================================================
@st.cache_resource
def get_openai_client() -> OpenAI:
    """Crea y cachea el cliente de OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        logger.error("OPENAI_API_KEY no encontrada en variables de entorno")
        raise ValueError(
            "OPENAI_API_KEY no configurada. "
            "Por favor crea un archivo .env con tu clave de API."
        )
    
    logger.info("Cliente OpenAI inicializado correctamente")
    return OpenAI(api_key=api_key)


# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="LibrIA – ¿De qué trata el libro?",
    page_icon="assets/logo-libria-transparente.png",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Inyectar CSS Mobile-First con branding
inject_mobile_css()

# Mostrar header mejorado
mostrar_header()


# Debug solo en consola/log (no en UI)
if SHOW_DEBUG_ERRORS:
    from pathlib import Path
    logger.info(
        "Logo exists: %s",
        (Path(__file__).resolve().parent / "assets" / "logo-libria-transparente.png").exists()
    )




# ============================================================
# RATE LIMITING - VERIFICACIÓN INICIAL
# ============================================================
device_id = get_device_fingerprint()
puede_buscar, restantes = check_rate_limit(device_id)
mostrar_cuota(restantes)

if not puede_buscar:
    st.error(
        "❌ Has alcanzado tu límite de 3 búsquedas gratuitas.\n\n"
        "💡 Si eres evaluador del proyecto, usa el link especial con tu token de acceso."
    )
    st.stop()

logger.info("Nueva sesión iniciada en LibrIA")


# ============================================================
# HELPERS (FUNCIONES AUXILIARES)
# ============================================================

def image_bytes_to_data_url(image_bytes: bytes, mime: str) -> str:
    """Convierte bytes de imagen en Data URL para OpenAI Vision API."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def safe_json_parse(content: str) -> dict:
    """Parse robusto de JSON con recuperación de errores."""
    content = content.strip()

    try:
        return json.loads(content)
        
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse falló, intentando recuperación. Error: {e}")
        
        start = content.find("{")
        end = content.rfind("}")
        
        if start != -1 and end != -1 and end > start:
            try:
                recovered_json = json.loads(content[start:end + 1])
                logger.info("JSON recuperado exitosamente mediante extracción")
                return recovered_json
            except json.JSONDecodeError:
                logger.error(f"Recuperación de JSON falló. Contenido: {content[:200]}...")
                raise
        
        logger.error(f"No se pudo recuperar JSON. Contenido: {content[:200]}...")
        raise


def extract_title_author(client: OpenAI, image_bytes: bytes, mime: str) -> dict:
    """Extrae título y autor de una portada usando GPT-4o-mini Vision."""
    logger.info(f"Iniciando extracción de título/autor. Tamaño imagen: {len(image_bytes)} bytes")
    
    data_url = image_bytes_to_data_url(image_bytes, mime)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        timeout=30,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    )

    content = resp.choices[0].message.content or ""
    logger.info(f"Respuesta recibida de OpenAI. Longitud: {len(content)} caracteres")

    result = safe_json_parse(content)
    logger.info(f"Extracción exitosa - Título: {result.get('titulo')}, Autor: {result.get('autor')}")
    return result


def llamar_n8n_webhook(titulo: str, autor: str, email: str = None, telegram_code: str = None) -> dict:
    """
    Llama al webhook de n8n para buscar reseñas.
    
    Args:
        titulo: Título del libro
        autor: Autor del libro
        email: Email del usuario (opcional)
        telegram_code: Código QR de Telegram (opcional)
        
    Returns:
        dict: Respuesta JSON del webhook con la ficha completa
    """
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    
    if not webhook_url:
        logger.error("N8N_WEBHOOK_URL no configurada")
        raise ValueError("N8N_WEBHOOK_URL no configurada en .env")
    
    payload = {
        "titulo": titulo,
        "autor": autor,
        "requestId": f"req-{int(time.time())}",
        "device_id": device_id,
        "email": email,
        "telegram_code": telefono_completo,  # Nuevo: código QR en lugar de teléfono
        "generar_audio": bool(telegram_code)
    }
    
    logger.info(f"Llamando webhook n8n para: {titulo} - {autor}")
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        logger.info("Respuesta exitosa de n8n webhook")
        return data
        
    except requests.exceptions.Timeout:
        logger.error("Timeout al llamar n8n webhook")
        raise Exception("El servidor tardó demasiado en responder. Intenta nuevamente.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al llamar n8n webhook: {str(e)}")
        raise Exception(f"Error al conectar con el servidor: {str(e)}")


# ============================================================
# UI PRINCIPAL - PASO 1: CAPTURA DE IMAGEN
# ============================================================
st.write("### 📸 Paso 1: Sube la portada del libro")

# Solo file uploader (sin cámara)
archivo = st.file_uploader(
    "Selecciona una imagen",
    type=["jpg", "jpeg", "png", "webp"],
    help="Sube una foto clara de la portada del libro"
)

if not archivo:
    st.info("👆 Sube una imagen para comenzar")
    st.stop()

# Validar tamaño de imagen
image_bytes = archivo.read()
mime = archivo.type or "image/jpeg"

if len(image_bytes) > MAX_IMAGE_BYTES:
    size_mb = len(image_bytes) / 1024 / 1024
    logger.warning(f"Imagen rechazada por tamaño: {size_mb:.2f} MB")
    st.error(f"❌ La imagen es muy pesada ({size_mb:.2f} MB). Máximo {MAX_IMAGE_MB} MB.")
    st.info(
        "💡 **Tip:** Reduce el tamaño en [TinyPNG](https://tinypng.com) "
        "o ajusta la calidad de la foto."
    )
    st.stop()

# Mostrar preview
st.image(image_bytes, caption="Portada cargada", use_container_width=True)


# ============================================================
# UI PRINCIPAL - PASO 2: OPCIONES DE ENTREGA (REACTIVAS)
# ============================================================
st.write("### 📬 Paso 2: ¿Cómo quieres recibir tu reseña?")

st.write("Selecciona al menos una opción adicional:")

# Visualizar en pantalla - SIEMPRE ACTIVO
st.checkbox("👀 Visualizar en pantalla", value=True, disabled=True, 
            help="Siempre se mostrará en pantalla", key="mostrar_web")

# Email opcional - CON CAMPO CONDICIONAL REACTIVO
enviar_email = st.checkbox("📧 Recibir PDF por correo", key="check_email")

# Contenedor reactivo para email
email_container = st.empty()
email = ""

if enviar_email:
    with email_container.container():
        email = st.text_input(
            "Tu email",
            placeholder="tu@email.com",
            help="Enviaremos un PDF con la reseña completa",
            key="input_email"
        )



# ============================================================
# TELEGRAM CON TELÉFONO
# ============================================================


enviar_telegram = st.checkbox("🎧 Audio resumen por Telegram (1 min)", key="check_telegram")

telegram_container = st.empty()
telefono_completo = ""

if enviar_telegram:
    with telegram_container.container():
        codigos_pais = get_codigos_pais()
        
        col_pais, col_numero = st.columns([1, 2])
        with col_pais:
            pais_seleccionado = st.selectbox(
                "País",
                list(codigos_pais.keys()),
                index=0,
                help="Selecciona tu código de país",
                key="select_pais"
            )
        
        with col_numero:
            if pais_seleccionado == "🌍 Otro país (ingresar código)":
                codigo_manual = st.text_input(
                    "Código país",
                    placeholder="+1, +44, +86...",
                    help="Ejemplo: +1 (USA), +44 (UK)",
                    key="input_codigo"
                )
                numero = st.text_input(
                    "Número",
                    placeholder="999-888-777",
                    help="Solo el número sin código de país",
                    key="input_numero"
                )
                
                if codigo_manual and numero:
                    numero_limpio = numero.replace("-", "").replace(" ", "")
                    telefono_completo = f"{codigo_manual}{numero_limpio}"
            else:
                numero = st.text_input(
                    "Número",
                    placeholder="999-888-777",
                    help="Solo el número sin código de país",
                    key="input_numero"
                )
                
                if numero:
                    codigo = codigos_pais[pais_seleccionado]
                    numero_limpio = numero.replace("-", "").replace(" ", "")
                    telefono_completo = f"{codigo}{numero_limpio}"


# Botón de envío
submitted = st.button(
    "🚀 OBTENER MI RESEÑA",
    type="primary",
    use_container_width=True
)


# ============================================================
# PROCESAMIENTO Y VALIDACIONES
# ============================================================
if submitted:
    # ========================================
    # VALIDACIÓN 1: Al menos Email O Telegram
    # ========================================
    if not enviar_email and not enviar_telegram:
        st.error(
            "⚠️ **Debes seleccionar al menos una opción adicional:**\n\n"
            "• 📧 Recibir PDF por correo\n\n"
            "• 🎧 Audio resumen por Telegram"
        )
        st.stop()
    
    # ========================================
    # VALIDACIÓN 2: Email (si fue seleccionado)
    # ========================================
    if enviar_email:
        if not email:
            st.error("⚠️ Ingresa tu email")
            st.stop()
        if not validar_email(email):
            st.error("⚠️ Email inválido. Formato correcto: usuario@dominio.com")
            st.stop()
    
    # ========================================
    # PASO 1: OCR - EXTRAER TÍTULO Y AUTOR
    # ========================================
    with st.spinner("📸 Analizando portada con IA..."):
        try:
            client = get_openai_client()
            result_ocr = extract_title_author(client, image_bytes, mime)
            titulo = result_ocr.get("titulo")
            autor = result_ocr.get("autor")
            
            if not titulo:
                st.error("❌ No se pudo detectar el título del libro. Intenta con otra foto.")
                st.stop()
            
            st.success(f"✅ Libro detectado: **{titulo}** - {autor or 'Autor no detectado'}")
            
        except Exception as e:
            logger.error(f"Error en OCR: {str(e)}", exc_info=True)
            st.error("❌ No se pudo analizar la portada. Verifica que la imagen sea clara.")
            if SHOW_DEBUG_ERRORS:
                st.exception(e)
            st.stop()
    
    # ========================================
    # GENERAR CÓDIGO QR PARA TELEGRAM
    # ========================================
    if enviar_telegram:
        # Generar código único
        import secrets
        telegram_code = secrets.token_urlsafe(8)  # Código aleatorio seguro
        logger.info(f"Código Telegram generado: {telegram_code}")
    
    # ========================================
    # PASO 2: LLAMAR N8N PARA BUSCAR RESEÑAS
    # ========================================
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Progress: 20%
        status_text.write("🔍 Buscando reseñas en internet...")
        progress_bar.progress(20)
        time.sleep(1)
        
        # Llamar webhook de n8n
        resultado_n8n = llamar_n8n_webhook(
            titulo=titulo,
            autor=autor,
            email=email if enviar_email else None,
            telegram_code=telegram_code if enviar_telegram else None
        )
        
        # Progress: 60%
        status_text.write("📊 Generando ficha técnica...")
        progress_bar.progress(60)
        time.sleep(2)
        
        # Progress: 90%
        status_text.write("✨ Finalizando...")
        progress_bar.progress(90)
        time.sleep(1)
        
        # Progress: 100%
        progress_bar.progress(100)
        status_text.write("✅ ¡Listo!")
        time.sleep(0.5)
        
        # Limpiar progress bar
        progress_bar.empty()
        status_text.empty()
        
        # ========================================
        # PASO 3: MOSTRAR RESULTADOS
        # ========================================
        
        # Extraer datos de la respuesta
        ficha_data = resultado_n8n.get("body", resultado_n8n)
        
        st.success("🎉 ¡Tu reseña está lista!")
        
        # Mostrar en tabs
        tab1, tab2, tab3 = st.tabs(["📚 Resumen", "📊 Detalles", "🔧 JSON"])
        
        with tab1:
            if "informacion_basica" in ficha_data:
                info = ficha_data["informacion_basica"]
                st.write(f"### {info.get('titulo', titulo)}")
                st.write(f"**Autor:** {info.get('autor', autor)}")
            
            if "clasificacion" in ficha_data:
                clasif = ficha_data["clasificacion"]
                st.write(f"**Género:** {clasif.get('genero_principal', 'N/A')}")
            
            st.divider()
            
            if "contenido" in ficha_data:
                contenido = ficha_data["contenido"]
                st.write("#### 📖 Sinopsis")
                st.write(contenido.get("sinopsis", "No disponible"))
        
        with tab2:
            if "clasificacion" in ficha_data:
                clasif = ficha_data["clasificacion"]
                if "temas_clave" in clasif:
                    st.write("#### 🎯 Temas Clave")
                    for tema in clasif["temas_clave"]:
                        st.write(f"• {tema}")
            
            if "estadisticas" in resultado_n8n:
                st.write("#### 📊 Métricas de Calidad")
                stats_str = resultado_n8n["estadisticas"]
                stats = json.loads(stats_str) if isinstance(stats_str, str) else stats_str
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Confiabilidad", f"{stats.get('confiabilidad', 0)*100:.0f}%")
                col2.metric("Completitud", f"{stats.get('completitud', 0)*100:.0f}%")
                col3.metric("Fuentes", stats.get('numeroFuentes', 0))
        
        with tab3:
            st.json(ficha_data)
        
        # ========================================
        # ENVIAR PDF POR EMAIL
        # ========================================
        if enviar_email:
            try:
                with st.spinner("📄 Generando PDF..."):
                    pdf_bytes = generar_pdf(ficha_data, titulo, autor)
                
                with st.spinner(f"📧 Enviando a {email}..."):
                    enviar_pdf_email(email, pdf_bytes, titulo)
                
                st.success(f"✅ PDF enviado exitosamente a **{email}**")
                st.info("📬 Revisa tu bandeja de entrada (y spam por si acaso)")
                
            except Exception as e:
                logger.error(f"Error al generar/enviar PDF: {str(e)}", exc_info=True)
                st.error(f"❌ No se pudo enviar el PDF. Error: {str(e)}")
                if SHOW_DEBUG_ERRORS:
                    st.exception(e)
        
        # ========================================
        # MOSTRAR QR PARA TELEGRAM
        # ========================================
        if enviar_telegram and telegram_code:
            st.markdown("---")
            st.write("### 🎧 Recibe tu audio en Telegram")
            
            # Generar URL del bot con código
            bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "LibriaBot")
            telegram_url = f"https://t.me/{bot_username}?start={telegram_code}"
            
            # Generar QR usando API externa
            qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={telegram_url}"
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(qr_api_url, caption="Escanea con Telegram")
                st.markdown(
                    f"<div class='qr-container'>"
                    f"<p><strong>O haz clic aquí:</strong></p>"
                    f"<a href='{telegram_url}' target='_blank' style='color: #00D9FF; font-size: 18px;'>"
                    f"Abrir en Telegram 📱</a>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            
            st.info(
                "📱 **Instrucciones:**\n\n"
                "1. Escanea el código QR con tu app de Telegram\n"
                "2. O haz clic en el link si estás en móvil\n"
                "3. El bot te enviará tu audio automáticamente"
            )
        
        # ========================================
        # INCREMENTAR CONTADOR DE USO
        # ========================================
        increment_usage()
        
        logger.info(f"Búsqueda exitosa para: {titulo} - {autor}")
        
    except Exception as e:
        logger.error(f"Error al procesar libro: {str(e)}", exc_info=True)
        
        progress_bar.empty()
        status_text.empty()
        
        st.error(
            "❌ Ocurrió un error al buscar las reseñas. "
            "Por favor intenta nuevamente en unos momentos."
        )
        
        if SHOW_DEBUG_ERRORS:
            st.exception(e)


# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption(
    "🤖 Powered by OpenAI GPT-4o-mini Vision + n8n | "
    "📝 LibrIA v3.1 | "
    f"🐛 Debug: {'ON' if SHOW_DEBUG_ERRORS else 'OFF'}"
)

logger.info("Renderizado completo de la página")