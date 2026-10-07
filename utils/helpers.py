"""
Utilidades: formateo, validación, WhatsApp.
"""
import re
import urllib.parse
from datetime import date, datetime, timedelta
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


# ─── FORMATTERS ────────────────────────────────────────────────────────────────

def fmt_moneda(valor: float) -> str:
    """Formatea número como moneda argentina: $1.234,56"""
    if valor is None:
        return "$0,00"
    return f"${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_fecha(fecha_str: str) -> str:
    """Convierte YYYY-MM-DD a DD/MM/YYYY."""
    if not fecha_str:
        return ""
    try:
        d = datetime.strptime(fecha_str[:10], "%Y-%m-%d")
        return d.strftime("%d/%m/%Y")
    except ValueError:
        return fecha_str


def fmt_fecha_larga(fecha_str: str) -> str:
    """Convierte YYYY-MM-DD a 'lunes 01 de enero de 2026'."""
    if not fecha_str:
        return ""
    meses = ["enero","febrero","marzo","abril","mayo","junio",
             "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    try:
        d = datetime.strptime(fecha_str[:10], "%Y-%m-%d")
        return f"{d.day:02d} de {meses[d.month-1]} de {d.year}"
    except ValueError:
        return fecha_str


def hoy_str() -> str:
    """Retorna hoy en formato YYYY-MM-DD."""
    return date.today().isoformat()


def sumar_dias(fecha_str: str, dias: int) -> str:
    """Suma días a fecha YYYY-MM-DD y retorna YYYY-MM-DD."""
    try:
        d = datetime.strptime(fecha_str[:10], "%Y-%m-%d") + timedelta(days=dias)
        return d.strftime("%Y-%m-%d")
    except ValueError:
        return fecha_str


def es_vencida(fecha_str: str, estado: str) -> bool:
    """Retorna True si la fecha de entrega está vencida y el pedido sigue activo."""
    if not fecha_str:
        return False
    estados_finales = {"Entregado", "Cobrado", "Cancelado"}
    if estado in estados_finales:
        return False
    try:
        d = datetime.strptime(fecha_str[:10], "%Y-%m-%d").date()
        return d < date.today()
    except ValueError:
        return False


# ─── VALIDATORS ────────────────────────────────────────────────────────────────

def validar_requerido(valor: str, campo: str) -> str | None:
    """Retorna mensaje de error si el campo está vacío."""
    if not valor or not valor.strip():
        return f"El campo '{campo}' es requerido."
    return None


def validar_positivo(valor: float, campo: str) -> str | None:
    """Retorna mensaje de error si el valor no es positivo."""
    if valor <= 0:
        return f"'{campo}' debe ser mayor a 0."
    return None


def limpiar_telefono(tel: str) -> str:
    """Elimina caracteres no numéricos del teléfono."""
    return re.sub(r"[^\d]", "", tel)


def formatear_wa_numero(numero: str) -> str:
    """
    Convierte número argentino a formato internacional para WhatsApp.
    Ej: 03460 15-123456 → 5493460123456
    """
    limpio = limpiar_telefono(numero)
    # Quitar 0 inicial de código de área
    if limpio.startswith("0"):
        limpio = limpio[1:]
    # Quitar 15 de celular
    if len(limpio) > 6 and limpio[2:4] == "15":
        limpio = limpio[:2] + limpio[4:]
    # Agregar prefijo Argentina
    if not limpio.startswith("54"):
        limpio = "549" + limpio
    return limpio


# ─── WHATSAPP ──────────────────────────────────────────────────────────────────

def abrir_whatsapp_presupuesto(
    nombre: str,
    whatsapp: str,
    nro_pedido: str,
    total: float,
    fecha_creacion: str,
) -> bool:
    """
    Abre WhatsApp Web con mensaje de presupuesto pre-armado.
    Retorna True si pudo abrir, False si el número está vacío.
    """
    if not whatsapp or not whatsapp.strip():
        return False

    numero = formatear_wa_numero(whatsapp)
    fecha_vence = sumar_dias(fecha_creacion, 15)
    fecha_vence_fmt = fmt_fecha(fecha_vence)
    total_fmt = fmt_moneda(total)

    mensaje = (
        f"Hola {nombre}! 👋\n"
        f"Te envío el presupuesto N° {nro_pedido} por {total_fmt}.\n"
        f"El presupuesto vence el {fecha_vence_fmt}.\n"
        f"Cualquier consulta me avisás. ¡Gracias! 🖨️"
    )

    url = f"https://wa.me/{numero}?text={urllib.parse.quote(mensaje)}"
    QDesktopServices.openUrl(QUrl(url))
    return True


def abrir_whatsapp_resumen(
    nombre: str,
    whatsapp: str,
    saldo_total: float,
    pedidos_resumen: list[dict],
) -> bool:
    """Abre WhatsApp con resumen de cuenta corriente."""
    if not whatsapp or not whatsapp.strip():
        return False

    numero = formatear_wa_numero(whatsapp)
    lineas = [f"Hola {nombre}! 👋\nResumen de cuenta:\n"]
    for p in pedidos_resumen[:10]:  # máximo 10 para no saturar
        lineas.append(f"• Pedido {p['nro']}: {fmt_moneda(p['saldo'])} pendiente")
    lineas.append(f"\n💰 *Saldo total: {fmt_moneda(saldo_total)}*")
    lineas.append("\nCualquier consulta me avisás. ¡Gracias!")

    mensaje = "\n".join(lineas)
    url = f"https://wa.me/{numero}?text={urllib.parse.quote(mensaje)}"
    QDesktopServices.openUrl(QUrl(url))
    return True
