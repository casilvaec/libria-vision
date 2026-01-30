# ============================================================
# EMAIL SENDER - LIBRIA
# ============================================================
# Envía PDFs por email usando Gmail SMTP

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


# ============================================================
# FUNCIÓN PRINCIPAL DE ENVÍO
# ============================================================

def enviar_pdf_email(email_destino: str, pdf_bytes: bytes, titulo_libro: str) -> bool:
    """
    Envía PDF de reseña por Gmail SMTP.
    
    Args:
        email_destino: Email del destinatario
        pdf_bytes: Bytes del PDF generado
        titulo_libro: Título del libro para el subject
        
    Returns:
        bool: True si se envió exitosamente, False si falló
        
    Raises:
        Exception: Si falta configuración o error crítico
    """
    # Obtener credenciales desde variables de entorno
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    
    if not gmail_user or not gmail_password:
        logger.error("GMAIL_USER o GMAIL_APP_PASSWORD no configurados")
        raise ValueError(
            "Falta configuración de email. "
            "Verifica que GMAIL_USER y GMAIL_APP_PASSWORD estén en .env"
        )
    
    logger.info(f"Preparando envío de PDF a {email_destino} para libro: {titulo_libro}")
    
    # Crear mensaje
    msg = MIMEMultipart()
    msg['From'] = f"LibrIA <{gmail_user}>"
    msg['To'] = email_destino
    msg['Subject'] = f"📚 Tu reseña de \"{titulo_libro}\" - LibrIA"
    
    # Cuerpo del email (HTML bonito)
    body_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
          <h2 style="color: #00D9FF;">📚 ¡Tu reseña está lista!</h2>
          
          <p>Hola,</p>
          
          <p>Aquí está la reseña completa de <strong>"{titulo_libro}"</strong> que solicitaste en LibrIA.</p>
          
          <p>El PDF adjunto incluye:</p>
          <ul>
            <li>📖 Sinopsis completa</li>
            <li>🎯 Temas clave</li>
            <li>💬 Reseñas destacadas</li>
            <li>👥 Público objetivo</li>
          </ul>
          
          <p style="margin-top: 30px; font-size: 14px; color: #666;">
            <strong>LibrIA - Reseñas Inteligentes</strong><br>
            Desarrollado por Carlos Silva | Ing. en Informática
          </p>
          
          <p style="font-size: 12px; color: #999; margin-top: 20px;">
            Este email fue generado automáticamente. Si no solicitaste esta reseña, puedes ignorar este mensaje.
          </p>
        </div>
      </body>
    </html>
    """
    
    msg.attach(MIMEText(body_html, 'html'))
    
    # Adjuntar PDF
    pdf_attachment = MIMEApplication(pdf_bytes, _subtype='pdf')
    
    # Sanitizar nombre del archivo (remover caracteres problemáticos)
    filename_safe = sanitizar_nombre_archivo(titulo_libro)
    pdf_attachment.add_header(
        'Content-Disposition',
        'attachment',
        filename=f'{filename_safe}.pdf'
    )
    msg.attach(pdf_attachment)
    
    # Enviar email
    try:
        logger.info(f"Conectando a Gmail SMTP...")
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(gmail_user, gmail_password)
            smtp.send_message(msg)
        
        logger.info(f"✅ PDF enviado exitosamente a {email_destino}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Error de autenticación Gmail: {str(e)}")
        raise Exception(
            "Error de autenticación con Gmail. "
            "Verifica que GMAIL_APP_PASSWORD sea correcto y que la verificación en 2 pasos esté activada."
        )
        
    except smtplib.SMTPException as e:
        logger.error(f"Error SMTP al enviar email: {str(e)}")
        raise Exception(f"Error al enviar email: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error inesperado al enviar email: {str(e)}", exc_info=True)
        raise Exception(f"Error inesperado: {str(e)}")


# ============================================================
# UTILIDADES
# ============================================================

def sanitizar_nombre_archivo(nombre: str) -> str:
    """
    Sanitiza nombre de archivo para uso seguro.
    
    Remueve caracteres problemáticos y limita longitud.
    
    Args:
        nombre: Nombre original del archivo
        
    Returns:
        str: Nombre sanitizado
    """
    # Caracteres a remover o reemplazar
    reemplazos = {
        '/': '-',
        '\\': '-',
        ':': '-',
        '*': '',
        '?': '',
        '"': '',
        '<': '',
        '>': '',
        '|': '',
        '\n': ' ',
        '\r': ' '
    }
    
    # Aplicar reemplazos
    for char, replacement in reemplazos.items():
        nombre = nombre.replace(char, replacement)
    
    # Remover espacios múltiples
    nombre = ' '.join(nombre.split())
    
    # Limitar longitud (máximo 50 caracteres)
    if len(nombre) > 50:
        nombre = nombre[:47] + '...'
    
    return nombre.strip()