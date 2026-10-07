"""
Tab 3: Cuenta Corriente — facturas ARCA, recibos, trazabilidad y buscadores.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QHeaderView, QAbstractItemView,
    QCompleter, QMessageBox, QTabWidget, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from models.cliente_model import ClienteModel
from models.pedido_model import PedidoModel
from models.models import PagoModel
from models.factura_model import FacturaModel, ReciboModel
from controllers.reporte_controller import ReporteController
from utils.helpers import fmt_moneda, fmt_fecha, abrir_whatsapp_resumen
from utils.styles import AppStyles
from network.data_provider import get_provider

C_FECHA=0; C_NRO=1; C_CLI_P=2; C_ESTADO=3; C_TOTAL=4; C_SENA=5; C_PAGADO=6; C_SALDO=7; C_FACTURA=8
CF_NRO=0; CF_FECHA=1; CF_CLI=2; CF_TIPO=3; CF_TOTAL=4; CF_CAE=5; CF_EST=6; CF_EMAIL=7
CR_NRO=0; CR_FECHA=1; CR_CLI=2; CR_MONTO=3; CR_MET=4; CR_EMAIL=5


class TabCuentaCorriente(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cliente_model = get_provider().clientes
        self.pedido_model  = get_provider().pedidos
        self.pago_model    = get_provider().pagos
        self.factura_model = get_provider().facturas
        self.recibo_model  = get_provider().recibos
        self.reporte_ctrl  = get_provider().reportes
        self._cliente_id: int = 0
        self._pedidos: list[dict] = []
        self._facturas = []
        self._recibos  = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Cliente:"))
        self.cmb_cliente = QComboBox()
        self.cmb_cliente.setEditable(True)
        self.cmb_cliente.setMinimumWidth(260)
        self._cargar_clientes()
        self.cmb_cliente.currentIndexChanged.connect(self._on_cliente)
        hdr.addWidget(self.cmb_cliente)
        self.lbl_saldo = QLabel("Saldo: $0,00")
        self.lbl_saldo.setStyleSheet("font-size:13pt;font-weight:bold;color:#a0a0b0;")
        hdr.addWidget(self.lbl_saldo)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Botones
        btn_row = QHBoxLayout()
        def _btn(txt, cb, obj=None):
            b = QPushButton(txt)
            if obj: b.setObjectName(obj)
            b.clicked.connect(cb)
            btn_row.addWidget(b)
            return b
        _btn("💰  Registrar Pago",    self._registrar_pago,   "btn_success")
        _btn("🧾  Emitir Recibo",     self._emitir_recibo)
        _btn("📋  Factura ARCA",      self._emitir_factura)
        _btn("📋  Ver Pedido",        self._ver_pedido)
        _btn("📱  WhatsApp Resumen",  self._enviar_wa)
        _btn("🖨️  Estado de Cuenta",  self._imprimir_estado_cuenta)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Inner tabs
        self.inner_tabs = QTabWidget()
        self.inner_tabs.addTab(self._tab_pedidos(),   "📦  Pedidos")
        self.inner_tabs.addTab(self._tab_facturas(),  "🧾  Facturas ARCA")
        self.inner_tabs.addTab(self._tab_recibos(),   "📄  Recibos")
        layout.addWidget(self.inner_tabs)

        self.lbl_footer = QLabel("")
        self.lbl_footer.setStyleSheet(f"color:{AppStyles.TEXT_DIM};font-size:9pt;")
        layout.addWidget(self.lbl_footer)

    def _tab_pedidos(self):
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0,6,0,0)
        bus = QHBoxLayout()
        self.inp_bus_ped = QLineEdit(); self.inp_bus_ped.setPlaceholderText("Buscar pedido...")
        self.inp_bus_ped.setFixedWidth(260); self.inp_bus_ped.textChanged.connect(self._fil_ped)
        bus.addWidget(QLabel("Buscar:")); bus.addWidget(self.inp_bus_ped); bus.addStretch()
        lay.addLayout(bus)
        self.tbl_ped = QTableWidget(0,9)
        self.tbl_ped.setHorizontalHeaderLabels(["Fecha","N° Pedido","Cliente","Estado","Total","Seña","Pagado","Saldo","Factura"])
        h = self.tbl_ped.horizontalHeader()
        h.setSectionResizeMode(C_CLI_P, QHeaderView.ResizeMode.Stretch)
        for col,w_ in [(C_FECHA,80),(C_NRO,105),(C_ESTADO,140),(C_TOTAL,90),(C_SENA,80),(C_PAGADO,90),(C_SALDO,90),(C_FACTURA,115)]:
            self.tbl_ped.setColumnWidth(col,w_)
        self.tbl_ped.setAlternatingRowColors(True)
        self.tbl_ped.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_ped.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_ped.verticalHeader().setVisible(False)
        self.tbl_ped.doubleClicked.connect(self._ver_pedido)
        self.tbl_ped.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl_ped.customContextMenuRequested.connect(self._ctx_pedidos)
        lay.addWidget(self.tbl_ped)
        return w

    def _tab_facturas(self):
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0,6,0,0)
        bus = QHBoxLayout()
        self.inp_bus_fac = QLineEdit(); self.inp_bus_fac.setPlaceholderText("Buscar factura/CAE...")
        self.inp_bus_fac.setFixedWidth(260); self.inp_bus_fac.textChanged.connect(self._fil_fac)
        btn_reim = QPushButton("🖨️  Reimprimir PDF"); btn_reim.clicked.connect(self._reimprimir_factura)
        bus.addWidget(QLabel("Buscar:")); bus.addWidget(self.inp_bus_fac); bus.addStretch(); bus.addWidget(btn_reim)
        lay.addLayout(bus)
        self.tbl_fac = QTableWidget(0,8)
        self.tbl_fac.setHorizontalHeaderLabels(["N° Factura","Fecha","Cliente","Tipo","Total","CAE","Estado","Email"])
        hh = self.tbl_fac.horizontalHeader()
        hh.setSectionResizeMode(CF_CLI, QHeaderView.ResizeMode.Stretch)
        for col,w_ in [(CF_NRO,115),(CF_FECHA,85),(CF_TIPO,90),(CF_TOTAL,95),(CF_CAE,130),(CF_EST,85),(CF_EMAIL,55)]:
            self.tbl_fac.setColumnWidth(col,w_)
        self.tbl_fac.setAlternatingRowColors(True)
        self.tbl_fac.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_fac.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_fac.verticalHeader().setVisible(False)
        self.tbl_fac.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl_fac.customContextMenuRequested.connect(self._ctx_facturas)
        lay.addWidget(self.tbl_fac)
        return w

    def _tab_recibos(self):
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0,6,0,0)
        bus = QHBoxLayout()
        self.inp_bus_rec = QLineEdit(); self.inp_bus_rec.setPlaceholderText("Buscar recibo...")
        self.inp_bus_rec.setFixedWidth(260); self.inp_bus_rec.textChanged.connect(self._fil_rec)
        bus.addWidget(QLabel("Buscar:")); bus.addWidget(self.inp_bus_rec); bus.addStretch()
        lay.addLayout(bus)
        self.tbl_rec = QTableWidget(0,6)
        self.tbl_rec.setHorizontalHeaderLabels(["N° Recibo","Fecha","Cliente","Monto","Método","Email"])
        hh = self.tbl_rec.horizontalHeader()
        hh.setSectionResizeMode(CR_CLI, QHeaderView.ResizeMode.Stretch)
        for col,w_ in [(CR_NRO,110),(CR_FECHA,85),(CR_MONTO,95),(CR_MET,110),(CR_EMAIL,55)]:
            self.tbl_rec.setColumnWidth(col,w_)
        self.tbl_rec.setAlternatingRowColors(True)
        self.tbl_rec.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_rec.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_rec.verticalHeader().setVisible(False)
        self.tbl_rec.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl_rec.customContextMenuRequested.connect(self._ctx_recibos)
        lay.addWidget(self.tbl_rec)
        return w

    # ── Carga ──────────────────────────────────────────────────────────────

    def _cargar_clientes(self):
        clientes = self.cliente_model.get_all()
        self.cmb_cliente.clear()
        self.cmb_cliente.addItem("", 0)
        for c in clientes:
            self.cmb_cliente.addItem(c.nombre, c.id)
        comp = QCompleter([c.nombre for c in clientes])
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.cmb_cliente.setCompleter(comp)

    def _on_cliente(self, _):
        self._cliente_id = self.cmb_cliente.currentData() or 0
        self._cargar_datos()

    def _cargar_datos(self):
        if not self._cliente_id:
            self._pedidos  = self.reporte_ctrl.pedidos_cuenta_corriente(0)
            self._facturas = self.factura_model.get_all_facturas()
            self._recibos  = self.recibo_model.get_all_recibos()
        else:
            self._pedidos  = self.reporte_ctrl.pedidos_cuenta_corriente(self._cliente_id)
            self._facturas = self.factura_model.get_by_cliente(self._cliente_id)
            self._recibos  = self.recibo_model.get_by_cliente(self._cliente_id)
        self._poblar_pedidos(self._pedidos)
        self._poblar_facturas(self._facturas)
        self._poblar_recibos(self._recibos)
        self._actualizar_saldo()

    def _actualizar_saldo(self):
        saldo = sum(p["saldo"] for p in self._pedidos)
        total = sum(p["total"] for p in self._pedidos)
        color = AppStyles.DANGER if saldo > 0.01 else AppStyles.SUCCESS
        self.lbl_saldo.setText(f"Saldo: {fmt_moneda(saldo)}")
        self.lbl_saldo.setStyleSheet(f"color:{color};font-size:13pt;font-weight:bold;")
        self.lbl_footer.setText(
            f"Pedidos: {len(self._pedidos)}  |  Facturado: {fmt_moneda(total)}  |  "
            f"Saldo: {fmt_moneda(saldo)}  |  "
            f"Facturas ARCA: {len(self._facturas)}  |  Recibos: {len(self._recibos)}"
        )

    def _poblar_pedidos(self, pedidos):
        fact_map: dict[int, list] = {}
        for f in self._facturas:
            if f.pedido_id:
                if f.pedido_id not in fact_map:
                    fact_map[f.pedido_id] = []
                fact_map[f.pedido_id].append(f)

        def _fact_label(pid):
            fs = fact_map.get(pid, [])
            if not fs: return "—"
            autorizadas = [x for x in fs if x.estado == "autorizada"]
            if len(fs) == 1:
                ico = "✅" if autorizadas else "⏳"
                return f"{ico} {fs[0].nro_factura or 'Pend.'}"
            return f"✅ {len(autorizadas)}/{len(fs)} fact."
        self.tbl_ped.setRowCount(0)
        for p in pedidos:
            row = self.tbl_ped.rowCount(); self.tbl_ped.insertRow(row)
            cli_nombre = p.get("cliente_nombre", "") or ""
            vals = [fmt_fecha(p["fecha"]), p["nro"], cli_nombre, p["estado"],
                    fmt_moneda(p["total"]), fmt_moneda(p["sena"]),
                    fmt_moneda(p["pagado"]), fmt_moneda(p["saldo"]),
                    _fact_label(p["id"])]
            for col, txt in enumerate(vals):
                item = QTableWidgetItem(str(txt))
                item.setData(Qt.ItemDataRole.UserRole, p["id"])
                # Guardar cliente_id en col C_CLI_P para menú contextual
                if col == C_CLI_P:
                    item.setData(Qt.ItemDataRole.UserRole + 1, p.get("cliente_id", 0))
                alin = Qt.AlignmentFlag.AlignVCenter
                if col in (C_TOTAL,C_SENA,C_PAGADO,C_SALDO):
                    alin |= Qt.AlignmentFlag.AlignRight
                elif col in (C_FECHA,C_NRO,C_FACTURA):
                    alin |= Qt.AlignmentFlag.AlignCenter
                else:
                    alin |= Qt.AlignmentFlag.AlignLeft
                item.setTextAlignment(int(alin))
                self.tbl_ped.setItem(row, col, item)
            if p["saldo"] > 0.01:
                it = self.tbl_ped.item(row, C_SALDO)
                if it: it.setForeground(QColor(AppStyles.DANGER))
            self.tbl_ped.setRowHeight(row, 32)

    def _fil_ped(self):
        txt = self.inp_bus_ped.text().lower()
        self._poblar_pedidos([p for p in self._pedidos
            if txt in p["nro"].lower() or txt in p["estado"].lower()
            or txt in p.get("cliente_nombre","").lower()] if txt else self._pedidos)

    def _poblar_facturas(self, facturas):
        TIPOS = {1:"Fact.A", 6:"Fact.B", 11:"Fact.C"}
        self.tbl_fac.setRowCount(0)
        for f in facturas:
            row = self.tbl_fac.rowCount(); self.tbl_fac.insertRow(row)
            vals = [f.nro_factura or "(pend.)", fmt_fecha(f.fecha_emision),
                    f.cliente_nombre or "",
                    TIPOS.get(f.tipo_cbte, str(f.tipo_cbte)),
                    fmt_moneda(f.importe_total), f.cae or "—",
                    f.estado, "✅" if f.email_enviado else "—"]
            for col, txt in enumerate(vals):
                item = QTableWidgetItem(str(txt))
                item.setData(Qt.ItemDataRole.UserRole, f.id)
                item.setData(Qt.ItemDataRole.UserRole+1, f.cliente_id)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col in (CF_CLI, CF_CAE):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if col == CF_TOTAL:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_fac.setItem(row, col, item)
            color = {"autorizada": AppStyles.SUCCESS, "rechazada": AppStyles.DANGER,
                     "error": AppStyles.DANGER}.get(f.estado, AppStyles.TEXT_DIM)
            it = self.tbl_fac.item(row, CF_EST)
            if it: it.setForeground(QColor(color))
            self.tbl_fac.setRowHeight(row, 32)

    def _fil_fac(self):
        txt = self.inp_bus_fac.text().lower()
        self._poblar_facturas([f for f in self._facturas
            if txt in (f.nro_factura or "").lower() or txt in (f.cae or "").lower()
            or txt in (f.cliente_nombre or "").lower()] if txt else self._facturas)

    def _poblar_recibos(self, recibos):
        self.tbl_rec.setRowCount(0)
        for r in recibos:
            row = self.tbl_rec.rowCount(); self.tbl_rec.insertRow(row)
            vals = [r.nro_recibo, fmt_fecha(r.fecha), r.cliente_nombre or "",
                    fmt_moneda(r.monto), r.metodo, "✅" if r.email_enviado else "—"]
            for col, txt in enumerate(vals):
                item = QTableWidgetItem(str(txt))
                item.setData(Qt.ItemDataRole.UserRole, r.id)
                item.setData(Qt.ItemDataRole.UserRole+1, r.cliente_id)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == CR_CLI:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if col == CR_MONTO:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_rec.setItem(row, col, item)
            self.tbl_rec.setRowHeight(row, 32)

    def _fil_rec(self):
        txt = self.inp_bus_rec.text().lower()
        self._poblar_recibos([r for r in self._recibos
            if txt in r.nro_recibo.lower()
            or txt in (r.cliente_nombre or "").lower()] if txt else self._recibos)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _ped_sel(self):
        row = self.tbl_ped.currentRow()
        if row < 0: return None
        it = self.tbl_ped.item(row, C_NRO)
        if not it: return None
        pid = it.data(Qt.ItemDataRole.UserRole)
        return next((p for p in self._pedidos if p["id"] == pid), None)

    def _get_cliente_de_fila_pedido(self, row=-1):
        """
        Obtiene el cliente de la fila actual de la tabla de pedidos.
        Prioriza: cliente_id en el dict del pedido > UserRole+1 > combo global.
        """
        # 1. Intentar desde el dict _pedidos que ahora incluye cliente_id
        p = self._ped_sel()
        if p and p.get("cliente_id"):
            return self.cliente_model.get_by_id(p["cliente_id"])
        # 2. Intentar desde UserRole+1 en la celda
        if row >= 0:
            it = self.tbl_ped.item(row, C_CLI_P)
            if it:
                cid = it.data(Qt.ItemDataRole.UserRole + 1)
                if cid:
                    return self.cliente_model.get_by_id(cid)
        # 3. Fallback al combo global
        return self._get_cliente()

    def _get_cliente_de_fila_factura(self, row):
        it = self.tbl_fac.item(row, CF_CLI)
        if it:
            cid = it.data(Qt.ItemDataRole.UserRole + 1)
            if cid:
                return self.cliente_model.get_by_id(cid)
        return self._get_cliente()

    def _get_cliente_de_fila_recibo(self, row):
        it = self.tbl_rec.item(row, CR_CLI)
        if it:
            cid = it.data(Qt.ItemDataRole.UserRole + 1)
            if cid:
                return self.cliente_model.get_by_id(cid)
        return self._get_cliente()

    def _fac_sel(self):
        row = self.tbl_fac.currentRow()
        if row < 0: return None
        it = self.tbl_fac.item(row, CF_NRO)
        if not it: return None
        return self.factura_model.get_by_id(it.data(Qt.ItemDataRole.UserRole))

    def _get_cliente(self):
        return self.cliente_model.get_by_id(self._cliente_id) if self._cliente_id else None

    # ── Acciones ──────────────────────────────────────────────────────────

    def _registrar_pago(self):
        p = self._ped_sel()
        if not p:
            QMessageBox.information(self, "Info", "Seleccioná un pedido."); return
        if p["saldo"] <= 0:
            QMessageBox.information(self, "Sin saldo", "Pedido ya saldado."); return
        from views.dialogs.dialogo_pago import DialogoPago
        if DialogoPago(p["id"], p["saldo"], self).exec():
            self._cargar_datos()

    def _emitir_recibo(self):
        from views.dialogs.dialogo_recibo import DialogoRecibo
        p       = self._ped_sel()
        cliente = self._get_cliente_de_fila_pedido()
        if not cliente:
            QMessageBox.information(self, "Info",
                "Seleccioná un pedido primero para determinar el cliente."); return
        pedido_obj = self.pedido_model.get_by_id(p["id"]) if p else None
        pago_obj = None
        if pedido_obj:
            pagos = self.pago_model.get_by_pedido(pedido_obj.id)
            if pagos: pago_obj = pagos[0]
        if DialogoRecibo(pedido=pedido_obj, pago=pago_obj, cliente=cliente, parent=self).exec():
            self._cargar_datos()

    def _emitir_factura(self):
        from views.dialogs.dialogo_factura import DialogoEmitirFactura
        p       = self._ped_sel()
        cliente = self._get_cliente_de_fila_pedido()
        if not cliente:
            QMessageBox.information(self, "Info",
                "Seleccioná un pedido primero para determinar el cliente."); return
        pedido_obj = self.pedido_model.get_by_id(p["id"]) if p else None
        if DialogoEmitirFactura(pedido=pedido_obj, cliente=cliente, parent=self).exec():
            self._cargar_datos()
            self.inner_tabs.setCurrentIndex(1)

    def _ver_pedido(self):
        p = self._ped_sel()
        if not p:
            QMessageBox.information(self, "Info", "Seleccioná un pedido."); return
        from views.dialogs.dialogo_pedido import DialogoPedido
        if DialogoPedido(pedido_id=p["id"], parent=self).exec():
            self._cargar_datos()

    def _reimprimir_factura(self):
        f = self._fac_sel()
        if not f:
            QMessageBox.information(self, "Info", "Seleccioná una factura."); return
        try:
            from utils.pdf_factura import generar_factura_pdf
            from db.database import DatabaseManager
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            cfg = get_provider().config.get_datos_imprenta()
            nro = (f.nro_factura or f"id_{f.id}").replace("-","_")
            out = str(DatabaseManager().presupuestos_dir / f"factura_{nro}.pdf")
            generar_factura_pdf(f, cfg, out)
            QDesktopServices.openUrl(QUrl.fromLocalFile(out))
        except Exception as e:
            QMessageBox.warning(self, "Error PDF", str(e))

    def _enviar_wa(self):
        if not self._cliente_id:
            QMessageBox.information(self, "Info", "Seleccioná un cliente."); return
        cliente = self._get_cliente()
        saldo   = sum(p["saldo"] for p in self._pedidos)
        resumen = [{"nro": p["nro"], "saldo": p["saldo"]} for p in self._pedidos if p["saldo"] > 0]
        if not abrir_whatsapp_resumen(cliente.nombre, cliente.whatsapp, saldo, resumen):
            QMessageBox.warning(self, "WhatsApp", "Cliente sin WhatsApp registrado.")

    def _imprimir_estado_cuenta(self):
        if not self._cliente_id:
            QMessageBox.information(self, "Info", "Seleccioná un cliente."); return
        try:
            from utils.pdf_generator import generar_estado_cuenta
            from db.database import DatabaseManager
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            from utils.helpers import hoy_str
            cliente   = self._get_cliente()
            pedidos   = [self.pedido_model.get_by_id(p["id"]) for p in self._pedidos]
            pm        = get_provider().pagos
            pagos_map = {p.id: pm.get_by_pedido(p.id) for p in pedidos}
            saldo     = sum(p["saldo"] for p in self._pedidos)
            out = str(DatabaseManager().presupuestos_dir /
                      f"cuenta_{cliente.nombre.replace(' ','_')}_{hoy_str()}.pdf")
            generar_estado_cuenta(cliente, pedidos, pagos_map, saldo, out)
            QDesktopServices.openUrl(QUrl.fromLocalFile(out))
        except Exception as e:
            QMessageBox.warning(self, "Error PDF", str(e))

    def _ctx_pedidos(self, pos):
        row = self.tbl_ped.rowAt(pos.y())
        if row < 0: return
        it = self.tbl_ped.item(row, C_NRO)
        if not it: return
        self.tbl_ped.selectRow(row)
        it_estado = self.tbl_ped.item(row, C_ESTADO)
        estado_actual = it_estado.text() if it_estado else ""
        estados_facturables = {"Cobrado", "Entregado", "Pendiente de Cobro"}
        puede_facturar = estado_actual in estados_facturables
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        m.addAction("✏️  Ver / Editar pedido",   lambda: self._ver_pedido())
        m.addAction("💰  Registrar pago",        lambda: self._registrar_pago())
        act_fac = m.addAction("🧾  Emitir Factura ARCA", lambda: self._emitir_factura())
        if not puede_facturar:
            act_fac.setEnabled(False)
            act_fac.setToolTip(f"Solo disponible en: {', '.join(sorted(estados_facturables))}")
        m.addAction("📄  Emitir Recibo",         lambda: self._emitir_recibo())
        m.exec(self.tbl_ped.viewport().mapToGlobal(pos))

    def _ctx_facturas(self, pos):
        row = self.tbl_fac.rowAt(pos.y())
        if row < 0: return
        it = self.tbl_fac.item(row, CF_NRO)
        if not it: return
        self.tbl_fac.selectRow(row)
        fid = it.data(Qt.ItemDataRole.UserRole)
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        m.addAction("🖨️  Ver PDF factura",     lambda: self._reimprimir_factura())
        m.addAction("📧  Enviar por email",    lambda: self._email_factura(fid, row))
        m.exec(self.tbl_fac.viewport().mapToGlobal(pos))

    def _email_factura(self, fid, row=None):
        f = self.factura_model.get_by_id(fid)
        if not f:
            return
        cliente = (self._get_cliente_de_fila_factura(row) if row is not None
                   else self.cliente_model.get_by_id(f.cliente_id))
        if not cliente or not cliente.email:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Sin email", "El cliente no tiene email registrado.")
            return
        try:
            from utils.pdf_factura import generar_factura_pdf
            from models.config_model import ConfigModel
            from db.database import DatabaseManager
            from utils.email_helper import enviar_email, cuerpo_factura
            from utils.helpers import fmt_moneda, hoy_str
            cfg = ConfigModel().get_datos_imprenta()
            nro = (f.nro_factura or f"id_{f.id}").replace("-","_")
            out = str(DatabaseManager().presupuestos_dir / f"factura_{nro}.pdf")
            generar_factura_pdf(f, cfg, out)
            res = enviar_email(
                destinatario=cliente.email,
                asunto=f"Factura N° {f.nro_factura or nro}",
                cuerpo_html=cuerpo_factura(cfg.get("razon_social",""), f.nro_factura or nro,
                    f.cae or "", fmt_moneda(f.importe_total), cliente.nombre),
                pdf_path=out,
                nombre_adjunto=f"factura_{nro}.pdf",
            )
            from PySide6.QtWidgets import QMessageBox
            if res["success"]:
                from models.factura_model import FacturaModel
                FacturaModel().marcar_email_enviado(fid)
                QMessageBox.information(self, "Email enviado", res["message"])
                self._cargar_datos()
            else:
                QMessageBox.warning(self, "Error email", res["message"])
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", str(e))

    def _ctx_recibos(self, pos):
        row = self.tbl_rec.rowAt(pos.y())
        if row < 0: return
        it = self.tbl_rec.item(row, CR_NRO)
        if not it: return
        self.tbl_rec.selectRow(row)
        rid = it.data(Qt.ItemDataRole.UserRole)
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        m.addAction("🖨️  Ver PDF recibo",    lambda: self._ver_recibo_pdf(rid))
        m.addAction("📧  Enviar por email",  lambda: self._email_recibo(rid, row))
        m.exec(self.tbl_rec.viewport().mapToGlobal(pos))

    def _ver_recibo_pdf(self, rid):
        r = next((x for x in self._recibos if x.id == rid), None)
        if r and r.pdf_path:
            from PySide6.QtCore import QUrl; from PySide6.QtGui import QDesktopServices
            import os
            if os.path.exists(r.pdf_path): QDesktopServices.openUrl(QUrl.fromLocalFile(r.pdf_path)); return
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "PDF", "No se encontró el archivo PDF del recibo.")

    def _email_recibo(self, rid, row=None):
        r = next((x for x in self._recibos if x.id == rid), None)
        if not r: return
        cliente = (self._get_cliente_de_fila_recibo(row) if row is not None
                   else self.cliente_model.get_by_id(r.cliente_id))
        if not cliente or not cliente.email:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self,"Sin email","El cliente no tiene email registrado."); return
        try:
            from utils.email_helper import enviar_email, cuerpo_recibo
            from utils.helpers import fmt_moneda
            from models.config_model import ConfigModel
            cfg = ConfigModel().get_datos_imprenta()
            res = enviar_email(
                destinatario=cliente.email,
                asunto=f"Recibo N° {r.nro_recibo}",
                cuerpo_html=cuerpo_recibo(cfg.get("razon_social",""), r.nro_recibo,
                    fmt_moneda(r.monto), r.metodo, cliente.nombre),
                pdf_path=r.pdf_path or None,
                nombre_adjunto=f"recibo_{r.nro_recibo}.pdf",
            )
            from PySide6.QtWidgets import QMessageBox
            if res["success"]:
                from models.factura_model import ReciboModel
                ReciboModel().marcar_email(rid)
                QMessageBox.information(self,"Email enviado", res["message"])
                self._cargar_datos()
            else:
                QMessageBox.warning(self,"Error email", res["message"])
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self,"Error", str(e))

    def refrescar(self):
        self._cargar_clientes()
        self._cargar_datos()
