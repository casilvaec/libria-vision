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
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException

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
    mostrar_footer,
    get_codigos_pais,
    get_regiones_pais
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


def llamar_n8n_webhook(
    titulo: str,
    autor: str,
    email: str = None,
    
    telegram_code: str = None
) -> dict:
    """
    Llama al webhook de n8n para buscar reseñas.
    
    Args:
        titulo: Título del libro (Obligatorio)
        autor: Autor del libro (opcional)
        email: Email del usuario (opcional, pero DEBE estar email O telegram_code)
        telegram_code: Código challenge de Telegram (opcional, pero DEBE estar email O telegram_code)
        
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
            # E.164, solo si eligió Telegram
        "telegram_code": telegram_code,    # código start del bot
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
# FUNCIONES TELEGRAM CHALLENGE
# ============================================================

def generar_challenge() -> str:
    """
    Genera código aleatorio de 8 caracteres para validación de Telegram.
    
    Returns:
        str: Código único (ej: "AB12CD34")
    """
    import secrets
    return secrets.token_urlsafe(8)[:8].upper()


def calcular_firma_esperada(codigo: str) -> str:
    """
    Calcula firma HMAC esperada del código usando la clave secreta compartida.
    
    Args:
        codigo: Código challenge generado
        
    Returns:
        str: Firma HMAC en formato hexadecimal (8 caracteres)
    """
    import hmac
    import hashlib
    
    secret_key = os.getenv("TELEGRAM_SECRET_KEY", "libria_secret_key_2025_segura")
    
    firma = hmac.new(
        secret_key.encode(),
        codigo.encode(),
        hashlib.sha256
    ).hexdigest()[:8]
    
    return firma.upper()


def validar_firma(codigo: str, firma_usuario: str) -> bool:
    """
    Valida que la firma ingresada por el usuario sea correcta.
    
    Args:
        codigo: Código challenge original
        firma_usuario: Firma que ingresó el usuario desde el bot
        
    Returns:
        bool: True si la firma es válida
    """
    if not firma_usuario:
        return False
    
    firma_esperada = calcular_firma_esperada(codigo)
    return firma_usuario.upper().strip() == firma_esperada

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

# --- Exclusividad: si marca Email, desmarca Telegram; y viceversa ---
def _toggle_email():
    if st.session_state.get("check_email"):
        st.session_state["check_telegram"] = False

def _toggle_telegram():
    if st.session_state.get("check_telegram"):
        st.session_state["check_email"] = False
        # si quieres también limpiar email al pasar a telegram:
        st.session_state["input_email"] = ""
        st.session_state["email_valido"] = False
        st.session_state["email_error"] = ""

# Email opcional - CON CAMPO CONDICIONAL REACTIVO (VALIDACIÓN EN VIVO)
enviar_email = st.checkbox(
    "📄 Recibir PDF por correo",
    key="check_email",
    on_change=_toggle_email,
    disabled=st.session_state.get("check_telegram", False)
)

# --- Estado inicial (solo la 1era vez) ---
if "email_valido" not in st.session_state:
    st.session_state.email_valido = False
if "email_error" not in st.session_state:
    st.session_state.email_error = ""

# --- Callback: se ejecuta cada vez que cambia el input ---
def _validar_email_en_vivo():
    val = (st.session_state.get("input_email") or "").strip()

    if not val:
        st.session_state.email_valido = False
        st.session_state.email_error = "⚠️ Ingresa tu email"
        return

    if not validar_email(val):
        st.session_state.email_valido = False
        st.session_state.email_error = "⚠️ Email inválido. Formato correcto: usuario@dominio.com"
        return

    st.session_state.email_valido = True
    st.session_state.email_error = ""

# Contenedor reactivo para email
email_container = st.empty()
email = ""

if enviar_email:
    with email_container.container():
        email = st.text_input(
            "Tu email",
            placeholder="tu@email.com",
            help="Enviaremos un PDF con la reseña completa",
            key="input_email",
            on_change=_validar_email_en_vivo
        )

        # Mostrar feedback inmediato (UX)
        if st.session_state.email_error:
            st.error(st.session_state.email_error)
        
else:
    # Si desmarcan el checkbox, limpias estado (evita que quede “válido” guardado)
    st.session_state.email_valido = False
    st.session_state.email_error = ""

# ============================================================
# TELEGRAM CON TELÉFONO (VALIDACIÓN REAL CON PHONENUMBERS)
# ============================================================

# enviar_telegram = st.checkbox(
#     "🎧 Audio resumen por Telegram (1 min)",
#     key="check_telegram",
#     on_change=_toggle_telegram,
#     disabled=st.session_state.get("check_email", False)
# )

# telegram_container = st.empty()
# telefono_completo = ""

# # --- Estado inicial (solo 1era vez) ---
# if "tel_valido" not in st.session_state:
#     st.session_state.tel_valido = False
# if "tel_error" not in st.session_state:
#     st.session_state.tel_error = ""
# if "tel_e164" not in st.session_state:
#     st.session_state.tel_e164 = ""

# regiones_pais = get_regiones_pais()

# def _validar_tel_en_vivo():
#     pais = st.session_state.get("select_pais")
#     numero = (st.session_state.get("input_numero") or "").strip()

#     if not numero:
#         st.session_state.tel_valido = False
#         st.session_state.tel_error = "⚠️ Ingresa tu número"
#         st.session_state.tel_e164 = ""
#         return

#     region = regiones_pais.get(pais, "")

#     try:
#         # Si es MANUAL, el usuario debe escribir con +código
#         if region == "MANUAL":
#             if not numero.startswith("+"):
#                 st.session_state.tel_valido = False
#                 st.session_state.tel_error = "⚠️ Para 'Otro país', escribe el número con +código. Ej: +34 600123123"
#                 st.session_state.tel_e164 = ""
#                 return
#             p = phonenumbers.parse(numero, None)
#         else:
#             p = phonenumbers.parse(numero, region)

#         if not phonenumbers.is_valid_number(p):
#             st.session_state.tel_valido = False
#             st.session_state.tel_error = "⚠️ Número inválido para el país seleccionado"
#             st.session_state.tel_e164 = ""
#             return

#         st.session_state.tel_valido = True
#         st.session_state.tel_error = ""
#         st.session_state.tel_e164 = phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)

#     except NumberParseException:
#         st.session_state.tel_valido = False
#         st.session_state.tel_error = "⚠️ Número inválido. Revisa el formato."
#         st.session_state.tel_e164 = ""

# if enviar_telegram:
#     with telegram_container.container():

#         col_pais, col_numero = st.columns([1, 2])

#         with col_pais:
#             st.selectbox(
#                 "País",
#                 list(regiones_pais.keys()),
#                 index=0,
#                 help="Selecciona tu país (validaremos el número automáticamente)",
#                 key="select_pais",
#                 on_change=_validar_tel_en_vivo
#             )

#         with col_numero:
#             st.text_input(
#                 "Número",
#                 placeholder="Ej: 0999888777 (o +34 600123123 si es 'Otro país')",
#                 help="Puedes escribir con espacios o guiones, lo ajustamos automáticamente",
#                 key="input_numero",
#                 on_change=_validar_tel_en_vivo
#             )

#         # 2) Mostrar error inmediato (si existe)
#         if st.session_state.tel_error:
#             st.error(st.session_state.tel_error)

#         # 3) Solo si el teléfono es válido, muestro instrucciones + link
#         if st.session_state.tel_valido:
#             st.info(
#                 "Para recibir tu audio, primero activa nuestro bot:\n\n"
#                 "1. Abre Telegram en tu teléfono\n"
#                 "2. Busca: **@LibriaBot** o da click en el link de **\"Abrir el bot ahora\"**\n"
#                 "3. Presiona **START**\n"
#                 "4. Regresa aquí\n\n"
#                 "✅ Solo necesitas hacer esto una vez."
#             )

#             bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "LibriaBot")
#             bot_url = f"https://t.me/{bot_username}"

#             st.markdown(f"👉 **Abrir el bot ahora:** {bot_url}")

#             telefono_completo = st.session_state.tel_e164
# else:
#     # Si se desmarca, limpia estado para no dejar válido “guardado”
#     st.session_state.tel_valido = False
#     st.session_state.tel_error = ""
#     st.session_state.tel_e164 = ""


# ============================================================
# TELEGRAM CON CHALLENGE (SIN TELÉFONO)
# ============================================================

enviar_telegram = st.checkbox(
    "🎧 Audio resumen por Telegram (1 min aprox.)",
    key="check_telegram",
    on_change=_toggle_telegram,
    disabled=st.session_state.get("check_email", False)
)

# Estado inicial para challenge
if "telegram_challenge" not in st.session_state:
    st.session_state.telegram_challenge = None
if "telegram_firma_valida" not in st.session_state:
    st.session_state.telegram_firma_valida = False
if "telegram_error" not in st.session_state:
    st.session_state.telegram_error = ""

telegram_code = ""

if enviar_telegram:
    # Generar challenge una sola vez
    if st.session_state.telegram_challenge is None:
        st.session_state.telegram_challenge = generar_challenge()
    
    codigo_challenge = st.session_state.telegram_challenge
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "libria_resenas_bot")
    
    # Mostrar instrucciones
    st.info(
        f"📱 **Para recibir tu audio:**\n\n"
        f"1. Abre Telegram\n"
        f"2. Busca: **@{bot_username}**\n"
        f"3. Envía este mensaje:\n\n"
        f"`/start {codigo_challenge}`\n\n"
        f"4. El bot te responderá con un código\n"
        f"5. Pega ese código aquí abajo ⬇️"
    )
    
    # Link directo al bot
    bot_url = f"https://t.me/{bot_username}?start={codigo_challenge}"
    st.markdown(f"👉 [Abrir bot ahora]({bot_url})")
    
    # Callback para validar firma
    def _validar_firma_telegram():
        firma = (st.session_state.get("input_firma_telegram") or "").strip()
        
        if not firma:
            st.session_state.telegram_firma_valida = False
            st.session_state.telegram_error = ""
            return
        
        if validar_firma(codigo_challenge, firma):
            st.session_state.telegram_firma_valida = True
            st.session_state.telegram_error = ""
            # Guardar el código validado
            telegram_code = codigo_challenge
        else:
            st.session_state.telegram_firma_valida = False
            st.session_state.telegram_error = "❌ Código incorrecto. Verifica que copiaste bien el código que te dio el bot."
    
    # Input para la firma
    st.text_input(
        "Código de verificación del bot",
        placeholder="ABC12345",
        help="Pega aquí el código que te dio el bot en Telegram",
        key="input_firma_telegram",
        on_change=_validar_firma_telegram
    )
    
    # Mostrar error o éxito
    if st.session_state.telegram_error:
        st.error(st.session_state.telegram_error)
    
    if st.session_state.telegram_firma_valida:
        st.success("✅ Bot activado correctamente. Ya puedes obtener tu reseña.")
        telegram_code = codigo_challenge

else:
    # Si desmarca, limpia estado
    st.session_state.telegram_challenge = None
    st.session_state.telegram_firma_valida = False
    st.session_state.telegram_error = ""

# Reglas para habilitar el botón:
# - Debe escoger SOLO una opción: email XOR telegram
# - Si escogió email: email válido
# - Si escogió telegram: firma validada
elige_una = (enviar_email ^ enviar_telegram)

email_ok = enviar_email and bool(st.session_state.email_valido)
telegram_ok = enviar_telegram and bool(st.session_state.telegram_firma_valida)

puede_enviar = elige_una and (email_ok or telegram_ok)




submitted = st.button(
    "🚀 OBTENER MI RESEÑA",
    type="primary",
    use_container_width=True,
    disabled=not puede_enviar
)

if not (enviar_email or enviar_telegram):
    st.info("Selecciona **una** opción: correo **o** Telegram, para habilitar el botón.")
elif enviar_email and not st.session_state.email_valido:
    st.info("Ingresa un email válido para habilitar el botón.")
elif enviar_telegram and not st.session_state.telegram_firma_valida:
    st.info("Completa la validación del bot de Telegram para habilitar el botón.")

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
    # PREPARAR CÓDIGO TELEGRAM 
    # ========================================
    ''' 
    if enviar_telegram:
        # Generar código único
        import secrets
        telegram_code = secrets.token_urlsafe(8)  # Código aleatorio seguro
        logger.info(f"Código Telegram generado: {telegram_code}")
    '''
    # ========================================
    # PREPARAR CÓDIGO TELEGRAM (ya validado)
    # ========================================
    telegram_code_final = None
    if enviar_telegram and st.session_state.telegram_firma_valida:
        telegram_code_final = st.session_state.telegram_challenge
        logger.info(f"Código Telegram validado: {telegram_code_final}")


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
            telegram_code=telegram_code_final
            
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
        # CONFIRMACIÓN TELEGRAM
        # ========================================
        if enviar_telegram:
            st.success("🎧 Tu audio se está generando y llegará a Telegram en breve")
            st.info(
                "📱 **El audio llegará automáticamente**\n\n"
                "Revisa tu conversación con el bot en Telegram.\n"
                "Puede tardar 10-30 segundos en llegar."
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
mostrar_footer()

st.markdown("""
<div style="
    background:#e8f4ff;
    border-radius:10px;
    padding:12px;
    text-align:center;
    font-size:14px;
">
 LibrIA utiliza IA y puede cometer errores. Verifica el contenido generado.
</div>
""", unsafe_allow_html=True)


logger.info("Renderizado completo de la página")