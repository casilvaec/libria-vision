# ============================================================
# UI MOBILE-FIRST - LIBRIA
# ============================================================
# Estilos CSS optimizados para dispositivos móviles
# y componentes de interfaz de usuario

import streamlit as st


# ============================================================
# CSS MOBILE-FIRST
# ============================================================

def inject_mobile_css():
    """
    Inyecta CSS personalizado optimizado para móviles.
    
    Características:
    - Botones grandes y táctiles (60px altura mínima)
    - Inputs de formulario más grandes
    - Espaciado cómodo para dedos
    - Tipografía legible en pantallas pequeñas
    - Diseño responsive que se adapta al tamaño
    """
    st.markdown("""
    <style>
        /* ========================================
           BOTONES - Mobile Friendly
           ======================================== */
        .stButton > button {
            width: 100%;
            height: 60px;
            font-size: 18px;
            font-weight: 600;
            border-radius: 12px;
            margin: 10px 0;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        /* Botón primario más destacado */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
        }
        
        /* ========================================
           INPUTS - Más grandes para móvil
           ======================================== */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            font-size: 16px !important;
            padding: 12px !important;
            border-radius: 8px !important;
        }
        
        /* ========================================
           FILE UPLOADER - Área táctil grande
           ======================================== */
        .uploadedFile {
            border-radius: 12px;
        }
        
        /* ========================================
           CHECKBOXES - Más grandes y espaciados
           ======================================== */
        .stCheckbox {
            padding: 8px 0;
        }
        
        .stCheckbox > label {
            font-size: 16px;
        }
        
        /* ========================================
           CARDS Y CONTENEDORES
           ======================================== */
        .stExpander {
            border-radius: 12px;
            border: 1px solid #e0e0e0;
        }
        
        /* ========================================
           ALERTAS Y BANNERS
           ======================================== */
        .stAlert {
            border-radius: 12px;
            padding: 16px;
            margin: 12px 0;
        }
        
        /* ========================================
           PROGRESS BAR
           ======================================== */
        .stProgress > div > div > div {
            border-radius: 10px;
            height: 12px;
        }
        
        /* ========================================
           RESPONSIVE - Ajustes para tablets y desktop
           ======================================== */
        @media (min-width: 768px) {
            .stButton > button {
                max-width: 500px;
                margin: 10px auto;
            }
        }
        
        /* ========================================
           ESPACIADO GENERAL
           ======================================== */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        /* ========================================
           TABS - Mejor legibilidad
           ======================================== */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            padding: 12px 20px;
            font-size: 16px;
        }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# PROGRESS BAR CON MENSAJES
# ============================================================

def mostrar_progreso_con_mensajes(mensajes: list):
    """
    Muestra un progress bar animado con mensajes dinámicos.
    
    Args:
        mensajes: Lista de tuplas (porcentaje, mensaje, tiempo_segundos)
        
    Example:
        >>> mensajes = [
        >>>     (20, "📸 Analizando portada...", 3),
        >>>     (60, "🔍 Buscando reseñas...", 30),
        >>>     (100, "✅ ¡Listo!", 2)
        >>> ]
        >>> mostrar_progreso_con_mensajes(mensajes)
    """
    import time
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for porcentaje, mensaje, segundos in mensajes:
        progress_bar.progress(porcentaje)
        status_text.write(mensaje)
        time.sleep(segundos)
    
    # Limpiar al final
    progress_bar.empty()
    status_text.empty()


# ============================================================
# VALIDACIÓN DE EMAIL
# ============================================================

def validar_email(email: str) -> bool:
    """
    Valida formato básico de email.
    
    Args:
        email: String del email a validar
        
    Returns:
        bool: True si el formato es válido
        
    Example:
        >>> validar_email("usuario@example.com")
        True
        >>> validar_email("email-invalido")
        False
    """
    import re
    
    # Patrón regex básico para email
    # No es perfecto pero suficiente para validación básica
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    return bool(re.match(patron, email))


# ============================================================
# VALIDACIÓN DE TELÉFONO
# ============================================================

def validar_telefono(telefono: str) -> bool:
    """
    Valida formato básico de número de teléfono.
    
    Acepta formatos:
    - +593999888777
    - +593-999-888-777
    - +593 999 888 777
    
    Args:
        telefono: String del teléfono a validar
        
    Returns:
        bool: True si el formato es válido
    """
    import re
    
    # Remover espacios, guiones y paréntesis
    telefono_limpio = re.sub(r'[\s\-\(\)]', '', telefono)
    
    # Debe empezar con + y tener entre 10 y 15 dígitos
    patron = r'^\+\d{10,15}$'
    
    return bool(re.match(patron, telefono_limpio))


# ============================================================
# SELECTOR DE CÓDIGO DE PAÍS
# ============================================================

def get_codigos_pais() -> dict:
    """
    Retorna diccionario de códigos de país para Telegram.
    
    Incluye todos los países de América + España + opción manual.
    
    Returns:
        dict: {nombre_pais: codigo}
    """
    return {
        "🇪🇨 Ecuador": "+593",
        "🇨🇴 Colombia": "+57",
        "🇵🇪 Perú": "+51",
        "🇲🇽 México": "+52",
        "🇦🇷 Argentina": "+54",
        "🇨🇱 Chile": "+56",
        "🇪🇸 España": "+34",
        "🇺🇸 Estados Unidos": "+1",
        "🇻🇪 Venezuela": "+58",
        "🇺🇾 Uruguay": "+598",
        "🇵🇾 Paraguay": "+595",
        "🇧🇴 Bolivia": "+591",
        "🇬🇹 Guatemala": "+502",
        "🇭🇳 Honduras": "+504",
        "🇸🇻 El Salvador": "+503",
        "🇨🇷 Costa Rica": "+506",
        "🇵🇦 Panamá": "+507",
        "🇳🇮 Nicaragua": "+505",
        "🇨🇺 Cuba": "+53",
        "🇩🇴 Rep. Dominicana": "+1-809",
        "🌍 Otro país (ingresar código)": "manual"
    }


# ============================================================
# HEADER MEJORADO
# ============================================================

def mostrar_header():
    """
    Muestra header mejorado con título y descripción.
    """
    st.title("📚 Libria - ¿De qué trata el libro?")
    st.markdown("*Descúbrelo fácil y rápido, solo necesitas una foto/imagen de la portada del libro*")
    
    # Instrucciones colapsables
    with st.expander("📖 ¿Cómo funciona?", expanded=False):
        st.markdown("""
        **Paso 1:** 📸 Toma una foto o sube una imagen de la portada del libro
        
        **Paso 2:** 📬 Elige cómo quieres recibir tu reseña:
        - 👀 Visualizar en pantalla (siempre incluido)
        - 📧 PDF por correo (opcional)
        - 🎧 Audio resumen por Telegram (opcional)
        
        **Paso 3:** ✅ ¡Listo! En segundos tendrás tu reseña completa
        
        ---
        
        **💡 Tips para mejores resultados:**
        - Foto frontal y centrada de la portada
        - Buena iluminación sin reflejos
        - Texto del título y autor legible
        """)