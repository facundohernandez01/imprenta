"""
PDF de Factura Electrónica ARCA y Recibo de Pago.
"""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from utils.helpers import fmt_moneda, fmt_fecha, hoy_str
import base64
import json
import io


def _generar_qr_arca(factura) -> bytes | None:
    """
    Genera imagen QR de ARCA según especificación oficial.
    Retorna bytes PNG o None si no hay librería qrcode instalada.
    
    La URL del QR tiene formato:
    https://serviciosweb.afip.gob.ar/cae/qr/?p=<BASE64_JSON>
    """
    if not factura.cae:
        return None
    
    # Construir el payload JSON según especificación ARCA
    cuit_receptor = factura.cuit_receptor.replace("-", "").strip() if factura.cuit_receptor else ""
    nro_cbte_str  = str(factura.nro_factura or "").split("-")
    nro_cbte      = int(nro_cbte_str[-1]) if nro_cbte_str else 0
    
    payload = {
        "ver":         1,
        "fecha":       factura.fecha_emision.replace("-", "") if factura.fecha_emision else "",
        "cuit":        0,           # se completa con el CUIT del emisor en get_datos_imprenta
        "ptoVta":      factura.punto_venta,
        "tipoCbte":    factura.tipo_cbte,
        "nroCbte":     nro_cbte,
        "importe":     factura.importe_total,
        "tipoDoc":     80 if cuit_receptor else 99,
        "nroDoc":      int(cuit_receptor) if cuit_receptor else 0,
        "cae":         factura.cae,
        "fechaCae":    factura.cae_vto.replace("-", "") if factura.cae_vto else "",
        "tipoCodAut":  "E",
    }
    
    json_bytes   = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64_payload  = base64.b64encode(json_bytes).decode("ascii")
    url_qr       = f"https://serviciosweb.afip.gob.ar/cae/qr/?p={b64_payload}"
    
    try:
        import qrcode
        from qrcode.image.pil import PilImage
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=2,
        )
        qr.add_data(url_qr)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        # qrcode no instalado: generar QR mínimo con PIL puro usando 
        # una matriz de puntos simple (fallback visual)
        return _qr_fallback_pil(url_qr)


def _qr_fallback_pil(url: str) -> bytes | None:
    """
    Fallback: genera una imagen con el texto de la URL cuando qrcode no está.
    No es un QR real, pero muestra la URL para escaneo manual.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        w, h = 200, 60
        img = Image.new("RGB", (w, h), "white")
        draw = ImageDraw.Draw(img)
        draw.text((5, 5),  "URL QR ARCA:", fill="black")
        draw.text((5, 20), url[:55], fill="gray")
        draw.text((5, 35), url[55:110] if len(url) > 55 else "", fill="gray")
        draw.text((5, 50), "(instalar: pip install qrcode[pil])", fill="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None

C_DARK   = colors.HexColor("#0f0f1a")
C_ACCENT = colors.HexColor("#e94560")
C_BG     = colors.HexColor("#f5f5f5")
C_BORDER = colors.HexColor("#cccccc")
C_TEXT   = colors.HexColor("#1a1a1a")
C_DIM    = colors.HexColor("#666666")
C_GREEN  = colors.HexColor("#1a6a2a")
C_WHITE  = colors.white

TIPO_CBTE_NOMBRES = {
    1: "FACTURA A", 6: "FACTURA B", 11: "FACTURA C",
    2: "NOTA DE DÉBITO A", 7: "NOTA DE DÉBITO B",
    3: "NOTA DE CRÉDITO A", 8: "NOTA DE CRÉDITO B",
}

LETRA_TIPO = {1: "A", 6: "B", 11: "C", 2: "A", 7: "B", 3: "A", 8: "B"}


def _estilo(nombre, **kw) -> ParagraphStyle:
    defaults = dict(fontName="Helvetica", fontSize=9, textColor=C_TEXT)
    defaults.update(kw)
    return ParagraphStyle(nombre, **defaults)


def generar_factura_pdf(factura, datos_imprenta: dict, output_path: str) -> str:
    """
    Genera PDF de factura electrónica con QR de CAE (texto plano si no hay qrcode).
    """
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=2*cm,
    )
    story = []

    razon      = datos_imprenta.get("razon_social", "")
    cuit       = datos_imprenta.get("cuit", "")
    domicilio  = datos_imprenta.get("domicilio_fiscal", datos_imprenta.get("direccion", ""))
    telefono   = datos_imprenta.get("telefono", "")
    email_imp  = datos_imprenta.get("email", "")
    iibb       = datos_imprenta.get("ingresos_brutos", "")
    logo_path  = datos_imprenta.get("logo_path", "")
    letra      = LETRA_TIPO.get(factura.tipo_cbte, "B")
    tipo_nombre = TIPO_CBTE_NOMBRES.get(factura.tipo_cbte, f"COMPROBANTE TIPO {factura.tipo_cbte}")

    N  = _estilo("N")
    NB = _estilo("NB", fontName="Helvetica-Bold")
    S  = _estilo("S", fontSize=8, textColor=C_DIM)
    T  = _estilo("T", fontSize=14, fontName="Helvetica-Bold", textColor=C_ACCENT)
    TR = _estilo("TR", fontSize=12, fontName="Helvetica-Bold", alignment=TA_RIGHT)
    C  = _estilo("C", alignment=TA_CENTER)
    CB = _estilo("CB", fontName="Helvetica-Bold", alignment=TA_CENTER, fontSize=10)

    # ── ENCABEZADO BIPARTITO (izq=empresa, centro=letra, der=datos cbte) ──
    logo_cell = []
    if logo_path and Path(logo_path).exists():
        try:
            logo_cell.append(Image(logo_path, width=3.2*cm, height=1.8*cm))
        except Exception:
            pass
    logo_cell.append(Paragraph(f"<b>{razon}</b>", NB))
    logo_cell.append(Paragraph(f"CUIT: {cuit}", S))
    logo_cell.append(Paragraph(domicilio, S))
    if telefono:
        logo_cell.append(Paragraph(f"Tel: {telefono}", S))
    if iibb:
        logo_cell.append(Paragraph(f"IIBB: {iibb}", S))

    # Centro: letra grande
    letra_cell = [
        Paragraph(f"<b>{letra}</b>", ParagraphStyle(
            "letra_grande", fontSize=40, fontName="Helvetica-Bold",
            alignment=TA_CENTER, textColor=C_DARK
        )),
        Paragraph(tipo_nombre, ParagraphStyle(
            "tipo_nombre", fontSize=8, alignment=TA_CENTER, textColor=C_DIM
        )),
    ]

    # Derecha: número y fecha
    pv_str = str(factura.punto_venta).zfill(4)
    nro_str = str(factura.nro_factura or "").zfill(8) if factura.nro_factura else "--------"
    der_cell = [
        Paragraph(f"Punto de Venta: {pv_str}", S),
        Paragraph(f"N°: <b>{pv_str}-{nro_str}</b>", NB),
        Paragraph(f"Fecha: {fmt_fecha(factura.fecha_emision)}", N),
        Spacer(1, 4),
        Paragraph("Responsable Inscripto" if letra == "A" else "Consumidor Final / Monotributo", S),
    ]

    header_tbl = Table([[logo_cell, letra_cell, der_cell]],
                        colWidths=[7*cm, 3*cm, 7*cm])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("LINEAFTER", (0, 0), (0, 0), 1, C_BORDER),
        ("LINEBEFORE", (2, 0), (2, 0), 1, C_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(header_tbl)
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT, spaceAfter=8))

    # ── RECEPTOR ──
    datos_rec = [
        ["DATOS DEL RECEPTOR", ""],
        ["Razón Social / Nombre:", factura.razon_receptor or "Consumidor Final"],
        ["CUIT / DNI:", factura.cuit_receptor or "-"],
        ["Domicilio:", factura.domicilio_receptor or "-"],
    ]
    tbl_rec = Table(datos_rec, colWidths=[5*cm, 12*cm])
    tbl_rec.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("SPAN", (0, 0), (-1, 0)),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, C_BORDER),
        ("BACKGROUND", (0, 1), (-1, -1), C_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tbl_rec)
    story.append(Spacer(1, 10))

    # ── TABLA IMPORTES ──
    filas_imp = [["Descripción", "Importe Neto", "IVA", "Total"]]
    concepto_desc = {1: "Productos", 2: "Servicios", 3: "Productos y Servicios"}
    desc = factura.observaciones or concepto_desc.get(factura.concepto, "Servicios")
    filas_imp.append([
        Paragraph(desc, N),
        fmt_moneda(factura.importe_neto),
        fmt_moneda(factura.importe_iva),
        fmt_moneda(factura.importe_total),
    ])
    tbl_imp = Table(filas_imp, colWidths=[9*cm, 3*cm, 3*cm, 2*cm])
    tbl_imp.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, C_BORDER),
        ("BACKGROUND", (0, 1), (-1, -1), C_WHITE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl_imp)
    story.append(Spacer(1, 8))

    # ── TOTAL ──
    total_tbl = Table([
        ["IMPORTE TOTAL:", fmt_moneda(factura.importe_total)]
    ], colWidths=[14*cm, 3*cm])
    total_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("TEXTCOLOR", (1, 0), (1, 0), C_GREEN),
        ("LINEABOVE", (0, 0), (-1, 0), 1, C_DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(total_tbl)
    story.append(Spacer(1, 14))

    # ── CAE ──
    if factura.cae:
        cae_tbl = Table([
            ["CAE N°:", factura.cae, "Vto. CAE:", fmt_fecha(factura.cae_vto)]
        ], colWidths=[2.5*cm, 6*cm, 2.5*cm, 6*cm])
        cae_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e8ffe8")),
            ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#80c080")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(cae_tbl)

    story.append(Spacer(1, 8))
    
    # ── QR ARCA ──
    if factura.cae:
        # Actualizar cuit del emisor en el payload QR
        cuit_emisor = datos_imprenta.get("cuit", "").replace("-","").strip()
        _factura_con_cuit = factura
        try:
            # Parche para pasar el cuit al generador de QR
            class _FWithCuit:
                def __getattr__(self, name):
                    return getattr(factura, name)
            _FWithCuit.cuit_emisor = cuit_emisor
        except Exception:
            pass
        
        qr_bytes = _generar_qr_arca(factura)
        if qr_bytes:
            # Actualizar cuit en el QR: regenerar con cuit correcto
            try:
                import base64, json, io
                cuit_num = int(cuit_emisor) if cuit_emisor else 0
                nro_cbte_s = str(factura.nro_factura or "").split("-")
                nro_cbte   = int(nro_cbte_s[-1]) if nro_cbte_s else 0
                payload = {
                    "ver":1, "fecha": (factura.fecha_emision or "").replace("-",""),
                    "cuit": cuit_num, "ptoVta": factura.punto_venta,
                    "tipoCbte": factura.tipo_cbte, "nroCbte": nro_cbte,
                    "importe": factura.importe_total,
                    "tipoDoc": 80 if factura.cuit_receptor else 99,
                    "nroDoc": int(factura.cuit_receptor.replace("-","")) if factura.cuit_receptor else 0,
                    "cae": factura.cae,
                    "fechaCae": (factura.cae_vto or "").replace("-",""),
                    "tipoCodAut": "E",
                }
                b64 = base64.b64encode(json.dumps(payload, separators=(",",":")).encode()).decode()
                url_qr = f"https://serviciosweb.afip.gob.ar/cae/qr/?p={b64}"
                try:
                    import qrcode
                    qr = qrcode.QRCode(version=None,
                        error_correction=qrcode.constants.ERROR_CORRECT_M,
                        box_size=4, border=2)
                    qr.add_data(url_qr); qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    buf = io.BytesIO(); img.save(buf, format="PNG")
                    qr_bytes = buf.getvalue()
                except ImportError:
                    pass
            except Exception:
                pass
            
            from reportlab.platypus import Image as RLImage
            buf_rl = io.BytesIO(qr_bytes)
            qr_img = RLImage(buf_rl, width=2.5*cm, height=2.5*cm)
            lbl_qr = Paragraph("QR ARCA — Verificá este comprobante escaneando el código",
                                _estilo("qr_lbl", fontSize=7, textColor=C_DIM))
            qr_tbl = Table([[qr_img, lbl_qr]], colWidths=[3*cm, 14*cm])
            qr_tbl.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f0fff0")),
                ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#80c080")),
                ("LEFTPADDING", (0,0), (-1,-1), 6),
                ("TOPPADDING", (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(qr_tbl)
            story.append(Spacer(1, 4))

    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER))
    story.append(Paragraph(
        "Comprobante generado electrónicamente — Autorizado por ARCA",
        _estilo("pie", fontSize=8, textColor=C_DIM, alignment=TA_CENTER)
    ))

    doc.build(story)
    return output_path


def generar_recibo_pdf(recibo, datos_imprenta: dict,
                       cliente_nombre: str, output_path: str) -> str:
    """Genera PDF de recibo de pago simple."""
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=2*cm,
    )
    story = []
    razon   = datos_imprenta.get("razon_social", "")
    cuit    = datos_imprenta.get("cuit", "")
    dom     = datos_imprenta.get("domicilio_fiscal", datos_imprenta.get("direccion", ""))
    logo    = datos_imprenta.get("logo_path", "")

    N  = _estilo("N2")
    NB = _estilo("NB2", fontName="Helvetica-Bold")
    S  = _estilo("S2", fontSize=8, textColor=C_DIM)

    # Header
    logo_items = []
    if logo and Path(logo).exists():
        try:
            logo_items.append(Image(logo, width=3*cm, height=1.7*cm))
        except Exception:
            pass
    logo_items += [Paragraph(f"<b>{razon}</b>", NB), Paragraph(f"CUIT: {cuit}", S),
                   Paragraph(dom, S)]

    rec_items = [
        Paragraph("<b>RECIBO DE PAGO</b>", ParagraphStyle(
            "rh", fontSize=16, fontName="Helvetica-Bold",
            textColor=C_ACCENT, alignment=TA_RIGHT
        )),
        Paragraph(f"N° {recibo.nro_recibo}", ParagraphStyle(
            "rn", fontSize=11, fontName="Helvetica-Bold", alignment=TA_RIGHT
        )),
        Paragraph(f"Fecha: {fmt_fecha(recibo.fecha)}", _estilo("rf", alignment=TA_RIGHT)),
    ]

    hdr = Table([[logo_items, rec_items]], colWidths=[9*cm, 8*cm])
    hdr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT, spaceAfter=10))

    story.append(Paragraph(
        f"Recibí de <b>{cliente_nombre}</b> la suma de:", N
    ))
    story.append(Spacer(1, 6))

    monto_tbl = Table([[fmt_moneda(recibo.monto)]], colWidths=[17*cm])
    monto_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_BG),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 18),
        ("TEXTCOLOR", (0, 0), (-1, -1), C_GREEN),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 1, C_BORDER),
    ]))
    story.append(monto_tbl)
    story.append(Spacer(1, 10))

    detalle = [
        ["Método de pago:", recibo.metodo or "-"],
        ["Concepto:", recibo.concepto or "-"],
    ]
    if recibo.nro_pedido:
        detalle.append(["Pedido N°:", recibo.nro_pedido])

    tbl_det = Table(detalle, colWidths=[4*cm, 13*cm])
    tbl_det.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl_det)
    story.append(Spacer(1, 30))

    firma_tbl = Table([["_________________________", "_________________________"]],
                       colWidths=[8*cm, 8*cm])
    firma_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), C_DIM),
    ]))
    story.append(firma_tbl)
    tbl_labels = Table([["Firma Receptor", "Firma Emisor"]], colWidths=[8*cm, 8*cm])
    tbl_labels.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), C_DIM),
    ]))
    story.append(tbl_labels)

    doc.build(story)
    return output_path
