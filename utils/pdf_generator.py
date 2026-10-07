"""
Generador de PDFs con ReportLab.
Presupuesto, Orden de Taller, Estado de Cuenta.
"""
import os
from pathlib import Path
from datetime import date
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfgen import canvas

from utils.helpers import fmt_moneda, fmt_fecha, fmt_fecha_larga, hoy_str, sumar_dias


# Paleta de colores del PDF
C_DARK    = colors.HexColor("#0f0f1a")
C_ACCENT  = colors.HexColor("#e94560")
C_BG      = colors.HexColor("#f5f5f5")
C_BORDER  = colors.HexColor("#cccccc")
C_TEXT    = colors.HexColor("#1a1a1a")
C_DIM     = colors.HexColor("#666666")
C_GREEN   = colors.HexColor("#1a6a2a")
C_WHITE   = colors.white


def _get_styles() -> dict:
    """Retorna estilos de párrafo personalizados."""
    base = getSampleStyleSheet()
    estilos = {
        "titulo": ParagraphStyle(
            "titulo", fontSize=18, textColor=C_ACCENT,
            fontName="Helvetica-Bold", alignment=TA_LEFT, spaceAfter=2
        ),
        "subtitulo": ParagraphStyle(
            "subtitulo", fontSize=10, textColor=C_DIM,
            fontName="Helvetica", alignment=TA_LEFT
        ),
        "header_empresa": ParagraphStyle(
            "header_empresa", fontSize=11, textColor=C_TEXT,
            fontName="Helvetica-Bold"
        ),
        "normal": ParagraphStyle(
            "normal", fontSize=9, textColor=C_TEXT, fontName="Helvetica"
        ),
        "small": ParagraphStyle(
            "small", fontSize=8, textColor=C_DIM, fontName="Helvetica"
        ),
        "bold": ParagraphStyle(
            "bold", fontSize=9, textColor=C_TEXT, fontName="Helvetica-Bold"
        ),
        "total_label": ParagraphStyle(
            "total_label", fontSize=12, textColor=C_TEXT,
            fontName="Helvetica-Bold", alignment=TA_RIGHT
        ),
        "total_valor": ParagraphStyle(
            "total_valor", fontSize=14, textColor=C_GREEN,
            fontName="Helvetica-Bold", alignment=TA_RIGHT
        ),
        "pie": ParagraphStyle(
            "pie", fontSize=8, textColor=C_DIM,
            fontName="Helvetica-Oblique", alignment=TA_CENTER
        ),
    }
    return estilos


def _header_empresa(story: list, datos_imprenta: dict, estilos: dict) -> None:
    """Agrega header con logo y datos de la empresa."""
    logo_path = datos_imprenta.get("logo_path", "")
    razon     = datos_imprenta.get("razon_social", "Mi Imprenta")
    cuit      = datos_imprenta.get("cuit", "")
    direccion = datos_imprenta.get("direccion", "")
    telefono  = datos_imprenta.get("telefono", "")
    email     = datos_imprenta.get("email", "")

    # Logo + datos lado a lado
    logo_cell: list = []
    if logo_path and Path(logo_path).exists():
        try:
            img = Image(logo_path, width=3.5*cm, height=2*cm)
            img.hAlign = "LEFT"
            logo_cell = [img]
        except Exception:
            logo_cell = [Paragraph(razon, estilos["titulo"])]
    else:
        logo_cell = [Paragraph(razon, estilos["titulo"])]

    datos_empresa = []
    datos_empresa.append(Paragraph(f"<b>{razon}</b>", estilos["header_empresa"]))
    if cuit:
        datos_empresa.append(Paragraph(f"CUIT: {cuit}", estilos["small"]))
    if direccion:
        datos_empresa.append(Paragraph(direccion, estilos["small"]))
    if telefono:
        datos_empresa.append(Paragraph(f"Tel: {telefono}", estilos["small"]))
    if email:
        datos_empresa.append(Paragraph(email, estilos["small"]))

    tabla_header = Table(
        [[logo_cell, datos_empresa]],
        colWidths=[4*cm, 13*cm]
    )
    tabla_header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(tabla_header)
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT, spaceAfter=8))


def generar_presupuesto(
    pedido: object,
    detalle: list,
    cliente: object,
    datos_imprenta: dict,
    output_path: str,
) -> str:
    """
    Genera PDF de presupuesto.
    Retorna path del archivo generado.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=2*cm
    )
    estilos = _get_styles()
    story = []

    # Header empresa
    _header_empresa(story, datos_imprenta, estilos)

    # Título del documento
    story.append(Paragraph("PRESUPUESTO", ParagraphStyle(
        "doc_titulo", fontSize=20, textColor=C_DARK,
        fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4
    )))
    usuario_txt = f"  |  Usuario: {pedido.usuario_nombre}" if getattr(pedido, 'usuario_nombre', '') else ""
    story.append(Paragraph(
        f"N° {pedido.nro_pedido}  |  Fecha: {fmt_fecha(pedido.fecha_creacion)}{usuario_txt}",
        ParagraphStyle("doc_sub", fontSize=10, textColor=C_DIM,
                       alignment=TA_CENTER, spaceAfter=12)
    ))

    # Datos del cliente
    fecha_vence = sumar_dias(pedido.fecha_creacion, 15)
    datos_cli = [
        ["CLIENTE", ""],
        ["Nombre:", cliente.nombre],
    ]
    if cliente.cuit:
        datos_cli.append(["CUIT:", cliente.cuit])
    if cliente.direccion:
        datos_cli.append(["Dirección:", cliente.direccion])
    if cliente.telefono:
        datos_cli.append(["Teléfono:", cliente.telefono])
    if pedido.fecha_entrega:
        datos_cli.append(["Fecha entrega:", fmt_fecha(pedido.fecha_entrega)])

    tabla_cli = Table(datos_cli, colWidths=[3.5*cm, 13.5*cm])
    tabla_cli.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("SPAN", (0, 0), (-1, 0)),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 1), (-1, -1), C_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BG, C_WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tabla_cli)
    story.append(Spacer(1, 12))

    # Tabla de items
    headers = ["Cant.", "Descripción", "Detalle", "P. Unit.", "Subtotal"]
    filas = [headers]
    for item in detalle:
        detalle_medidas = ""
        if item.ancho and item.alto:
            detalle_medidas = f"{item.ancho}m × {item.alto}m = {item.ancho*item.alto:.2f}m²"
        filas.append([
            str(item.cantidad),
            Paragraph(item.descripcion, estilos["normal"]),
            Paragraph(detalle_medidas, estilos["small"]),
            fmt_moneda(item.precio_unitario),
            fmt_moneda(item.subtotal),
        ])

    tabla_items = Table(filas, colWidths=[1.5*cm, 7*cm, 4*cm, 2.5*cm, 2*cm])
    tabla_items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tabla_items)
    story.append(Spacer(1, 10))

    # Totales (alineados a la derecha)
    totales_data = []
    totales_data.append(["Subtotal:", fmt_moneda(pedido.subtotal)])
    if pedido.descuento > 0:
        totales_data.append(["Descuento:", f"- {fmt_moneda(pedido.descuento)}"])
    if pedido.sena > 0:
        totales_data.append(["Seña / Anticipo:", f"- {fmt_moneda(pedido.sena)}"])
    totales_data.append(["TOTAL:", fmt_moneda(pedido.total)])
    if pedido.sena > 0:
        totales_data.append(["Saldo pendiente:", fmt_moneda(pedido.saldo)])

    tabla_totales = Table(totales_data, colWidths=[12*cm, 5*cm])
    estilo_totales = TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, C_DARK),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("TEXTCOLOR", (1, -1), (1, -1), C_GREEN),
    ])
    if pedido.descuento > 0:
        estilo_totales.add("TEXTCOLOR", (1, 1), (1, 1), colors.red)
    tabla_totales.setStyle(estilo_totales)
    story.append(tabla_totales)
    story.append(Spacer(1, 12))

    # Observaciones
    if pedido.observaciones:
        story.append(Paragraph("<b>Observaciones:</b>", estilos["bold"]))
        story.append(Paragraph(pedido.observaciones, estilos["normal"]))
        story.append(Spacer(1, 8))

    # Pie de página
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=6))
    story.append(Paragraph(
        f"Presupuesto válido hasta el {fmt_fecha(fecha_vence)}. No incluye IVA. "
        f"La seña/anticipo no es reembolsable una vez iniciado el trabajo.",
        estilos["pie"]
    ))

    doc.build(story)
    return output_path


def generar_orden_taller(pedidos: list, detalle_map: dict, output_path: str) -> str:
    """
    Genera PDF con todos los pedidos en estado 'En Taller'.
    detalle_map: {pedido_id: [PedidoDetalle]}
    """
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=2*cm
    )
    estilos = _get_styles()
    story = []

    story.append(Paragraph("ORDEN DE TALLER", ParagraphStyle(
        "ot", fontSize=18, fontName="Helvetica-Bold",
        textColor=C_DARK, alignment=TA_CENTER, spaceAfter=4
    )))
    story.append(Paragraph(
        f"Generado: {fmt_fecha(hoy_str())}  |  Total pedidos: {len(pedidos)}",
        ParagraphStyle("ot_sub", fontSize=9, textColor=C_DIM, alignment=TA_CENTER)
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT, spaceAfter=10))

    for pedido in pedidos:
        story.append(Paragraph(
            f"Pedido N° {pedido.nro_pedido} — {pedido.cliente_nombre}",
            ParagraphStyle("p_header", fontSize=11, fontName="Helvetica-Bold",
                           textColor=C_WHITE,
                           backColor=C_DARK, leftIndent=8,
                           spaceBefore=8, spaceAfter=4)
        ))
        info = f"Entrega: {fmt_fecha(pedido.fecha_entrega) or 'Sin fecha'}  |  Total: {fmt_moneda(pedido.total)}"
        story.append(Paragraph(info, estilos["small"]))

        items = detalle_map.get(pedido.id, [])
        if items:
            filas = [["Cant.", "Descripción", "Medidas"]]
            for item in items:
                medidas = f"{item.ancho}×{item.alto}m" if item.ancho and item.alto else ""
                filas.append([str(item.cantidad), item.descripcion, medidas])
            t = Table(filas, colWidths=[1.5*cm, 12*cm, 3.5*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333355")),
                ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_BG]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
        if pedido.observaciones:
            story.append(Paragraph(
                f"Obs: {pedido.observaciones}", estilos["small"]
            ))
        story.append(Spacer(1, 8))

    doc.build(story)
    return output_path


def generar_estado_cuenta(
    cliente: object,
    pedidos: list,
    pagos_map: dict,
    saldo_total: float,
    output_path: str,
) -> str:
    """
    Genera PDF de estado de cuenta del cliente.
    pagos_map: {pedido_id: [Pago]}
    """
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=2*cm
    )
    estilos = _get_styles()
    story = []

    story.append(Paragraph("ESTADO DE CUENTA", ParagraphStyle(
        "ec", fontSize=18, fontName="Helvetica-Bold",
        textColor=C_DARK, alignment=TA_CENTER, spaceAfter=4
    )))
    story.append(Paragraph(
        f"Cliente: {cliente.nombre}  |  Fecha: {fmt_fecha(hoy_str())}",
        ParagraphStyle("ec_sub", fontSize=10, textColor=C_DIM, alignment=TA_CENTER)
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT, spaceAfter=12))

    # Tabla resumen
    headers = ["Nro. Pedido", "Fecha", "Estado", "Total", "Seña", "Pagado", "Saldo"]
    filas = [headers]
    for p in pedidos:
        pagado = sum(pg.monto for pg in pagos_map.get(p.id, []))
        filas.append([
            p.nro_pedido,
            fmt_fecha(p.fecha_creacion),
            p.estado,
            fmt_moneda(p.total),
            fmt_moneda(p.sena),
            fmt_moneda(pagado),
            fmt_moneda(p.saldo),
        ])

    tabla = Table(filas, colWidths=[3*cm, 2.5*cm, 3*cm, 2.5*cm, 2*cm, 2*cm, 2*cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 12))

    # Total
    story.append(Paragraph(
        f"SALDO TOTAL PENDIENTE: {fmt_moneda(saldo_total)}",
        ParagraphStyle("saldo_total", fontSize=13, fontName="Helvetica-Bold",
                       textColor=C_ACCENT if saldo_total > 0 else C_GREEN,
                       alignment=TA_RIGHT)
    ))

    doc.build(story)
    return output_path
