"""
Diálogo para emitir recibo de pago simple (sin ARCA).
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QDoubleSpinBox,
    QDateEdit, QTextEdit, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, QDate

from models.factura_model import ReciboModel, Recibo
from models.config_model import ConfigModel
from models.usuario_model import UsuarioModel
from utils.helpers import fmt_moneda, hoy_str
from utils.styles import AppStyles
from network.data_provider import get_provider


class DialogoRecibo(QDialog):
    """Genera recibo de pago y opcionalmente lo envía por email."""

    def __init__(self, pedido=None, pago=None, cliente=None, parent=None):
        super().__init__(parent)
        self.pedido  = pedido
        self.pago    = pago
        self.cliente = cliente
        self.config  = get_provider().config
        self.model   = get_provider().recibos
        self._pdf_path: str = ""
        self._recibo_id: int = 0
        self.setWindowTitle("Emitir Recibo de Pago")
        self.setMinimumWidth(440)
        self.setModal(True)
        self._build_ui()
        self._pre_cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        titulo = QLabel("🧾  Recibo de Pago")
        titulo.setObjectName("lbl_header")
        layout.addWidget(titulo)

        form = QFormLayout()
        form.setSpacing(10)

        self.date_fecha = QDateEdit(QDate.currentDate())
        self.date_fecha.setCalendarPopup(True)
        self.date_fecha.setDisplayFormat("dd/MM/yyyy")

        self.lbl_cliente = QLabel("")
        self.lbl_cliente.setStyleSheet("font-weight: bold;")

        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setRange(0.01, 9_999_999)
        self.spin_monto.setDecimals(2)
        self.spin_monto.setPrefix("$ ")

        self.cmb_metodo = QComboBox()
        self.cmb_metodo.addItems(["Efectivo", "Transferencia", "Mercado Pago",
                                   "Tarjeta Débito", "Tarjeta Crédito", "Cheque"])

        self.inp_concepto = QLineEdit()
        self.inp_concepto.setPlaceholderText("Ej: Pago pedido N° 2026-0001")

        form.addRow("Fecha:", self.date_fecha)
        form.addRow("Cliente:", self.lbl_cliente)
        form.addRow("Monto *:", self.spin_monto)
        form.addRow("Método:", self.cmb_metodo)
        form.addRow("Concepto:", self.inp_concepto)
        layout.addLayout(form)

        # Email
        email_lay = QHBoxLayout()
        self.chk_email = QCheckBox("Enviar por email")
        self.chk_email.setChecked(bool(self.cliente and self.cliente.email))
        self.lbl_email = QLabel(
            self.cliente.email if self.cliente and self.cliente.email else "Sin email"
        )
        self.lbl_email.setStyleSheet(f"color: {AppStyles.TEXT_DIM};")
        email_lay.addWidget(self.chk_email)
        email_lay.addWidget(self.lbl_email)
        email_lay.addStretch()
        layout.addLayout(email_lay)

        btn_row = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_emitir = QPushButton("🖨️  Emitir Recibo")
        btn_emitir.setObjectName("btn_primary")
        btn_emitir.clicked.connect(self._emitir)
        btn_row.addWidget(btn_cancelar)
        btn_row.addStretch()
        btn_row.addWidget(btn_emitir)
        layout.addLayout(btn_row)

    def _pre_cargar(self) -> None:
        if self.cliente:
            self.lbl_cliente.setText(self.cliente.nombre)
        if self.pago:
            self.spin_monto.setValue(self.pago.monto)
            self.cmb_metodo.setCurrentText(self.pago.metodo or "Efectivo")
        if self.pedido:
            self.inp_concepto.setText(f"Pago pedido N° {self.pedido.nro_pedido}")

    def _emitir(self) -> None:
        if not self.cliente:
            QMessageBox.warning(self, "Error", "No hay cliente asociado.")
            return
        monto = self.spin_monto.value()
        if monto <= 0:
            QMessageBox.warning(self, "Error", "El monto debe ser mayor a 0.")
            return

        usuario = UsuarioModel.usuario_actual()
        nro = self.model.generar_nro()
        recibo = Recibo(
            pedido_id=self.pedido.id if self.pedido else None,
            pago_id=self.pago.id if self.pago else None,
            cliente_id=self.cliente.id,
            usuario_id=usuario.id if usuario else None,
            nro_recibo=nro,
            fecha=self.date_fecha.date().toString("yyyy-MM-dd"),
            monto=monto,
            metodo=self.cmb_metodo.currentText(),
            concepto=self.inp_concepto.text().strip(),
            nro_pedido=self.pedido.nro_pedido if self.pedido else "",
        )
        self._recibo_id = self.model.insertar(recibo)
        if not self._recibo_id:
            QMessageBox.critical(self, "Error", "No se pudo guardar el recibo.")
            return

        # Generar PDF
        self._generar_pdf(recibo, nro)

        # Email
        if self.chk_email.isChecked() and self.cliente.email:
            self._enviar_email(recibo, nro)

        # Log de recibo
        try:
            from models.pedido_log_model import PedidoLogModel
            if self.pedido:
                PedidoLogModel().registrar_recibo(self.pedido.id, nro, monto)
        except Exception:
            pass

        QMessageBox.information(self, "✅  Recibo Emitido", f"Recibo N° {nro} generado.")
        self.accept()

    def _generar_pdf(self, recibo: Recibo, nro: str) -> None:
        try:
            from utils.pdf_factura import generar_recibo_pdf
            from db.database import DatabaseManager
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            config_imp = self.config.get_datos_imprenta()
            db_mgr     = DatabaseManager()
            out = str(db_mgr.presupuestos_dir / f"recibo_{nro.replace('-','_')}.pdf")
            self._pdf_path = out
            # Actualizar el path en DB
            from PySide6.QtSql import QSqlQuery
            from db.database import DatabaseManager as DM
            q = QSqlQuery(DM.get_db())
            q.prepare("UPDATE recibos SET pdf_path=:p WHERE id=:id")
            q.bindValue(":p", out)
            q.bindValue(":id", self._recibo_id)
            q.exec()
            generar_recibo_pdf(recibo, config_imp, self.cliente.nombre, out)
            QDesktopServices.openUrl(QUrl.fromLocalFile(out))
        except Exception as e:
            QMessageBox.warning(self, "PDF", str(e))

    def _enviar_email(self, recibo: Recibo, nro: str) -> None:
        try:
            from utils.email_helper import enviar_email, cuerpo_recibo
            res = enviar_email(
                destinatario=self.cliente.email,
                asunto=f"Recibo N° {nro} — {self.config.get('razon_social','')}",
                cuerpo_html=cuerpo_recibo(
                    self.config.get("razon_social", ""),
                    nro, fmt_moneda(recibo.monto),
                    recibo.metodo, self.cliente.nombre,
                ),
                pdf_path=self._pdf_path,
                nombre_adjunto=f"recibo_{nro.replace('-','_')}.pdf",
            )
            if res["success"]:
                self.model.marcar_email(self._recibo_id)
                try:
                    from models.pedido_log_model import PedidoLogModel
                    if self.pedido:
                        PedidoLogModel().registrar_email(
                            self.pedido.id, self.cliente.email,
                            f"Recibo N° {nro}")
                except Exception:
                    pass
            else:
                QMessageBox.warning(self, "Email", res["message"])
        except Exception as e:
            QMessageBox.warning(self, "Email", str(e))
