# ============================================================
# RATE LIMITING - LIBRIA
# ============================================================
# Sistema de control de uso para limitar búsquedas por dispositivo
# Usa device fingerprinting + localStorage para identificar usuarios únicos

import os
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# DEVICE FINGERPRINTING
# ============================================================

def get_device_fingerprint() -> str:
    """
    Genera un fingerprint único del dispositivo del usuario.
            
    Note:
        No es 100% infalible,
        pero es suficiente para una demo y prevenir uso casual excesivo.
    """
    # JavaScript que genera el fingerprint y lo persiste en localStorage
    fingerprint_component = """
    <script>
        // Función para generar fingerprint del dispositivo
        function getDeviceFingerprint() {
            // Recopila características únicas del navegador
            const data = {
                userAgent: navigator.userAgent,           // Info del navegador y OS
                screen: screen.width + 'x' + screen.height,  // Resolución pantalla
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,  // Zona horaria
                language: navigator.language              // Idioma del navegador
            };
            
            // Convierte el objeto a string para generar hash
            const str = JSON.stringify(data);
            
            // Genera hash simple (algoritmo djb2)
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                hash = ((hash << 5) - hash) + str.charCodeAt(i);
                hash = hash & hash; // Convierte a 32-bit integer
            }
            
            // Retorna hash en base 36 (números + letras)
            return Math.abs(hash).toString(36);
        }
        
        // Obtener o crear fingerprint
        let deviceId = localStorage.getItem('libria_device_id');
        
        if (!deviceId) {
            // Primera vez: generar y guardar
            deviceId = getDeviceFingerprint();
            localStorage.setItem('libria_device_id', deviceId);
        }
        
        // Comunicar el device_id a Streamlit
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: deviceId
        }, '*');
    </script>
    """
    
    # Renderiza el componente JavaScript (invisible, height=0)
    device_id = components.html(fingerprint_component, height=0)
    
    # Fallback: Si no se pudo obtener, generar uno temporal
    if not device_id:
        device_id = "temp_device"
    
    return device_id


# ============================================================
# VERIFICACIÓN DE CUOTA
# ============================================================

def check_rate_limit(device_id: str) -> tuple[bool, int | str]:
    """
    Verifica si el dispositivo puede hacer más búsquedas.
    
    Lógica:
    1. Si tiene token de evaluador en URL → límite evaluador (ej: 50)
    2. Si no → límite normal (ej: 3)
    """
    # Verificar si tiene token de evaluador en la URL
    # Ejemplo: https://libria.app?token=EVAL2024
    query_params = st.query_params
    token = query_params.get("token", "")
    eval_token = os.getenv("EVAL_TOKEN", "")

    # ✅ FIX: token puede venir como lista ["..."], lo normalizamos a string
    if isinstance(token, list):
        token = token[0]
    
    # ✅ Elegir el límite según modo
    if token and token == eval_token:
        max_limit = int(os.getenv("EVAL_LIMIT_MAX", "50"))   # evaluadores
    else:
        max_limit = int(os.getenv("RATE_LIMIT_MAX", "3"))    # público
    
    # Usuario normal / evaluador: Verificar cuota en session_state
    # Inicializar contador si es primera vez
    if 'usage_count' not in st.session_state:
        st.session_state.usage_count = 0
    
    
    # Calcular búsquedas restantes
    restantes = max_limit - st.session_state.usage_count
    puede_buscar = restantes > 0
    
    return (puede_buscar, restantes)


# ============================================================
# INCREMENTAR CONTADOR
# ============================================================

def increment_usage():
    """
    Incrementa el contador de búsquedas usadas.
    
    Se debe llamar DESPUÉS de una búsqueda exitosa.
    Usa st.session_state para persistir durante la sesión del usuario.
    """
    if 'usage_count' not in st.session_state:
        st.session_state.usage_count = 0
    
    st.session_state.usage_count += 1


# ============================================================
# UI - MOSTRAR CUOTA
# ============================================================

def mostrar_cuota(restantes: int | str):
    """
    Muestra banner visual con búsquedas restantes.
    
    - Evaluadores: Banner informativo con límite evaluador
    - Usuarios normales: Banner según límite normal
    
    
    """
    # Detectar si es evaluador (para mostrar el máximo correcto)
    query_params = st.query_params
    token = query_params.get("token", "")
    eval_token = os.getenv("EVAL_TOKEN", "")

    # ✅ FIX: token puede venir como lista ["..."], lo normalizamos a string
    if isinstance(token, list):
        token = token[0]

    if token and token == eval_token:
        max_limit = int(os.getenv("EVAL_LIMIT_MAX", "50"))
    
        if restantes <= 0:
            st.error(f"❌ **Has alcanzado tu límite de {max_limit} búsquedas (Evaluador)**")
        elif restantes == 1:
            st.warning(f"⚠️ **Última búsqueda disponible** ({restantes} de {max_limit})")
        else:
            st.info(f"🎓 **Modo Evaluador**: te quedan **{restantes} de {max_limit}** consultas")
        return
    
    # Usuario normal
    max_limit = int(os.getenv("RATE_LIMIT_MAX", "3"))
    if restantes <= 0:
        st.error(f"❌ **Has alcanzado tu límite de {max_limit} búsquedas gratuitas**")
    elif restantes == 1:
        st.warning(f"⚠️ **Última búsqueda disponible** ({restantes} de {max_limit})")
    else:
        st.info(f"⚡ Te quedan **{restantes} de {max_limit}** búsquedas gratuitas")