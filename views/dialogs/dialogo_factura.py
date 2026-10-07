"""
Diálogo para emitir factura electrónica ARCA desde cuenta corriente.
Pre-carga datos del pedido/cliente. Valida campos obligatorios.
"""
from datetime import date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QDoubleSpinBox,
    QDateEdit, QTextEdit, QMessageBox, QDialogButtonBox,
    QProgressDialog, QCheckBox
)
from PySide6.QtCore import Qt, QDate, QThread, Signal, QObject
from PySide6.QtGui import QFont

import configwsfe as cfgwsfe
from models.factura_model import FacturaModel, Factura
from models.config_model import ConfigModel
from models.usuario_model import UsuarioModel
from controllers.afip_controller import AFIPController
from utils.helpers import fmt_moneda, hoy_str
from utils.styles import AppStyles
from network.data_provider import get_provider


TIPOS_CBTE = [
    ("Factura B (Consumidor Final)", 6),
    ("Factura A (Responsable Inscripto)", 1),
    ("Factura C (Monotributo)", 11),
]

ALICUOTAS = [
    ("IVA 21%", cfgwsfe.IVA_21_PORCIENTO),
    ("IVA 10.5%", cfgwsfe.IVA_10_5_PORCIENTO),
    ("IVA 0%", cfgwsfe.IVA_0_PORCIENTO),
    ("No aplica (Fact. C)", cfgwsfe.IVA_0_PORCIENTO),
]

CONCEPTOS = [
    ("Productos", cfgwsfe.CONCEPTO_PRODUCTOS),
    ("Servicios", cfgwsfe.CONCEPTO_SERVICIOS),
    ("Mixto", cfgwsfe.CONCEPTO_MIXTO),
]


class _WorkerAFIP(QObject):
    """Worker para emitir en hilo separado sin bloquear UI."""
    terminado = Signal(dict)

    def __init__(self, datos: dict):
        super().__init__()
        self.datos = datos

    def run(self) -> None:
        ctrl = AFIPController()
        result = ctrl.emitir_factura(self.datos)
        self.terminado.emit(result)


class DialogoEmitirFactura(QDialog):
    """Formulario completo para emitir una factura electrónica."""

    def __init__(self, pedido=None, pago=None, cliente=None, parent=None):
        super().__init__(parent)
        self.pedido  = pedido
        self.pago    = pago
        self.cliente = cliente
        self.config  = get_provider().config
        self.factura_model = get_provider().facturas
        self.afip_ctrl = AFIPController()
        self._factura_id: int = 0
        self._pdf_path: str = ""

        self.setWindowTitle("Emitir Factura Electrónica — ARCA")
        self.setMinimumSize(780, 720)
        self.setModal(True)
        self._build_ui()
        self._pre_cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)
        def two_col(form: QFormLayout) -> QHBoxLayout:
            container = QHBoxLayout()
            left = QFormLayout()
            right = QFormLayout()
            left.setLabelAlignment(Qt.AlignRight)
            right.setLabelAlignment(Qt.AlignRight)
            for i in range(form.rowCount()):
                label_item = form.itemAt(i, QFormLayout.ItemRole.LabelRole)
                field_item = form.itemAt(i, QFormLayout.ItemRole.FieldRole)

                if i % 2 == 0:
                    left.addRow(label_item.widget(), field_item.widget())
                else:
                    right.addRow(label_item.widget(), field_item.widget())

            container.addLayout(left)
            container.addLayout(right)
            container.setStretch(0, 1)  # 👈 clave
            container.setStretch(1, 1)  # 👈 clave

            return container
        # Header
        titulo = QLabel("🧾  Emitir Factura Electrónica")
        titulo.setObjectName("lbl_header")
        layout.addWidget(titulo)

        cuit_emisor = self.config.get("cuit", "")
        lbl_emisor = QLabel(
            f"Emisor: {self.config.get('razon_social','')} — CUIT: {cuit_emisor} — "
            f"Punto de Venta: {self.config.get('punto_venta','1')}"
        )
        lbl_emisor.setStyleSheet(f"color: {AppStyles.TEXT_DIM}; font-size: 9pt;")
        layout.addWidget(lbl_emisor)

        # ── Tipo de comprobante ──
        grp_tipo = QGroupBox("Comprobante")
        form_tipo = QFormLayout()
        self.cmb_tipo = QComboBox()
        for texto, val in TIPOS_CBTE:
            self.cmb_tipo.addItem(texto, val)
        self.cmb_tipo.currentIndexChanged.connect(self._on_tipo_cambiado)

        self.date_emision = QDateEdit(QDate.currentDate())
        self.date_emision.setCalendarPopup(True)
        self.date_emision.setDisplayFormat("dd/MM/yyyy")

        self.cmb_concepto = QComboBox()
        for txt, val in CONCEPTOS:
            self.cmb_concepto.addItem(txt, val)

        form_tipo.addRow("Tipo:", self.cmb_tipo)
        form_tipo.addRow("Fecha emisión:", self.date_emision)
        form_tipo.addRow("Concepto:", self.cmb_concepto)
        grp_tipo.setLayout(two_col(form_tipo))
        layout.addWidget(grp_tipo)

        # ── Receptor ──
        grp_rec = QGroupBox("Datos del Receptor")
        
        form_rec = QFormLayout()
        self.inp_razon   = QLineEdit()
        self.inp_cuit_r  = QLineEdit()
        self.inp_cuit_r.setPlaceholderText("CUIT o DNI (ej: 20-12345678-9)")
        self.inp_dom_r   = QLineEdit()

        form_rec.addRow("Razón Social *:", self.inp_razon)
        form_rec.addRow("CUIT/DNI:", self.inp_cuit_r)
        form_rec.addRow("Domicilio:", self.inp_dom_r)
        grp_rec.setLayout(two_col(form_rec))
        layout.addWidget(grp_rec)

        # ── Importes ──
        grp_imp = QGroupBox("Importes")
        form_imp = QFormLayout()

        self.spin_neto = QDoubleSpinBox()
        self.spin_neto.setRange(0.01, 9_999_999)
        self.spin_neto.setDecimals(2)
        self.spin_neto.setPrefix("$ ")
        self.spin_neto.valueChanged.connect(self._recalcular)

        self.cmb_alicuota = QComboBox()
        for txt, val in ALICUOTAS:
            self.cmb_alicuota.addItem(txt, val)
        self.cmb_alicuota.currentIndexChanged.connect(self._recalcular)

        self.lbl_iva   = QLabel("$ 0,00")
        self.lbl_total = QLabel("$ 0,00")
        self.lbl_total.setObjectName("lbl_total")

        form_imp.addRow("Importe Neto *:", self.spin_neto)
        form_imp.addRow("Alícuota IVA:", self.cmb_alicuota)
        form_imp.addRow("IVA:", self.lbl_iva)
        form_imp.addRow("TOTAL:", self.lbl_total)
        grp_imp.setLayout(two_col(form_imp))
        layout.addWidget(grp_imp)

        # ── Detalle de items (si hay pedido) ──
        self.grp_items = QGroupBox("Detalle de ítems del pedido")
        self.grp_items.setVisible(False)
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        items_lay = QVBoxLayout(self.grp_items)
        self.tbl_items = QTableWidget(0, 4)
        self.tbl_items.setHorizontalHeaderLabels(["Cant.", "Descripción", "P.Unit.", "Subtotal"])
        self.tbl_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_items.setColumnWidth(0, 55); self.tbl_items.setColumnWidth(2, 90); self.tbl_items.setColumnWidth(3, 90)
        self.tbl_items.setMaximumHeight(160)
        self.tbl_items.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_items.verticalHeader().setVisible(False)
        items_lay.addWidget(self.tbl_items)
        layout.addWidget(self.grp_items)

        # ── Observaciones ──
        grp_obs = QGroupBox("Observaciones / Descripción")
        obs_lay = QVBoxLayout(grp_obs)
        self.inp_obs = QTextEdit()
        self.inp_obs.setMaximumHeight(60)
        self.inp_obs.setPlaceholderText("Descripción del servicio o productos facturados...")
        obs_lay.addWidget(self.inp_obs)
        layout.addWidget(grp_obs)

        # Email
        email_lay = QHBoxLayout()
        self.chk_enviar_email = QCheckBox("Enviar por email al cliente")
        self.chk_enviar_email.setChecked(bool(self.cliente and self.cliente.email))
        self.lbl_email_dest = QLabel(
            self.cliente.email if self.cliente and self.cliente.email else "Sin email"
        )
        self.lbl_email_dest.setStyleSheet(f"color: {AppStyles.TEXT_DIM};")
        email_lay.addWidget(self.chk_enviar_email)
        email_lay.addWidget(self.lbl_email_dest)
        email_lay.addStretch()
        layout.addLayout(email_lay)

        # Botones
        btn_row = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        self.btn_emitir = QPushButton("🧾  Emitir Factura ARCA")
        self.btn_emitir.setObjectName("btn_primary")
        self.btn_emitir.clicked.connect(self._emitir)
        btn_row.addWidget(btn_cancelar)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_emitir)
        layout.addLayout(btn_row)

    # ── Pre-carga ──────────────────────────────────────────────────────────

    def _pre_cargar(self) -> None:
        """Llena el formulario con datos del pedido y cliente."""
        if self.cliente:
            self.inp_razon.setText(self.cliente.nombre)
            self.inp_cuit_r.setText(self.cliente.cuit or "")
            self.inp_dom_r.setText(self.cliente.direccion or "")

        if self.pedido:
            self.spin_neto.setValue(self.pedido.total)
            obs = f"Pedido N° {self.pedido.nro_pedido}"
            if self.pedido.observaciones:
                obs += f" — {self.pedido.observaciones}"
            self.inp_obs.setPlainText(obs)

        elif self.pago:
            self.spin_neto.setValue(self.pago.monto)

        self._recalcular()
        self._cargar_items_pedido()

    def _cargar_items_pedido(self) -> None:
        """Muestra la tabla de items si hay pedido asociado."""
        if not self.pedido:
            self.grp_items.setVisible(False)
            return
        try:
            from network.data_provider import get_provider
            from utils.helpers import fmt_moneda
            from PySide6.QtWidgets import QTableWidgetItem
            items = get_provider().detalle.get_by_pedido(self.pedido.id)
            if not items:
                self.grp_items.setVisible(False)
                return
            self.grp_items.setVisible(True)
            self.tbl_items.setRowCount(0)
            for item in items:
                row = self.tbl_items.rowCount(); self.tbl_items.insertRow(row)
                for col, txt in enumerate([str(item.cantidad), item.descripcion,
                                            fmt_moneda(item.precio_unitario), fmt_moneda(item.subtotal)]):
                    it = QTableWidgetItem(txt)
                    it.setTextAlignment(0x0082 if col > 1 else 0x0084)
                    self.tbl_items.setItem(row, col, it)
                self.tbl_items.setRowHeight(row, 26)
        except Exception:
            self.grp_items.setVisible(False)

    def _on_tipo_cambiado(self) -> None:
        tipo = self.cmb_tipo.currentData()
        # Factura C no discrimina IVA
        if tipo == cfgwsfe.TIPO_CBTE_FACTURA_C:
            self.cmb_alicuota.setCurrentIndex(3)  # No aplica
            self.cmb_alicuota.setEnabled(False)
        else:
            self.cmb_alicuota.setEnabled(True)
        self._recalcular()

    def _recalcular(self) -> None:
        neto  = self.spin_neto.value()
        tipo  = self.cmb_tipo.currentData()
        alic  = self.cmb_alicuota.currentData()

        if tipo == cfgwsfe.TIPO_CBTE_FACTURA_C or alic == cfgwsfe.IVA_0_PORCIENTO:
            iva = 0.0
        elif alic == cfgwsfe.IVA_21_PORCIENTO:
            iva = round(neto * 0.21, 2)
        elif alic == cfgwsfe.IVA_10_5_PORCIENTO:
            iva = round(neto * 0.105, 2)
        else:
            iva = 0.0

        total = round(neto + iva, 2)
        self.lbl_iva.setText(fmt_moneda(iva))
        self.lbl_total.setText(fmt_moneda(total))

    # ── Validación ────────────────────────────────────────────────────────

    def _validar(self) -> list[str]:
        errores = []
        cfg = self.config.get_datos_imprenta()
        if not cfg.get("cuit"):
            errores.append("CUIT del emisor no configurado (Configuración → Datos de la Imprenta)")
        if not cfg.get("razon_social"):
            errores.append("Razón Social del emisor no configurada")
        if not cfg.get("domicilio_fiscal") and not cfg.get("direccion"):
            errores.append("Domicilio fiscal del emisor no configurado")
        if not self.afip_ctrl.certificados_existen():
            errores.append("Certificados AFIP no encontrados (Configuración → AFIP)")
        if not self.inp_razon.text().strip():
            errores.append("Razón Social del receptor es obligatoria")
        if self.spin_neto.value() <= 0:
            errores.append("El importe neto debe ser mayor a 0")
        tipo = self.cmb_tipo.currentData()
        if tipo == cfgwsfe.TIPO_CBTE_FACTURA_A and not self.inp_cuit_r.text().strip():
            errores.append("CUIT del receptor es obligatorio para Factura A")
        return errores

    # ── Emisión ───────────────────────────────────────────────────────────

    def _emitir(self) -> None:
        errores = self._validar()
        if errores:
            QMessageBox.warning(self, "Datos incompletos",
                "Corregí los siguientes campos antes de emitir:\n\n• " +
                "\n• ".join(errores))
            return

        neto   = self.spin_neto.value()
        tipo   = self.cmb_tipo.currentData()
        alic   = self.cmb_alicuota.currentData()
        iva    = 0.0
        if tipo != cfgwsfe.TIPO_CBTE_FACTURA_C and alic != cfgwsfe.IVA_0_PORCIENTO:
            iva = round(neto * (0.21 if alic == cfgwsfe.IVA_21_PORCIENTO else 0.105), 2)
        total = round(neto + iva, 2)

        cuit_r_raw = self.inp_cuit_r.text().strip().replace("-", "")
        if cuit_r_raw:
            tipo_doc = cfgwsfe.DOC_TIPO_CUIT
            nro_doc  = int(cuit_r_raw)
        else:
            tipo_doc = cfgwsfe.DOC_TIPO_CONSUMIDOR_FINAL
            nro_doc  = 0

        datos_afip = {
            "tipo_cbte":      tipo,
            "concepto":       self.cmb_concepto.currentData(),
            "tipo_doc":       tipo_doc,
            "nro_doc":        nro_doc,
            "importe_neto":   neto,
            "iva_porcentaje": alic,
            "fecha_cbte":     self.date_emision.date().toString("yyyyMMdd"),
        }

        # Guardar borrador en DB antes de llamar AFIP
        usuario = UsuarioModel.usuario_actual()
        factura = Factura(
            pedido_id=self.pedido.id if self.pedido else None,
            pago_id=self.pago.id if self.pago else None,
            cliente_id=self.cliente.id if self.cliente else 0,
            usuario_id=usuario.id if usuario else None,
            tipo_cbte=tipo,
            punto_venta=self.afip_ctrl.get_punto_venta(),
            fecha_emision=self.date_emision.date().toString("yyyy-MM-dd"),
            cuit_receptor=self.inp_cuit_r.text().strip(),
            razon_receptor=self.inp_razon.text().strip(),
            domicilio_receptor=self.inp_dom_r.text().strip(),
            importe_neto=neto,
            importe_iva=iva,
            importe_total=total,
            alicuota_iva=alic,
            concepto=self.cmb_concepto.currentData(),
            estado="pendiente",
            observaciones=self.inp_obs.toPlainText().strip(),
        )
        self._factura_id = self.factura_model.insertar(factura)

        # Progreso
        self.btn_emitir.setEnabled(False)
        prog = QProgressDialog("Comunicando con ARCA...", None, 0, 0, self)
        prog.setWindowTitle("Espera...")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()

        # Llamada AFIP (bloqueante simple — no vale la pena thread para pocos usuarios)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        resultado = self.afip_ctrl.emitir_factura(datos_afip)
        prog.close()
        self.btn_emitir.setEnabled(True)

        if not resultado["success"]:
            self.factura_model.actualizar_cae(
                self._factura_id, "", "", "", "rechazada"
            )
            QMessageBox.critical(self, "Error ARCA", resultado["message"])
            return

        # Éxito: guardar CAE
        nro_cbte = str(resultado["numero"])
        cae      = resultado["cae"]
        cae_vto  = resultado["vencimiento_cae"]
        pv_fmt   = str(self.afip_ctrl.get_punto_venta()).zfill(4)
        nro_fmt  = nro_cbte.zfill(8)
        nro_factura = f"{pv_fmt}-{nro_fmt}"

        self.factura_model.actualizar_cae(
            self._factura_id, nro_factura, cae, cae_vto, "autorizada"
        )

        # Generar PDF
        self._generar_y_abrir_pdf(nro_factura, cae, cae_vto, neto, iva, total)

        # Email
        if self.chk_enviar_email.isChecked() and self.cliente and self.cliente.email:
            self._enviar_email(nro_factura, cae, total)

        # Log de factura
        try:
            from models.pedido_log_model import PedidoLogModel
            if self.pedido:
                PedidoLogModel().registrar_factura(self.pedido.id, nro_factura, cae)
        except Exception:
            pass

        QMessageBox.information(self, "✅  Factura Autorizada",
            f"Factura N° {nro_factura} autorizada por ARCA.\n"
            f"CAE: {cae}\nVto. CAE: {cae_vto}")
        self.accept()

    def _generar_y_abrir_pdf(self, nro, cae, cae_vto, neto, iva, total) -> None:
        try:
            from utils.pdf_factura import generar_factura_pdf
            from db.database import DatabaseManager
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            factura_upd = self.factura_model.get_by_id(self._factura_id)
            config_imp  = self.config.get_datos_imprenta()
            db_mgr      = DatabaseManager()
            out = str(db_mgr.presupuestos_dir / f"factura_{nro.replace('-','_')}.pdf")
            self._pdf_path = out
            generar_factura_pdf(factura_upd, config_imp, out)
            QDesktopServices.openUrl(QUrl.fromLocalFile(out))
        except Exception as e:
            QMessageBox.warning(self, "PDF", f"No se pudo generar el PDF: {e}")

    def _enviar_email(self, nro: str, cae: str, total: float) -> None:
        try:
            from utils.email_helper import enviar_email, cuerpo_factura
            asunto = (f"Factura N° {nro} — "
                      f"{self.config.get('razon_social','Imprenta')}")
            cuerpo = cuerpo_factura(
                self.config.get("razon_social", ""),
                nro, cae, fmt_moneda(total),
                self.cliente.nombre if self.cliente else "",
            )
            res = enviar_email(
                destinatario=self.cliente.email,
                asunto=asunto,
                cuerpo_html=cuerpo,
                pdf_path=self._pdf_path,
                nombre_adjunto=f"factura_{nro.replace('-','_')}.pdf",
            )
            if res["success"]:
                self.factura_model.marcar_email_enviado(self._factura_id)
                # Log email
                try:
                    from models.pedido_log_model import PedidoLogModel
                    if self.pedido:
                        PedidoLogModel().registrar_email(
                            self.pedido.id, self.cliente.email, asunto)
                except Exception:
                    pass
            else:
                QMessageBox.warning(self, "Email", f"No se pudo enviar el email:\n{res['message']}")
        except Exception as e:
            QMessageBox.warning(self, "Email", str(e))
