# ============================================================
# PDF GENERATOR - LIBRIA
# ============================================================
# Genera PDFs profesionales con la ficha técnica del libro
# Incluye branding, logo y formato de 2 páginas

import os
import textwrap
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ============================================================
# COLORES DE BRANDING LIBRIA
# ============================================================
# Extraídos del logo oficial
COLOR_CYAN = "#00D9FF"       # Azul cyan brillante (circuitos)
COLOR_AZUL_OSCURO = "#003D5C"  # Azul oscuro (borde)
COLOR_VERDE = "#10B981"      # Verde (libro)
COLOR_NEGRO = "#000000"      # Texto principal
COLOR_GRIS = "#666666"       # Texto secundario


# ============================================================
# UTILIDADES DE COLOR
# ============================================================

def hex_to_rgb(hex_color: str) -> tuple:
    """
    Convierte color hexadecimal a RGB (0-1).
    
    Args:
        hex_color: Color en formato "#RRGGBB"
        
    Returns:
        tuple: (r, g, b) con valores entre 0 y 1
    """
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (r/255, g/255, b/255)


# ============================================================
# FUNCIÓN PRINCIPAL DE GENERACIÓN
# ============================================================

def generar_pdf(ficha_data: dict, titulo: str = None, autor: str = None) -> bytes:
    """
    Genera PDF profesional con la reseña del libro.
    
    Características:
    - 2 páginas: Portada + Contenido
    - Logo en header de ambas páginas
    - Footer con créditos solo en última página
    - Colores del branding LibrIA
    - Sin métricas técnicas (solo contenido para usuario)
    
    Args:
        ficha_data: JSON con datos del libro desde n8n
        titulo: Título override (opcional)
        autor: Autor override (opcional)
        
    Returns:
        bytes: PDF generado en memoria
    """
    # Buffer para generar PDF en memoria
    buffer = BytesIO()
    
    # Crear canvas (página tamaño carta)
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter  # 8.5 x 11 inches
    
    # Extraer información de la ficha
    info_basica = ficha_data.get("informacion_basica", {})
    clasificacion = ficha_data.get("clasificacion", {})
    contenido = ficha_data.get("contenido", {})
    resenas = ficha_data.get("reseñas", {})
    audiencia = ficha_data.get("audiencia", {})
    contexto = ficha_data.get("contexto_publicacion", {})
    
    # Datos principales
    libro_titulo = titulo or info_basica.get("titulo", "Título no disponible")
    libro_subtitulo = info_basica.get("subtitulo")
    libro_autor = autor or info_basica.get("autor", "Autor no disponible")
    
    # GÉNERO: Combinar hasta 5 elementos
    generos_lista = []
    if clasificacion.get("genero_principal"):
        generos_lista.append(clasificacion["genero_principal"])
    generos_lista.extend(clasificacion.get("generos_secundarios", [])[:2])
    generos_lista.extend(clasificacion.get("categorias", [])[:2])
    genero_texto = ", ".join(generos_lista[:5]) if generos_lista else "No especificado"
    
    # TEMAS/CONCEPTOS CLAVE: Combinar hasta 8 elementos
    conceptos_lista = []
    conceptos_lista.extend(clasificacion.get("temas_clave", []))
    conceptos_lista.extend(clasificacion.get("palabras_clave", []))
    if clasificacion.get("tono_general"):
        # Dividir tono_general por "y" o comas
        tono = clasificacion["tono_general"]
        tono_parts = tono.replace(" y ", ", ").split(", ")
        conceptos_lista.extend(tono_parts)
    
    # Construir texto de conceptos
    conceptos_texto = ", ".join(conceptos_lista[:8]) if conceptos_lista else ""
    
    # Agregar mensaje_principal al final (si existe)
    mensaje_principal = contenido.get("mensaje_principal")
    if conceptos_texto and mensaje_principal:
        conceptos_texto = f"{conceptos_texto}. {mensaje_principal}"
    elif mensaje_principal and not conceptos_texto:
        # Si no hay conceptos pero sí mensaje, usar solo el mensaje
        conceptos_texto = mensaje_principal
    
    # SINOPSIS: Usar sinopsis o sinopsis_breve
    sinopsis = contenido.get("sinopsis") or contenido.get("sinopsis_breve", "No disponible")
    
    # RESEÑAS: Hasta 5 extractos
    extractos = resenas.get("extractos_destacados", [])[:5]
    
    # AUDIENCIA: Combinar publico_objetivo + recomendado_para
    audiencia_lista = []
    audiencia_lista.extend(audiencia.get("publico_objetivo", []))
    audiencia_lista.extend(audiencia.get("recomendado_para", []))
    audiencia_texto = ", ".join(set(audiencia_lista[:6])) if audiencia_lista else "No especificado"
    
    # RECONOCIMIENTOS: Construir lista de checkmarks basado en datos disponibles
    reconocimientos_lista = []
    
    # Verificar premios
    premios = ficha_data.get("reconocimientos", {}).get("premios", [])
    if premios and len(premios) > 0:
        reconocimientos_lista.append("✓ Premiado")
    
    # Verificar adaptaciones
    adaptaciones = ficha_data.get("reconocimientos", {}).get("adaptaciones", [])
    if adaptaciones and len(adaptaciones) > 0:
        reconocimientos_lista.append("✓ Adaptación a película/serie")
    
    # Verificar popularidad online
    popularidad = contexto.get("popularidad_online", "").lower()
    if popularidad in ["alta", "media"]:
        reconocimientos_lista.append("✓ Popular en redes sociales")
    
    # Verificar menciones en medios
    mencion_medios = ficha_data.get("reconocimientos", {}).get("mencion_medios", [])
    if mencion_medios and len(mencion_medios) > 0:
        reconocimientos_lista.append("✓ Mencionado en medios")
    
    # Verificar si es parte de serie
    serie = contexto.get("serie")
    if serie:
        reconocimientos_lista.append("✓ Forma parte de una serie")
    
    # ADVERTENCIAS: Solo advertencias_contenido (NO origen)
    advertencias = audiencia.get("advertencias_contenido", [])
    
    # ========================================
    # PÁGINA 1 - PORTADA
    # ========================================
    
    # Header con logo
    dibujar_header(pdf, width, height)
    
    # Título principal
    y_position = height - 2.2 * inch
    
    pdf.setFillColorRGB(*hex_to_rgb(COLOR_CYAN))
    pdf.setFont("Helvetica-Bold", 32)
    
    # Wrap título si es muy largo
    titulo_lines = textwrap.wrap(libro_titulo, width=30)
    for line in titulo_lines[:3]:  # Max 3 líneas
        pdf.drawCentredString(width / 2, y_position, line)
        y_position -= 38
    
    # Subtítulo (si existe)
    if libro_subtitulo:
        y_position -= 0.1 * inch
        pdf.setFont("Helvetica", 18)
        subtitulo_lines = textwrap.wrap(libro_subtitulo, width=40)
        for line in subtitulo_lines[:2]:
            pdf.drawCentredString(width / 2, y_position, line)
            y_position -= 22
    
    # Autor
    y_position -= 0.3 * inch
    pdf.setFillColorRGB(*hex_to_rgb(COLOR_AZUL_OSCURO))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(width / 2, y_position, libro_autor)
    
    # Línea decorativa
    y_position -= 0.5 * inch
    pdf.setStrokeColorRGB(*hex_to_rgb(COLOR_CYAN))
    pdf.setLineWidth(1)
    pdf.line(1.5 * inch, y_position, width - 1.5 * inch, y_position)
    
    # Género
    y_position -= 0.4 * inch
    pdf.setFillColorRGB(*hex_to_rgb(COLOR_VERDE))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(0.75 * inch, y_position, "Género:")
    
    pdf.setFillColorRGB(*hex_to_rgb(COLOR_NEGRO))
    pdf.setFont("Helvetica", 12)
    # Wrap género si es muy largo
    genero_lines = textwrap.wrap(genero_texto, width=65)
    for line in genero_lines[:2]:
        y_position -= 16
        pdf.drawString(0.75 * inch, y_position, line)
    
    # Conceptos clave (si hay)
    if conceptos_texto:
        y_position -= 0.4 * inch
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_CYAN))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(0.75 * inch, y_position, "🎯 Conceptos clave:")
        
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_GRIS))
        pdf.setFont("Helvetica", 11)
        # Wrap conceptos en múltiples líneas si es necesario
        conceptos_lines = textwrap.wrap(conceptos_texto, width=70)
        for line in conceptos_lines[:4]:  # Max 4 líneas
            y_position -= 15
            pdf.drawString(0.75 * inch, y_position, line)
    
    # Reconocimientos (si hay)
    if reconocimientos_lista:
        y_position -= 0.4 * inch
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_VERDE))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(0.75 * inch, y_position, "🏆 Reconocimientos:")
        
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_NEGRO))
        pdf.setFont("Helvetica", 11)
        for reconocimiento in reconocimientos_lista[:5]:  # Max 5
            y_position -= 15
            pdf.drawString(0.75 * inch, y_position, reconocimiento)
    
    # Finalizar página 1
    pdf.showPage()
    
    # ========================================
    # PÁGINA 2 - CONTENIDO
    # ========================================
    
    # Header con logo
    dibujar_header(pdf, width, height)
    
    y_position = height - 1.8 * inch
    margin_left = 0.75 * inch
    margin_right = width - 0.75 * inch
    
    # ─────────────────────────────────────
    # SECCIÓN: DE QUÉ TRATA ESTE LIBRO
    # ─────────────────────────────────────
    pdf.setFillColorRGB(*hex_to_rgb(COLOR_CYAN))
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(margin_left, y_position, "📖 De qué trata este libro")
    y_position -= 18
    
    pdf.setFillColorRGB(*hex_to_rgb(COLOR_NEGRO))
    pdf.setFont("Helvetica", 10)
    
    # Wrap texto de sinopsis
    sinopsis_lines = textwrap.wrap(sinopsis, width=80)
    for line in sinopsis_lines[:12]:  # Max 12 líneas
        if y_position < 2 * inch:
            break
        pdf.drawString(margin_left, y_position, line)
        y_position -= 12
    
    y_position -= 18
    
    # ─────────────────────────────────────
    # SECCIÓN: LO QUE DICEN LOS LECTORES
    # ─────────────────────────────────────
    if extractos and y_position > 2.5 * inch:
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_CYAN))
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(margin_left, y_position, "💬 Lo que dicen los lectores")
        y_position -= 18
        
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_GRIS))
        pdf.setFont("Helvetica-Oblique", 9)
        
        for extracto in extractos:
            if y_position < 2.2 * inch:
                break
            
            texto = extracto.get("extracto", "")
            fuente = extracto.get("fuente", "Anónimo")
            
            # Wrap extracto
            extracto_lines = textwrap.wrap(f'"{texto}"', width=78)
            for line in extracto_lines[:2]:  # Max 2 líneas por extracto
                if y_position < 2.2 * inch:
                    break
                pdf.drawString(margin_left + 10, y_position, line)
                y_position -= 10
            
            # Fuente
            pdf.setFont("Helvetica", 8)
            pdf.drawString(margin_left + 10, y_position, f"— {fuente}")
            y_position -= 16
            pdf.setFont("Helvetica-Oblique", 9)
        
        y_position -= 8
    
    # ─────────────────────────────────────
    # SECCIÓN: ¿PARA QUIÉN ES ESTE LIBRO?
    # ─────────────────────────────────────
    if y_position > 2 * inch:
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_CYAN))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(margin_left, y_position, "👥 ¿Para quién es este libro?")
        y_position -= 15
        
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_NEGRO))
        pdf.setFont("Helvetica", 10)
        
        # Wrap audiencia
        audiencia_lines = textwrap.wrap(audiencia_texto, width=75)
        for line in audiencia_lines[:2]:
            if y_position < 1.8 * inch:
                break
            pdf.drawString(margin_left, y_position, line)
            y_position -= 12
        
        y_position -= 10
    
    # ─────────────────────────────────────
    # SECCIÓN: TEN EN CUENTA
    # ─────────────────────────────────────
    if advertencias and y_position > 1.6 * inch:
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_VERDE))
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin_left, y_position, "⚠️ Ten en cuenta")
        y_position -= 14
        
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_GRIS))
        pdf.setFont("Helvetica", 9)
        
        # Advertencias
        for advertencia in advertencias[:4]:  # Max 4 advertencias
            if y_position < 1.5 * inch:
                break
            adv_lines = textwrap.wrap(f"• {advertencia}", width=75)
            for line in adv_lines[:2]:
                pdf.drawString(margin_left, y_position, line)
                y_position -= 10
    
    # ─────────────────────────────────────
    # FOOTER CON CRÉDITOS (solo página 2)
    # ─────────────────────────────────────
    dibujar_footer(pdf, width, height)
    
    # Finalizar PDF
    pdf.save()
    
    # Obtener bytes del PDF
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# COMPONENTES DE DISEÑO
# ============================================================

def dibujar_header(pdf: canvas.Canvas, width: float, height: float):
    """
    Dibuja header con logo en la parte superior.
    
    Args:
        pdf: Canvas de ReportLab
        width: Ancho de la página
        height: Alto de la página
    """
    # Ruta del logo
    logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logo-libria-transparente.png")
    
    # Dibujar logo (60px = ~0.83 inches)
    try:
        if os.path.exists(logo_path):
            logo_size = 0.6 * inch  # Tamaño del logo
            x_logo = 0.5 * inch
            y_logo = height - 0.9 * inch
            
            pdf.drawImage(
                logo_path,
                x_logo,
                y_logo,
                width=logo_size,
                height=logo_size,
                mask='auto',
                preserveAspectRatio=True
            )
            
            # Texto "LibrIA" al lado del logo
            pdf.setFillColorRGB(*hex_to_rgb(COLOR_CYAN))
            pdf.setFont("Helvetica-Bold", 20)
            pdf.drawString(x_logo + logo_size + 0.1 * inch, y_logo + 0.15 * inch, "LibrIA")
    except Exception as e:
        # Si falla el logo, solo texto
        pdf.setFillColorRGB(*hex_to_rgb(COLOR_CYAN))
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(0.5 * inch, height - 0.75 * inch, "📚 LibrIA")
    
    # Línea decorativa
    pdf.setStrokeColorRGB(*hex_to_rgb(COLOR_CYAN))
    pdf.setLineWidth(2)
    pdf.line(0.5 * inch, height - 1 * inch, width - 0.5 * inch, height - 1 * inch)


def dibujar_footer(pdf: canvas.Canvas, width: float, height: float):
    """
    Dibuja footer con créditos en la parte inferior.
    
    Args:
        pdf: Canvas de ReportLab
        width: Ancho de la página
        height: Alto de la página
    """
    # Línea decorativa
    pdf.setStrokeColorRGB(*hex_to_rgb(COLOR_CYAN))
    pdf.setLineWidth(1)
    pdf.line(0.5 * inch, 1.2 * inch, width - 0.5 * inch, 1.2 * inch)
    
    # Texto centrado
    y_footer = 0.9 * inch
    
    pdf.setFillColorRGB(*hex_to_rgb(COLOR_AZUL_OSCURO))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(width / 2, y_footer, "LibrIA - Reseñas Inteligentes")
    
    y_footer -= 15
    pdf.setFont("Helvetica", 9)
    pdf.setFillColorRGB(*hex_to_rgb(COLOR_GRIS))
    pdf.drawCentredString(width / 2, y_footer, "Desarrollado por Carlos Silva")
    
    y_footer -= 12
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(width / 2, y_footer, "Ing. en Informática")