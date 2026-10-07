"""
Diálogo registrar pago - con opción de emitir factura ARCA antes de confirmar.
"""
from datetime import date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QDoubleSpinBox, QDateEdit, QMessageBox, QDialogButtonBox,
    QCheckBox, QFrame
)
from PySide6.QtCore import Qt, QDate

from models.models import Pago
from models.pedido_model import PedidoModel
from network.data_provider import get_provider
from utils.helpers import fmt_moneda
from utils.styles import AppStyles


class DialogoPago(QDialog):
    def __init__(self, pedido_id: int, saldo_actual: float, parent=None):
        super().__init__(parent)
        self.pedido_id    = pedido_id
        self.saldo_actual = saldo_actual
        self._factura_emitida = False
        self.setWindowTitle("Registrar Pago")
        self.setMinimumWidth(420)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self); layout.setSpacing(10); layout.setContentsMargins(16,16,16,16)

        titulo = QLabel("💰  Registrar Pago")
        titulo.setObjectName("lbl_header")
        layout.addWidget(titulo)

        pedido = get_provider().pedidos.get_by_id(self.pedido_id)
        if pedido:
            lbl_pedido = QLabel(f"Pedido: <b>{pedido.nro_pedido}</b>  |  Cliente: <b>{pedido.cliente_nombre}</b>")
            layout.addWidget(lbl_pedido)

        lbl_saldo = QLabel(f"Saldo pendiente: {fmt_moneda(self.saldo_actual)}")
        color = AppStyles.DANGER if self.saldo_actual > 0 else AppStyles.SUCCESS
        lbl_saldo.setStyleSheet(f"color:{color};font-weight:bold;font-size:11pt;")
        layout.addWidget(lbl_saldo)

        # Separador
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background:{AppStyles.BORDER};"); layout.addWidget(line)

        form = QFormLayout(); form.setSpacing(10)

        self.date_fecha = QDateEdit(QDate.currentDate())
        self.date_fecha.setCalendarPopup(True)
        self.date_fecha.setDisplayFormat("dd/MM/yyyy")

        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setRange(0.01, 9_999_999)
        self.spin_monto.setDecimals(2); self.spin_monto.setPrefix("$ ")
        self.spin_monto.setValue(self.saldo_actual if self.saldo_actual > 0 else 0)

        self.cmb_metodo = QComboBox()
        self.cmb_metodo.addItems(["Efectivo","Transferencia","Mercado Pago",
                                   "Tarjeta Débito","Tarjeta Crédito","Cheque"])

        self.inp_comprobante = QLineEdit()
        self.inp_comprobante.setPlaceholderText("N° / CBU / alias / comprobante")

        self.inp_factura = QLineEdit()
        self.inp_factura.setPlaceholderText("N° factura (si ya existe)")

        form.addRow("Fecha:", self.date_fecha)
        form.addRow("Monto *:", self.spin_monto)
        form.addRow("Método:", self.cmb_metodo)
        form.addRow("Comprobante:", self.inp_comprobante)
        form.addRow("N° Factura:", self.inp_factura)
        layout.addLayout(form)

        # Opción: emitir factura ARCA en el mismo paso
        factura_frame = QFrame()
        factura_frame.setStyleSheet(
            f"background:{AppStyles.BG_LIGHT};border:1px solid {AppStyles.BORDER};"
            f"border-radius:5px;"
        )
        ff_lay = QVBoxLayout(factura_frame); ff_lay.setContentsMargins(10,8,10,8)
        self.chk_emitir_factura = QCheckBox("🧾  Emitir Factura ARCA al registrar el pago")
        self.chk_emitir_factura.setStyleSheet("font-weight:bold;")
        lbl_hint = QLabel("Se abrirá el formulario de facturación electrónica antes de confirmar.")
        lbl_hint.setStyleSheet(f"color:{AppStyles.TEXT_DIM};font-size:8pt;")
        ff_lay.addWidget(self.chk_emitir_factura)
        ff_lay.addWidget(lbl_hint)
        layout.addWidget(factura_frame)

        # Botones
        btn_row = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar"); btn_cancelar.clicked.connect(self.reject)
        self.btn_guardar = QPushButton("✅  Registrar Pago")
        self.btn_guardar.setObjectName("btn_primary")
        self.btn_guardar.clicked.connect(self._guardar)
        btn_row.addWidget(btn_cancelar); btn_row.addStretch(); btn_row.addWidget(self.btn_guardar)
        layout.addLayout(btn_row)

    def _guardar(self):
        monto = self.spin_monto.value()
        if monto <= 0:
            QMessageBox.warning(self,"Error","El monto debe ser mayor a 0."); return

        if monto > self.saldo_actual + 0.01:
            resp = QMessageBox.question(self,"Monto mayor al saldo",
                f"El monto ({fmt_moneda(monto)}) supera el saldo ({fmt_moneda(self.saldo_actual)}).\n¿Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp == QMessageBox.StandardButton.No: return

        # Si eligió emitir factura, abrirla primero
        if self.chk_emitir_factura.isChecked():
            pedido  = get_provider().pedidos.get_by_id(self.pedido_id)
            cliente = get_provider().clientes.get_by_id(pedido.cliente_id)
            from views.dialogs.dialogo_factura import DialogoEmitirFactura
            dlg_fac = DialogoEmitirFactura(pedido=pedido, cliente=cliente, parent=self)
            # Pre-cargar el monto del pago
            dlg_fac.spin_neto.setValue(monto)
            if dlg_fac.exec():
                self._factura_emitida = True
                # Obtener nro factura emitido y rellenarlo
                facturas = get_provider().facturas.get_by_pedido(self.pedido_id)
                if facturas and facturas[0].nro_factura:
                    self.inp_factura.setText(facturas[0].nro_factura)

        pago = Pago(
            pedido_id=self.pedido_id,
            fecha=self.date_fecha.date().toString("yyyy-MM-dd"),
            monto=monto,
            metodo=self.cmb_metodo.currentText(),
            comprobante=self.inp_comprobante.text().strip(),
            nro_factura=self.inp_factura.text().strip(),
        )
        nuevo_id = get_provider().pagos.insertar(pago)
        if not nuevo_id:
            QMessageBox.critical(self,"Error","No se pudo registrar el pago."); return

        # Si saldo ≤ 0 → Cobrado
        pedido_upd = get_provider().pedidos.get_by_id(self.pedido_id)
        if pedido_upd and pedido_upd.saldo <= 0.01:
            get_provider().pedidos.cambiar_estado(self.pedido_id, "Cobrado")

        # Log de pago
        try:
            from models.pedido_log_model import PedidoLogModel
            PedidoLogModel().registrar_pago(self.pedido_id, monto, self.cmb_metodo.currentText())
        except Exception:
            pass

        self.accept()
