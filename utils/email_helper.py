"""
Envío de emails con adjunto PDF. Usa Gmail con App Password.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from models.config_model import ConfigModel


def _get_config() -> dict:
    c = ConfigModel()
    return {
        "gmail_cuenta":  c.get("gmail_cuenta", ""),
        "gmail_app_pass": c.get("gmail_app_pass", ""),
        "razon_social":  c.get("razon_social", "Imprenta"),
    }


def _smtp_configurado() -> bool:
    cfg = _get_config()
    return bool(cfg["gmail_cuenta"] and cfg["gmail_app_pass"])


def enviar_email(
    destinatario: str,
    asunto: str,
    cuerpo_html: str,
    pdf_path: str | None = None,
    nombre_adjunto: str = "documento.pdf",
) -> dict:
    """
    Envía email con adjunto PDF opcional.
    Retorna {'success': bool, 'message': str}
    """
    if not _smtp_configurado():
        return {"success": False,
                "message": "Email no configurado. Configurá Gmail en Ajustes."}
    if not destinatario or "@" not in destinatario:
        return {"success": False, "message": "Dirección de email inválida o vacía."}

    cfg = _get_config()
    try:
        msg = MIMEMultipart("alternative" if not pdf_path else "mixed")
        msg["Subject"] = asunto
        msg["From"]    = f"{cfg['razon_social']} <{cfg['gmail_cuenta']}>"
        msg["To"]      = destinatario

        msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

        if pdf_path and Path(pdf_path).exists():
            with open(pdf_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition",
                            f'attachment; filename="{nombre_adjunto}"')
            msg.attach(part)

        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=contexto) as server:
            server.login(cfg["gmail_cuenta"], cfg["gmail_app_pass"])
            server.sendmail(cfg["gmail_cuenta"], destinatario, msg.as_string())

        return {"success": True, "message": f"Email enviado a {destinatario}"}

    except smtplib.SMTPAuthenticationError:
        return {"success": False,
                "message": "Error de autenticación Gmail. Verificá la App Password."}
    except Exception as e:
        return {"success": False, "message": f"Error al enviar email: {e}"}


def cuerpo_factura(razon_emisor: str, nro_factura: str, cae: str,
                   total: str, cliente_nombre: str) -> str:
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#222;">
    <h2 style="color:#e94560;">Factura Electrónica — {razon_emisor}</h2>
    <p>Estimado/a <b>{cliente_nombre}</b>,</p>
    <p>Adjuntamos la factura electrónica <b>N° {nro_factura}</b>
       por un total de <b>{total}</b>.</p>
    <p>CAE: <b>{cae}</b></p>
    <p>Podés descargar el PDF adjunto para guardarlo en tus registros.</p>
    <br/>
    <p style="color:#888;font-size:11px;">
        Este mensaje fue generado automáticamente por Gestión Imprenta Pro.
    </p>
    </body></html>
    """


def cuerpo_recibo(razon_emisor: str, nro_recibo: str, monto: str,
                  metodo: str, cliente_nombre: str) -> str:
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#222;">
    <h2 style="color:#e94560;">Recibo de Pago — {razon_emisor}</h2>
    <p>Estimado/a <b>{cliente_nombre}</b>,</p>
    <p>Adjuntamos el recibo <b>N° {nro_recibo}</b>
       por un monto de <b>{monto}</b> ({metodo}).</p>
    <p>Podés descargar el PDF adjunto como comprobante.</p>
    <br/>
    <p style="color:#888;font-size:11px;">
        Este mensaje fue generado automáticamente por Gestión Imprenta Pro.
    </p>
    </body></html>
    """
