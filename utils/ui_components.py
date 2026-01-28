# ============================================================
# UI MOBILE-FIRST - LIBRIA
# ============================================================
# Estilos CSS optimizados para dispositivos móviles
# y componentes de interfaz de usuario con branding oficial

from pathlib import Path
import base64
import streamlit as st
import re
from string import Template



# ============================================================
# COLORES DE BRANDING LIBRIA
# ============================================================
# Extraídos del logo oficial
COLOR_CYAN = "#00D9FF"          # Azul cyan brillante (circuitos)
COLOR_AZUL_OSCURO = "#003D5C"   # Azul oscuro (borde)
COLOR_VERDE = "#10B981"         # Verde (libro)
COLOR_NEGRO = "#000000"         # Texto principal
COLOR_GRIS = "#666666"          # Texto secundario


# ============================================================
# LOGO PATH (archivo real del proyecto)
# ============================================================
BASE_DIR = Path(__file__).resolve().parents[1]  # raíz del proyecto
LOGO_PATH = BASE_DIR / "assets" / "logo-libria-transparente.png"


# ============================================================
# CSS MOBILE-FIRST CON BRANDING
# ============================================================

def inject_mobile_css():
    """
    Inyecta CSS personalizado optimizado para móviles con branding LibrIA.
    Usa Template ($VAR) para evitar errores con llaves {} del CSS.
    """
    css = Template("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');
        :root {
            --color-cyan: $COLOR_CYAN;
            --color-azul-oscuro: $COLOR_AZUL_OSCURO;
            --color-verde: $COLOR_VERDE;
            --color-negro: $COLOR_NEGRO;
            --color-gris: $COLOR_GRIS;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: var(--color-negro);
        }
                   
        /* ========================================
        FONDO APP (Streamlit)
        ======================================== */
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main {
            background: #F4F8FF; /* azul muy claro, tech */
        }
                   
                  

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Space Grotesk', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-weight: 600;
            color: var(--color-azul-oscuro);
        }

        /* ========================================
        HEADER scoped (PRO, sin !important)
        ======================================== */
            .libria-header-wrap{
            margin: 0 0 10px 0;
            }

            .libria-header-wrap .libria-header{
            display:flex;
            align-items:center;
            justify-content:flex-start;
            gap:16px;
            padding: 10px 0;
            text-align:left;
            }

            .libria-header-wrap .libria-logo{
            width: 92px;
            height: 92px;
            object-fit: contain;
            flex: 0 0 auto;
            margin: 0;
            }

            .libria-header-wrap .libria-header-text{
            line-height: 1.15;
            flex: 1 1 auto;
            min-width: 0; /* evita recortes dentro de flex */
            }

            .libria-header-wrap .libria-brand{
            font-family: 'Space Grotesk', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 28px;
            font-weight: 900;
            color: var(--color-azul-oscuro);
            margin: 0;
            }

            .libria-header-wrap .libria-title{
            font-family: 'Space Grotesk', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 22px;
            font-weight: 800;
            color: var(--color-azul-oscuro);
            margin: 2px 0 0 0;
            }

            .libria-header-wrap .libria-subtitle{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 6px 0 0 0;
            font-style: italic;
            color: var(--color-gris);
            max-width: 70ch;
            }
                   
            /* MOBILE: bajar un poco el texto (mantener layout horizontal) */
            @media (max-width: 767px){
            .libria-header-wrap .libria-header{
                align-items: flex-start;
                padding-top: 18px;   /* ✅ baja TODO el header (logo+texto) */
            }

            .libria-header-wrap .libria-logo{
                margin-top: 4px;     /* ✅ baja un poco el logo */
            }

            .libria-header-wrap .libria-header-text{
                margin-top: 14px;    /* ✅ baja más el texto */
                flex: 1 1 auto;
                min-width: 0;
            }

            .libria-header-wrap .libria-brand{ font-size: 26px; }
            .libria-header-wrap .libria-title{ font-size: 20px; }
            .libria-header-wrap .libria-subtitle{ font-size: 14px; }
            }

            /* TABLET */
            @media (min-width: 768px){
            .libria-header-wrap .libria-logo{ width: 110px; height: 110px; }
            .libria-header-wrap .libria-brand{ font-size: 32px; }
            .libria-header-wrap .libria-title{ font-size: 24px; }
            .libria-header-wrap .libria-subtitle{ font-size: 15px; max-width: 80ch; }
            }

            /* DESKTOP */
            @media (min-width: 1024px){
            .libria-header-wrap .libria-logo{ width: 120px; height: 120px; }
            .libria-header-wrap .libria-brand{ font-size: 34px; }
            .libria-header-wrap .libria-title{ font-size: 26px; }
            .libria-header-wrap .libria-subtitle{ font-size: 16px; }
            }


        /* ========================================
           BOTONES
           ======================================== */
        .stButton > button {
            width: 100%;
            height: 60px;
            font-size: 18px;
            font-weight: 600;
            border-radius: 12px;
            margin: 10px 0;
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }

        .stButton > button:not(:disabled):hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 217, 255, 0.3);
        }
                   
        .stButton > button:disabled{
            opacity: 0.45;
            filter: grayscale(35%);
            cursor: not-allowed;
            box-shadow: none;
            transform: none;
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, $COLOR_CYAN 0%, $COLOR_AZUL_OSCURO 100%);
            border: none;
            color: white;
        }

        .stButton > button[kind="primary"]:hover {
            box-shadow: 0 8px 24px rgba(0, 217, 255, 0.4);
        }

        .stButton > button[kind="secondary"] {
            background: white;
            border: 2px solid $COLOR_CYAN;
            color: $COLOR_AZUL_OSCURO;
        }

        /* ========================================
           INPUTS
           ======================================== */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div > select {
            font-size: 16px !important;
            padding: 14px 12px !important;
            border-radius: 10px !important;
            border: 2px solid #e0e0e0 !important;
            transition: all 0.3s ease !important;
        }

        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus,
        .stSelectbox > div > div > select:focus {
            border-color: $COLOR_CYAN !important;
            box-shadow: 0 0 0 3px rgba(0, 217, 255, 0.1) !important;
        }

        /* ========================================
           FILE UPLOADER
           ======================================== */
        [data-testid="stFileUploader"] {
            border: 2px dashed $COLOR_CYAN;
            border-radius: 12px;
            padding: 20px;
            background: rgba(0, 217, 255, 0.05);
        }

        /* ========================================
           ESPACIADO GLOBAL (quita “amarillo”)
           ======================================== */
        .block-container{
            padding-top: 1rem;
            padding-bottom: 1.5rem;
        }

        @media (min-width: 768px){
            .block-container{
                max-width: 900px;
                padding: 1.5rem 1rem;
            }
        }
                   
        /* ========================================
        FOOTER LIBRIA (centrado + logo)
        ======================================== */
        .libria-footer{
            margin: 18px auto 8px auto;
            padding: 14px 16px;
            border-radius: 16px;
            background: rgba(0, 217, 255, 0.06);
            border: 1px solid rgba(0, 61, 92, 0.10);
            max-width: 900px;
        }

        .libria-footer-inner{
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            gap: 8px;
        }

        .libria-footer-logo{
            width: 44px;
            height: 44px;
            object-fit: contain;
        }

        .libria-footer-title{
            font-family: 'Space Grotesk', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-weight: 800;
            font-size: 14px;
            color: var(--color-azul-oscuro);
            margin: 0;
        }

        .libria-footer-line{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 13px;
            color: rgba(0, 61, 92, 0.78);
            margin: 0;
            line-height: 1.35;
        }

        .libria-footer-sub{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 12px;
            color: rgba(0, 61, 92, 0.60);
            margin: 4px 0 0 0;
            line-height: 1.35;
        }

    </style>
    """).substitute(
        COLOR_CYAN=COLOR_CYAN,
        COLOR_AZUL_OSCURO=COLOR_AZUL_OSCURO,
        COLOR_VERDE=COLOR_VERDE,
        COLOR_NEGRO=COLOR_NEGRO,
        COLOR_GRIS=COLOR_GRIS,
    )

    st.markdown(css, unsafe_allow_html=True)



# ============================================================
# COMPONENTES DE UI
# ============================================================

@st.cache_data(show_spinner=False)
def get_logo_data_url():
    """
    Devuelve un Data URL base64 del logo si existe, o None.
    (Sin tipado 'str | None' para evitar errores en Python < 3.10)
    """
    if not LOGO_PATH.exists():
        return None

    data = LOGO_PATH.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def mostrar_header():
    """
    Header con 3 líneas:
    - LibrIA
    - ¿De qué trata el libro?
    - subtítulo en cursiva
    """
    logo_data_url = get_logo_data_url()

    logo_html = (
        f'<img src="{logo_data_url}" alt="LibrIA Logo" class="libria-logo">'
        if logo_data_url
        else '<div style="font-size:42px; line-height:1;">📚</div>'
    )

    st.markdown(f"""
        <div class="libria-header-wrap">
        <div class="libria-header">
            {logo_html}
            <div class="libria-header-text">
                <div class="libria-brand">LibrIA</div>
                <div class="libria-title">¿De qué trata el libro?</div>
                <div class="libria-subtitle">Descúbrelo fácil y rápido, solo necesitas una foto/imagen de la portada del libro</div>
            </div>
        </div>
        </div>
        """, unsafe_allow_html=True)

def mostrar_footer():
    """
    Footer centrado con logo + 3 líneas de texto.
    """
    logo_data_url = get_logo_data_url()

    logo_html = (
        f'<img src="{logo_data_url}" alt="LibrIA" class="libria-footer-logo">'
        if logo_data_url
        else ""
    )

    st.markdown(f"""
    <div class="libria-footer">
      <div class="libria-footer-inner">
        {logo_html}
        <p class="libria-footer-title">LibrIA – Reseñas Inteligentes</p>
        <p class="libria-footer-line">Desarrollado por Carlos Silva</p>
        <p class="libria-footer-line">Ingeniero en Informática</p>
        
      </div>
    </div>
    """, unsafe_allow_html=True)


def mostrar_cuota(restantes: int):
    """
    Muestra contador de búsquedas restantes.
    """
    if restantes <= 0:
        st.error("❌ Has agotado tus 3 búsquedas gratuitas")
    elif restantes == 1:
        st.warning(f"⚠️ Te queda **{restantes}** búsqueda gratuita")
    else:
        st.info(f"⚡ Te quedan **{restantes}** de 3 búsquedas gratuitas")


def validar_email(email: str) -> bool:
    """
    Valida formato de email.
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validar_telefono(telefono: str) -> bool:
    """
    Valida formato de teléfono internacional.
    """
    pattern = r'^\+\d{10,15}$'
    return re.match(pattern, telefono) is not None


def get_codigos_pais() -> dict:
    """
    Retorna diccionario de códigos de país para Telegram.
    """
    return {
        "🇪🇨 Ecuador": "+593",
        "🇨🇴 Colombia": "+57",
        "🇵🇪 Perú": "+51",
        "🇦🇷 Argentina": "+54",
        "🇲🇽 México": "+52",
        "🇪🇸 España": "+34",
        "🇺🇸 USA": "+1",
        "🌍 Otro país (ingresar código)": "MANUAL"
    }

def get_regiones_pais() -> dict:
    """
    Retorna diccionario label -> ISO region (para phonenumbers).
    Nota: "MANUAL" significa que el usuario ingresará el número con +código.
    """
    return {
        "🇪🇨 Ecuador": "EC",
        "🇨🇴 Colombia": "CO",
        "🇵🇪 Perú": "PE",
        "🇦🇷 Argentina": "AR",
        "🇲🇽 México": "MX",
        "🇺🇸 USA": "US",
        "🇨🇦 Canadá": "CA",
        "🇨🇱 Chile": "CL",
        "🇧🇷 Brasil": "BR",
        "🇺🇾 Uruguay": "UY",
        "🇵🇾 Paraguay": "PY",
        "🇧🇴 Bolivia": "BO",
        "🇻🇪 Venezuela": "VE",
        "🇨🇷 Costa Rica": "CR",
        "🇵🇦 Panamá": "PA",
        "🇬🇹 Guatemala": "GT",
        "🇭🇳 Honduras": "HN",
        "🇸🇻 El Salvador": "SV",
        "🇳🇮 Nicaragua": "NI",
        "🇩🇴 Rep. Dominicana": "DO",
        "🇪🇸 España": "ES",
        "🌍 Otro país (ingresar código)": "MANUAL"
    }


def mostrar_progreso_con_mensajes(progreso: int, mensaje: str):
    """
    Muestra barra de progreso con mensaje.
    """
    st.progress(progreso / 100)
    st.write(mensaje)
