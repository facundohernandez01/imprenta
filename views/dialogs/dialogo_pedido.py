"""
Diálogo Nuevo / Editar Pedido.
El formulario más complejo de la app.
"""
import os
from pathlib import Path
from datetime import date

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCompleter,
    QDoubleSpinBox, QSpinBox, QDateEdit, QTextEdit, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QAbstractItemView, QFrame, QSizePolicy,
    QTabWidget, QWidget, QScrollArea
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QFont

from models.pedido_model import Pedido, ESTADOS_PEDIDO
from models.models import PedidoDetalle, Producto
from models.cliente_model import Cliente
from network.data_provider import get_provider
from utils.helpers import (
    fmt_moneda, hoy_str, abrir_whatsapp_presupuesto,
    validar_requerido
)


# Índices de columnas en la tabla de detalle
COL_CANT   = 0
COL_PROD   = 1
COL_ANCHO  = 2
COL_ALTO   = 3
COL_DESC   = 4
COL_PRECIO = 5
COL_SUB    = 6


class DialogoPedido(QDialog):
    """Diálogo para crear o editar un pedido completo."""

    pedido_guardado = Signal(int)  # emite el ID del pedido guardado

    def __init__(self, pedido_id: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.pedido_id = pedido_id
        self.pedido_model   = get_provider().pedidos
        self.detalle_model  = get_provider().detalle
        self.cliente_model  = get_provider().clientes
        self.producto_model = get_provider().productos

        self._clientes: list[Cliente] = []
        self._productos: list[Producto] = []
        self._cliente_id: int = 0
        self._bloqueando_calculo = False

        self.setWindowTitle("Nuevo Pedido" if not pedido_id else f"Editar Pedido")
        self.setMinimumSize(1050, 720)
        self.setModal(True)

        self._build_ui()
        self._cargar_combos()
        self._setup_shortcuts()

        if pedido_id:
            self._cargar_pedido()
        else:
            self._set_nro_nuevo()
            self.date_creacion.setDate(QDate.currentDate())

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        # QTabWidget principal
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        # Tab 1: Datos del pedido
        tab_datos = QWidget()
        tab_lay = QVBoxLayout(tab_datos)
        tab_lay.setSpacing(10)
        tab_lay.setContentsMargins(8, 8, 8, 8)
        self._tabs.addTab(tab_datos, "📋  Pedido")

        # Tab 2: Historial (se construye después)
        self._tab_historial = QWidget()
        self._tabs.addTab(self._tab_historial, "🕐  Historial")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # === HEADER ===
        header_layout = QHBoxLayout()

        self.lbl_nro = QLabel("Pedido N°: ---")
        self.lbl_nro.setObjectName("lbl_nro_pedido")
        header_layout.addWidget(self.lbl_nro)
        header_layout.addStretch()

        header_layout.addWidget(QLabel("Creación:"))
        self.date_creacion = QDateEdit(QDate.currentDate())
        self.date_creacion.setCalendarPopup(True)
        self.date_creacion.setDisplayFormat("dd/MM/yyyy")
        self.date_creacion.setFixedWidth(120)
        header_layout.addWidget(self.date_creacion)

        header_layout.addWidget(QLabel("Entrega:"))
        self.date_entrega = QDateEdit()
        self.date_entrega.setCalendarPopup(True)
        self.date_entrega.setDisplayFormat("dd/MM/yyyy")
        self.date_entrega.setFixedWidth(120)
        self.date_entrega.setSpecialValueText("Sin fecha")
        self.date_entrega.setDate(QDate.currentDate())
        header_layout.addWidget(self.date_entrega)

        header_layout.addWidget(QLabel("Estado:"))
        self.cmb_estado = QComboBox()
        self.cmb_estado.addItems(ESTADOS_PEDIDO)
        self.cmb_estado.setFixedWidth(160)
        header_layout.addWidget(self.cmb_estado)

        tab_lay.addLayout(header_layout)

        # === CLIENTE ===
        grp_cliente = QGroupBox("Cliente")
        cli_lay = QHBoxLayout(grp_cliente)

        self.cmb_cliente = QComboBox()
        self.cmb_cliente.setEditable(True)
        self.cmb_cliente.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.cmb_cliente.setMinimumWidth(280)
        self.cmb_cliente.setPlaceholderText("Buscar o crear cliente...")
        self.cmb_cliente.currentIndexChanged.connect(self._on_cliente_cambiado)
        self.cmb_cliente.editTextChanged.connect(self._on_cliente_texto_cambiado)
        cli_lay.addWidget(self.cmb_cliente, stretch=1)

        btn_nuevo_cliente = QPushButton("➕  Nuevo")
        btn_nuevo_cliente.setToolTip("Dar de alta un cliente sin salir del pedido (Atajo: Ctrl+M)")
        btn_nuevo_cliente.setShortcut("Ctrl+M")
        btn_nuevo_cliente.clicked.connect(self._nuevo_cliente_inline)
        cli_lay.addWidget(btn_nuevo_cliente)

        btn_ver_cliente = QPushButton("👤  Ver/Editar")
        btn_ver_cliente.clicked.connect(self._ver_cliente)
        cli_lay.addWidget(btn_ver_cliente)

        self.lbl_saldo_cli = QLabel("")
        self.lbl_saldo_cli.setObjectName("lbl_saldo_rojo")
        cli_lay.addWidget(self.lbl_saldo_cli)
        cli_lay.addStretch()
        tab_lay.addWidget(grp_cliente)

        # === DETALLE ===
        grp_det = QGroupBox("Detalle del pedido")
        det_lay = QVBoxLayout(grp_det)

        # Toolbar de la tabla
        det_toolbar = QHBoxLayout()
        btn_add_linea = QPushButton("➕  Agregar línea")
        btn_add_linea.clicked.connect(self._agregar_linea)
        btn_del_linea = QPushButton("➖  Eliminar seleccionada")
        btn_del_linea.setObjectName("btn_danger")
        btn_del_linea.clicked.connect(self._eliminar_linea_seleccionada)
        btn_nuevo_prod = QPushButton("📦  Nuevo Producto")
        btn_nuevo_prod.setToolTip("Crear producto sin salir del pedido")
        btn_nuevo_prod.clicked.connect(self._nuevo_producto_inline)
        det_toolbar.addWidget(btn_add_linea)
        det_toolbar.addWidget(btn_del_linea)
        det_toolbar.addWidget(btn_nuevo_prod)
        det_toolbar.addStretch()
        det_lay.addLayout(det_toolbar)

        # Tabla
        self.tabla_detalle = QTableWidget(0, 7)
        self.tabla_detalle.setHorizontalHeaderLabels([
            "Cant.", "Producto", "Ancho (m)", "Alto (m)", "Descripción", "P. Unit.", "Subtotal"
        ])
        hh = self.tabla_detalle.horizontalHeader()
        hh.setSectionResizeMode(COL_DESC, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(COL_PROD, QHeaderView.ResizeMode.Interactive)
        self.tabla_detalle.setColumnWidth(COL_CANT,   55)
        self.tabla_detalle.setColumnWidth(COL_PROD,   180)
        self.tabla_detalle.setColumnWidth(COL_ANCHO,  75)
        self.tabla_detalle.setColumnWidth(COL_ALTO,   75)
        self.tabla_detalle.setColumnWidth(COL_PRECIO, 90)
        self.tabla_detalle.setColumnWidth(COL_SUB,    90)
        self.tabla_detalle.setMinimumHeight(180)
        self.tabla_detalle.setAlternatingRowColors(True)
        self.tabla_detalle.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_detalle.itemChanged.connect(self._on_item_cambiado)
        self.tabla_detalle.doubleClicked.connect(self._on_detalle_doble_click)
        det_lay.addWidget(self.tabla_detalle)
        tab_lay.addWidget(grp_det, stretch=1)

        # === FOOTER ===
        footer_lay = QHBoxLayout()

        # Observaciones
        grp_obs = QGroupBox("Observaciones")
        obs_lay = QVBoxLayout(grp_obs)
        self.inp_obs = QTextEdit()
        self.inp_obs.setMaximumHeight(80)
        self.inp_obs.setPlaceholderText("Notas internas, instrucciones especiales...")
        obs_lay.addWidget(self.inp_obs)

        # Archivo de diseño
        arc_lay = QHBoxLayout()
        self.inp_archivo = QLineEdit()
        self.inp_archivo.setPlaceholderText("Archivo de diseño...")
        self.inp_archivo.setReadOnly(True)
        btn_adjuntar = QPushButton("📎")
        btn_adjuntar.setFixedWidth(32)
        btn_adjuntar.setToolTip("Adjuntar archivo de diseño")
        btn_adjuntar.clicked.connect(self._adjuntar_archivo)
        self.inp_archivo.mouseDoubleClickEvent = lambda e: self._abrir_archivo()
        arc_lay.addWidget(self.inp_archivo)
        arc_lay.addWidget(btn_adjuntar)
        obs_lay.addLayout(arc_lay)
        footer_lay.addWidget(grp_obs, stretch=1)

        # Totales
        grp_tot = QGroupBox("Totales")
        tot_lay = QFormLayout(grp_tot)
        tot_lay.setSpacing(8)

        self.spin_descuento = QDoubleSpinBox()
        self.spin_descuento.setRange(0, 9_999_999)
        self.spin_descuento.setDecimals(2)
        self.spin_descuento.setPrefix("$ ")
        self.spin_descuento.valueChanged.connect(self._recalcular_total)

        self.spin_sena = QDoubleSpinBox()
        self.spin_sena.setRange(0, 9_999_999)
        self.spin_sena.setDecimals(2)
        self.spin_sena.setPrefix("$ ")
        self.spin_sena.valueChanged.connect(self._recalcular_total)

        self.lbl_subtotal = QLabel("$ 0,00")
        self.lbl_total    = QLabel("$ 0,00")
        self.lbl_total.setObjectName("lbl_total")
        self.lbl_saldo    = QLabel("$ 0,00")

        tot_lay.addRow("Subtotal:", self.lbl_subtotal)
        tot_lay.addRow("Descuento:", self.spin_descuento)
        tot_lay.addRow("Seña/Anticipo:", self.spin_sena)
        tot_lay.addRow("TOTAL:", self.lbl_total)
        tot_lay.addRow("Saldo:", self.lbl_saldo)
        footer_lay.addWidget(grp_tot)
        tab_lay.addLayout(footer_lay)

        # === BOTONES PRINCIPALES (fuera del tab, en layout raíz) ===
        btn_row = QHBoxLayout()
        btn_cancelar   = QPushButton("Cancelar")
        btn_wa         = QPushButton("📱  WhatsApp")
        btn_imprimir   = QPushButton("🖨️  Guardar e Imprimir")
        btn_guardar    = QPushButton("💾  Guardar  (Ctrl+S)")
        btn_guardar.setObjectName("btn_primary")

        btn_cancelar.clicked.connect(self.reject)
        btn_wa.clicked.connect(self._enviar_whatsapp)
        btn_imprimir.clicked.connect(self._guardar_e_imprimir)
        btn_guardar.clicked.connect(self._guardar)

        btn_row.addWidget(btn_cancelar)
        btn_row.addStretch()
        btn_row.addWidget(btn_wa)
        btn_row.addWidget(btn_imprimir)
        btn_row.addWidget(btn_guardar)
        layout.addLayout(btn_row)

        # Construir tab historial vacío (se poblará al abrir)
        self._build_tab_historial()


    # ─── TAB HISTORIAL ────────────────────────────────────────────────────────

    def _build_tab_historial(self) -> None:
        """Construye la estructura del tab historial (datos se cargan al abrirlo)."""
        lay = QVBoxLayout(self._tab_historial)
        lay.setSpacing(8)
        lay.setContentsMargins(10, 10, 10, 10)

        # Facturas del pedido
        self._grp_facturas_hist = QGroupBox("🧾  Facturas Electrónicas")
        fl = QVBoxLayout(self._grp_facturas_hist)
        self._tbl_facturas_hist = QTableWidget(0, 5)
        self._tbl_facturas_hist.setHorizontalHeaderLabels(
            ["N° Factura", "Fecha", "Total", "CAE", "Estado"])
        hh = self._tbl_facturas_hist.horizontalHeader()
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._tbl_facturas_hist.setColumnWidth(0, 130)
        self._tbl_facturas_hist.setColumnWidth(1, 90)
        self._tbl_facturas_hist.setColumnWidth(2, 100)
        self._tbl_facturas_hist.setColumnWidth(4, 90)
        self._tbl_facturas_hist.setMaximumHeight(150)
        self._tbl_facturas_hist.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_facturas_hist.verticalHeader().setVisible(False)
        self._tbl_facturas_hist.setAlternatingRowColors(True)
        fl.addWidget(self._tbl_facturas_hist)
        lay.addWidget(self._grp_facturas_hist)

        # Recibos del pedido
        self._grp_recibos_hist = QGroupBox("📄  Recibos Emitidos")
        rl = QVBoxLayout(self._grp_recibos_hist)
        self._tbl_recibos_hist = QTableWidget(0, 4)
        self._tbl_recibos_hist.setHorizontalHeaderLabels(
            ["N° Recibo", "Fecha", "Monto", "Método"])
        hh2 = self._tbl_recibos_hist.horizontalHeader()
        hh2.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tbl_recibos_hist.setColumnWidth(1, 90)
        self._tbl_recibos_hist.setColumnWidth(2, 100)
        self._tbl_recibos_hist.setColumnWidth(3, 110)
        self._tbl_recibos_hist.setMaximumHeight(130)
        self._tbl_recibos_hist.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_recibos_hist.verticalHeader().setVisible(False)
        self._tbl_recibos_hist.setAlternatingRowColors(True)
        rl.addWidget(self._tbl_recibos_hist)
        lay.addWidget(self._grp_recibos_hist)

        # Log de cambios
        self._grp_log = QGroupBox("🕐  Log de Cambios")
        ll = QVBoxLayout(self._grp_log)
        self._tbl_log = QTableWidget(0, 4)
        self._tbl_log.setHorizontalHeaderLabels(
            ["Fecha/Hora", "Usuario", "Tipo", "Descripción"])
        hh3 = self._tbl_log.horizontalHeader()
        hh3.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._tbl_log.setColumnWidth(0, 140)
        self._tbl_log.setColumnWidth(1, 110)
        self._tbl_log.setColumnWidth(2, 120)
        self._tbl_log.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_log.verticalHeader().setVisible(False)
        self._tbl_log.setAlternatingRowColors(True)
        ll.addWidget(self._tbl_log)
        lay.addWidget(self._grp_log, stretch=1)

    def _on_tab_changed(self, index: int) -> None:
        """Carga el historial cuando se abre esa solapa."""
        if index == 1 and self.pedido_id:
            self._cargar_historial()

    def _cargar_historial(self) -> None:
        """Carga facturas, recibos y log del pedido actual."""
        from utils.helpers import fmt_moneda, fmt_fecha
        from utils.styles import AppStyles
        from PySide6.QtGui import QColor

        # ── Facturas ──
        try:
            facturas = get_provider().facturas.get_by_pedido(self.pedido_id)
            self._tbl_facturas_hist.setRowCount(0)
            TIPOS = {1: "Fact.A", 6: "Fact.B", 11: "Fact.C"}
            for f in facturas:
                row = self._tbl_facturas_hist.rowCount()
                self._tbl_facturas_hist.insertRow(row)
                vals = [f.nro_factura or "(pendiente)", fmt_fecha(f.fecha_emision),
                        fmt_moneda(f.importe_total), f.cae or "—", f.estado]
                for col, txt in enumerate(vals):
                    item = QTableWidgetItem(str(txt))
                    item.setData(Qt.ItemDataRole.UserRole, f.id)
                    alin = Qt.AlignmentFlag.AlignCenter
                    if col == 2:
                        alin = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    elif col == 3:
                        alin = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    item.setTextAlignment(int(alin))
                    self._tbl_facturas_hist.setItem(row, col, item)
                color_f = {"autorizada": AppStyles.SUCCESS,
                           "rechazada":  AppStyles.DANGER}.get(f.estado, AppStyles.TEXT_DIM)
                it = self._tbl_facturas_hist.item(row, 4)
                if it:
                    it.setForeground(QColor(color_f))
                self._tbl_facturas_hist.setRowHeight(row, 28)
        except Exception as e:
            print(f"Error cargando facturas en historial: {e}")

        # ── Recibos ──
        try:
            recibos = get_provider().recibos.get_by_pedido(self.pedido_id)
            self._tbl_recibos_hist.setRowCount(0)
            for r in recibos:
                row = self._tbl_recibos_hist.rowCount()
                self._tbl_recibos_hist.insertRow(row)
                vals = [r.nro_recibo, fmt_fecha(r.fecha), fmt_moneda(r.monto), r.metodo]
                for col, txt in enumerate(vals):
                    item = QTableWidgetItem(str(txt))
                    alin = Qt.AlignmentFlag.AlignCenter
                    if col == 2:
                        alin = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    item.setTextAlignment(int(alin))
                    self._tbl_recibos_hist.setItem(row, col, item)
                self._tbl_recibos_hist.setRowHeight(row, 28)
        except Exception as e:
            print(f"Error cargando recibos en historial: {e}")

        # ── Log de cambios ──
        try:
            from models.pedido_log_model import PedidoLogModel
            entries = PedidoLogModel().get_by_pedido(self.pedido_id)
            self._tbl_log.setRowCount(0)
            TIPO_LABELS = {
                "cambio_estado": "🔄 Cambio estado",
                "creacion":      "✨ Creación",
                "modificacion":  "✏️ Modificación",
                "pago":          "💰 Pago",
                "factura":       "🧾 Factura",
                "recibo":        "📄 Recibo",
                "email":         "📧 Email",
            }
            TIPO_COLORES = {
                "cambio_estado": AppStyles.INFO,
                "creacion":      AppStyles.SUCCESS,
                "pago":          AppStyles.SUCCESS,
                "factura":       AppStyles.ACCENT,
                "recibo":        "#e0a040",
                "email":         "#60b0e0",
                "modificacion":  AppStyles.TEXT_DIM,
            }
            for entry in entries:
                row = self._tbl_log.rowCount()
                self._tbl_log.insertRow(row)
                tipo_label = TIPO_LABELS.get(entry.tipo, entry.tipo)
                vals = [entry.fecha, entry.usuario, tipo_label, entry.descripcion]
                for col, txt in enumerate(vals):
                    item = QTableWidgetItem(str(txt))
                    alin = (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                            if col == 3 else Qt.AlignmentFlag.AlignCenter)
                    item.setTextAlignment(int(alin))
                    self._tbl_log.setItem(row, col, item)
                color_t = TIPO_COLORES.get(entry.tipo, AppStyles.TEXT_DIM)
                it = self._tbl_log.item(row, 2)
                if it:
                    it.setForeground(QColor(color_t))
                self._tbl_log.setRowHeight(row, 28)
        except Exception as e:
            print(f"Error cargando log en historial: {e}")

    # ─── SHORTCUTS ────────────────────────────────────────────────────────────

    def _nuevo_producto_inline(self) -> None:
        """Crea un producto sin cerrar el diálogo de pedido."""
        from views.abm.abm_views import _FormProducto
        dlg = _FormProducto(parent=self)
        if dlg.exec():
            self._productos = get_provider().productos.get_all()
            self._refrescar_combos_producto()

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._guardar)
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._nuevo_cliente_inline)
        QShortcut(QKeySequence("Delete"), self).activated.connect(
            self._eliminar_linea_seleccionada
        )

    # ─── CARGA DE DATOS ───────────────────────────────────────────────────────

    def _cargar_combos(self, preservar_cliente_id: int = 0) -> None:
        """Carga clientes y productos en los combos.

        Si se indica preservar_cliente_id (o hay uno seleccionado),
        mantiene la selección después de recargar para no perder el
        cliente elegido al dar de alta uno nuevo o editarlo.
        """
        # Preservar selección actual si no se indica otra
        if not preservar_cliente_id:
            try:
                preservar_cliente_id = self._cliente_id or 0
            except AttributeError:
                preservar_cliente_id = 0

        self._clientes = self.cliente_model.get_all()
        self._productos = self.producto_model.get_all()

        # Combo clientes con completer (bloquear señales para no resetear estado)
        self.cmb_cliente.blockSignals(True)
        try:
            nombres = [c.nombre for c in self._clientes]
            self.cmb_cliente.clear()
            self.cmb_cliente.addItem("", 0)
            for c in self._clientes:
                self.cmb_cliente.addItem(c.nombre, c.id)
            completer = QCompleter(nombres, self.cmb_cliente)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.cmb_cliente.setCompleter(completer)

            if preservar_cliente_id:
                idx = self.cmb_cliente.findData(preservar_cliente_id)
                if idx >= 0:
                    self.cmb_cliente.setCurrentIndex(idx)
        finally:
            self.cmb_cliente.blockSignals(False)

        # Sincronizar _cliente_id con lo mostrado
        self._sincronizar_cliente_desde_combo()

    def _set_nro_nuevo(self) -> None:
        """Genera y muestra el próximo número de pedido."""
        nro = self.pedido_model.generar_nro_pedido()
        self.lbl_nro.setText(f"Pedido N°: {nro}")
        self._nro_pedido = nro

    def _cargar_pedido(self) -> None:
        """Carga un pedido existente en el formulario."""
        pedido = self.pedido_model.get_by_id(self.pedido_id)
        if not pedido:
            return

        self._nro_pedido = pedido.nro_pedido
        self.lbl_nro.setText(f"Pedido N°: {pedido.nro_pedido}")
        self.setWindowTitle(f"Editar Pedido {pedido.nro_pedido}")

        # Fechas
        if pedido.fecha_creacion:
            self.date_creacion.setDate(QDate.fromString(pedido.fecha_creacion, "yyyy-MM-dd"))
        if pedido.fecha_entrega:
            self.date_entrega.setDate(QDate.fromString(pedido.fecha_entrega, "yyyy-MM-dd"))

        # Estado
        idx = self.cmb_estado.findText(pedido.estado)
        if idx >= 0:
            self.cmb_estado.setCurrentIndex(idx)

        # Cliente
        self._cliente_id = pedido.cliente_id
        idx_cli = self.cmb_cliente.findData(pedido.cliente_id)
        if idx_cli >= 0:
            self.cmb_cliente.setCurrentIndex(idx_cli)

        # Montos
        self._bloqueando_calculo = True
        self.spin_descuento.setValue(pedido.descuento)
        self.spin_sena.setValue(pedido.sena)
        self._bloqueando_calculo = False

        # Observaciones y archivo
        self.inp_obs.setPlainText(pedido.observaciones)
        self.inp_archivo.setText(pedido.archivo_diseno_path)

        # Detalle
        items = self.detalle_model.get_by_pedido(self.pedido_id)
        for item in items:
            self._agregar_linea(item)

        self._recalcular_total()

    # ─── TABLA DETALLE ────────────────────────────────────────────────────────

    def _agregar_linea(self, item: PedidoDetalle | None = None) -> None:
        """Agrega una fila a la tabla de detalle."""
        self.tabla_detalle.itemChanged.disconnect(self._on_item_cambiado)
        row = self.tabla_detalle.rowCount()
        self.tabla_detalle.insertRow(row)

        # Cant
        spin_cant = QSpinBox()
        spin_cant.setRange(1, 99999)
        spin_cant.setValue(item.cantidad if item else 1)
        spin_cant.valueChanged.connect(self._recalcular_fila)
        self.tabla_detalle.setCellWidget(row, COL_CANT, spin_cant)

        # Producto (combo editable con buscador)
        cmb_prod = QComboBox()
        cmb_prod.setEditable(True)
        cmb_prod.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        cmb_prod.addItem("-- Sin producto --", None)
        nombres_prod = []
        for p in self._productos:
            cmb_prod.addItem(p.nombre, p.id)
            nombres_prod.append(p.nombre)
        # Completer con búsqueda por contiene
        _comp = QCompleter(nombres_prod, cmb_prod)
        _comp.setFilterMode(Qt.MatchFlag.MatchContains)
        _comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        _comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        cmb_prod.setCompleter(_comp)
        # Al seleccionar del completer, sincronizar el índice del combo
        def _on_completer_activated(text, combo=cmb_prod):
            idx_found = combo.findText(text, Qt.MatchFlag.MatchExactly)
            if idx_found >= 0:
                combo.setCurrentIndex(idx_found)
        _comp.activated.connect(_on_completer_activated)
        if item and item.producto_id:
            idx = cmb_prod.findData(item.producto_id)
            if idx >= 0:
                cmb_prod.setCurrentIndex(idx)
        cmb_prod.currentIndexChanged.connect(
            lambda idx, r=row: self._on_producto_cambiado(r)
        )
        self.tabla_detalle.setCellWidget(row, COL_PROD, cmb_prod)

        # Ancho
        spin_ancho = QDoubleSpinBox()
        spin_ancho.setRange(0, 9999)
        spin_ancho.setDecimals(2)
        spin_ancho.setValue(item.ancho if item else 0)
        spin_ancho.valueChanged.connect(self._recalcular_fila)
        self.tabla_detalle.setCellWidget(row, COL_ANCHO, spin_ancho)

        # Alto
        spin_alto = QDoubleSpinBox()
        spin_alto.setRange(0, 9999)
        spin_alto.setDecimals(2)
        spin_alto.setValue(item.alto if item else 0)
        spin_alto.valueChanged.connect(self._recalcular_fila)
        self.tabla_detalle.setCellWidget(row, COL_ALTO, spin_alto)

        # Descripción
        cell_desc = QTableWidgetItem(item.descripcion if item else "")
        self.tabla_detalle.setItem(row, COL_DESC, cell_desc)

        # Precio unitario
        spin_precio = QDoubleSpinBox()
        spin_precio.setRange(0, 9_999_999)
        spin_precio.setDecimals(2)
        spin_precio.setPrefix("$ ")
        spin_precio.setValue(item.precio_unitario if item else 0)
        spin_precio.valueChanged.connect(self._recalcular_fila)
        self.tabla_detalle.setCellWidget(row, COL_PRECIO, spin_precio)

        # Subtotal (read-only)
        cell_sub = QTableWidgetItem(fmt_moneda(item.subtotal if item else 0))
        cell_sub.setFlags(Qt.ItemFlag.ItemIsEnabled)
        cell_sub.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.tabla_detalle.setItem(row, COL_SUB, cell_sub)

        self.tabla_detalle.setRowHeight(row, 36)
        self.tabla_detalle.itemChanged.connect(self._on_item_cambiado)

        # Guardar ID interno de la línea
        self.tabla_detalle.item(row, COL_SUB).setData(
            Qt.ItemDataRole.UserRole, item.id if item else 0
        )

    def _on_detalle_doble_click(self, index) -> None:
        """Doble click en col Producto → abre ese producto en edición."""
        if index.column() != COL_PROD:
            return
        row = index.row()
        cmb = self.tabla_detalle.cellWidget(row, COL_PROD)
        if not cmb:
            return
        prod_id = cmb.currentData()
        if not prod_id:
            return
        from views.abm.abm_views import _FormProducto
        dlg = _FormProducto(prod_id=prod_id, parent=self)
        if dlg.exec():
            # Recargar productos y refrescar combos
            self._productos = get_provider().productos.get_all()
            self._refrescar_combos_producto()

    def _refrescar_combos_producto(self) -> None:
        """Recarga los combos de producto en todas las filas."""
        for row in range(self.tabla_detalle.rowCount()):
            cmb = self.tabla_detalle.cellWidget(row, COL_PROD)
            if cmb:
                current_id = cmb.currentData()
                cmb.blockSignals(True)
                cmb.clear()
                cmb.addItem("-- Sin producto --", None)
                nombres = []
                for p in self._productos:
                    cmb.addItem(p.nombre, p.id)
                    nombres.append(p.nombre)
                _c = QCompleter(nombres, cmb)
                _c.setFilterMode(Qt.MatchFlag.MatchContains)
                _c.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                _c.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
                cmb.setCompleter(_c)
                idx = cmb.findData(current_id)
                cmb.setCurrentIndex(idx if idx >= 0 else 0)
                cmb.blockSignals(False)

    def _eliminar_linea_seleccionada(self) -> None:
        rows = self.tabla_detalle.selectedItems()
        if not rows:
            return
        row = self.tabla_detalle.currentRow()
        self.tabla_detalle.removeRow(row)
        self._recalcular_total()

    def _on_producto_cambiado(self, row: int) -> None:
        """Auto-completa precio cuando se selecciona producto."""
        cmb = self.tabla_detalle.cellWidget(row, COL_PROD)
        if not cmb:
            return
        prod_id = cmb.currentData()
        if prod_id is None:
            return
        for p in self._productos:
            if p.id == prod_id:
                spin_precio = self.tabla_detalle.cellWidget(row, COL_PRECIO)
                if spin_precio and spin_precio.value() == 0:
                    spin_precio.setValue(p.precio_base)
                # Auto-completar descripción si está vacía
                desc_item = self.tabla_detalle.item(row, COL_DESC)
                if desc_item and not desc_item.text():
                    desc_item.setText(p.nombre)
                break

    def _recalcular_fila(self) -> None:
        """Recalcula subtotales de todas las filas."""
        for row in range(self.tabla_detalle.rowCount()):
            spin_cant   = self.tabla_detalle.cellWidget(row, COL_CANT)
            spin_ancho  = self.tabla_detalle.cellWidget(row, COL_ANCHO)
            spin_alto   = self.tabla_detalle.cellWidget(row, COL_ALTO)
            spin_precio = self.tabla_detalle.cellWidget(row, COL_PRECIO)
            cell_sub    = self.tabla_detalle.item(row, COL_SUB)
            if not all([spin_cant, spin_precio, cell_sub]):
                continue
            cant   = spin_cant.value()
            precio = spin_precio.value()
            ancho  = spin_ancho.value() if spin_ancho else 0
            alto   = spin_alto.value() if spin_alto else 0
            # Si tiene medidas, multiplicar por m2
            if ancho > 0 and alto > 0:
                sub = cant * ancho * alto * precio
            else:
                sub = cant * precio
            cell_sub.setText(fmt_moneda(sub))
        self._recalcular_total()

    def _on_item_cambiado(self, item: QTableWidgetItem) -> None:
        if item.column() in (COL_DESC,):
            return
        self._recalcular_fila()

    def _recalcular_total(self) -> None:
        if self._bloqueando_calculo:
            return
        subtotal = 0.0
        for row in range(self.tabla_detalle.rowCount()):
            cell = self.tabla_detalle.item(row, COL_SUB)
            if cell:
                texto = cell.text().replace("$", "").replace(".", "").replace(",", ".")
                try:
                    subtotal += float(texto)
                except ValueError:
                    pass

        descuento = self.spin_descuento.value()
        sena      = self.spin_sena.value()
        total     = subtotal - descuento
        saldo     = total - sena

        self.lbl_subtotal.setText(fmt_moneda(subtotal))
        self.lbl_total.setText(fmt_moneda(total))
        self.lbl_saldo.setText(fmt_moneda(saldo))

    # ─── CLIENTE ──────────────────────────────────────────────────────────────

    def _sincronizar_cliente_desde_combo(self) -> None:
        """Sincroniza _cliente_id con lo que realmente muestra el combo.

        Evita el bug de ID "viejo": si el texto escrito no coincide con
        el cliente seleccionado, se considera que no hay cliente elegido.
        """
        texto = self.cmb_cliente.currentText().strip()
        cliente_id = self.cmb_cliente.currentData()
        if not cliente_id:
            self._cliente_id = 0
        else:
            # Verificar que el texto coincida con el nombre del ID seleccionado
            nombre_sel = self.cmb_cliente.itemText(self.cmb_cliente.currentIndex()).strip()
            if texto.lower() != nombre_sel.lower():
                # El usuario escribió otra cosa: buscar coincidencia exacta
                encontrado = next(
                    (c for c in self._clientes if c.nombre.lower() == texto.lower()),
                    None,
                )
                self._cliente_id = encontrado.id if encontrado else 0
            else:
                self._cliente_id = cliente_id
        self._mostrar_saldo_cliente()

    def _mostrar_saldo_cliente(self) -> None:
        if self._cliente_id:
            try:
                saldo = self.cliente_model.get_saldo_total(self._cliente_id)
            except Exception:
                saldo = 0
            if saldo > 0:
                self.lbl_saldo_cli.setText(f"⚠️  Saldo pendiente: {fmt_moneda(saldo)}")
            else:
                self.lbl_saldo_cli.setText("✅  Sin deuda")
        else:
            self.lbl_saldo_cli.setText("")

    def _on_cliente_cambiado(self, index: int) -> None:
        """Actualiza _cliente_id y muestra saldo del cliente."""
        self._sincronizar_cliente_desde_combo()

    def _on_cliente_texto_cambiado(self, texto: str) -> None:
        """Cuando el usuario escribe, invalidar ID viejo hasta elegir/crear."""
        # Si el texto no coincide con el ítem seleccionado, marcar sin cliente
        # (la sincronización final se hace en _verificar_cliente_nuevo / guardar)
        nombre_sel = ""
        idx = self.cmb_cliente.currentIndex()
        if idx >= 0:
            nombre_sel = self.cmb_cliente.itemText(idx).strip()
        if texto.strip().lower() != nombre_sel.lower():
            self._cliente_id = 0
            self.lbl_saldo_cli.setText("")

    def _nuevo_cliente_inline(self) -> None:
        """Alta de cliente sin cerrar el pedido. Botón ➕ Nuevo."""
        from views.dialogs.dialogo_cliente import DialogoClienteRapido
        texto_actual = self.cmb_cliente.currentText().strip()
        # Si el texto actual ya es un cliente existente, no pre-llenar como nuevo
        inicial = texto_actual
        for c in self._clientes:
            if c.nombre.lower() == texto_actual.lower():
                inicial = ""  # ya existe, abrir en blanco
                break
        dlg = DialogoClienteRapido(inicial, self)
        dlg.cliente_creado.connect(self._on_cliente_rapido_creado)
        dlg.exec()
        # Si el diálogo se aceptó, el callback ya seleccionó al cliente.
        # Si se canceló, no se toca nada y el pedido sigue abierto.

    def _ver_cliente(self) -> None:
        """Abre diálogo de edición del cliente seleccionado."""
        self._sincronizar_cliente_desde_combo()
        if not self._cliente_id:
            # Si escribió un nombre nuevo, ofrecer crearlo directo
            texto = self.cmb_cliente.currentText().strip()
            if texto:
                resp = QMessageBox.question(
                    self, "Cliente no encontrado",
                    f"'{texto}' no es un cliente registrado.\n\n"
                    "¿Querés darlo de alta ahora?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if resp == QMessageBox.StandardButton.Yes:
                    self._nuevo_cliente_inline()
                return
            QMessageBox.information(self, "Info", "Seleccioná un cliente primero.")
            return
        from views.dialogs.dialogo_cliente import DialogoCliente
        dlg = DialogoCliente(self._cliente_id, self)
        if dlg.exec():
            # Recargar manteniendo la selección (antes se perdía)
            self._cargar_combos(preservar_cliente_id=self._cliente_id)

    def _verificar_cliente_nuevo(self) -> bool:
        """
        Si el texto del combo no coincide con ningún cliente,
        pregunta si crear uno nuevo.
        Se llama desde _validar() antes de guardar.
        """
        self._sincronizar_cliente_desde_combo()
        if self._cliente_id:
            return True
        texto = self.cmb_cliente.currentText().strip()
        if not texto:
            return True  # _validar() pedirá seleccionar cliente

        # Buscar coincidencia exacta (por si se escribió a mano)
        for c in self._clientes:
            if c.nombre.lower() == texto.lower():
                idx = self.cmb_cliente.findData(c.id)
                if idx >= 0:
                    self.cmb_cliente.blockSignals(True)
                    self.cmb_cliente.setCurrentIndex(idx)
                    self.cmb_cliente.blockSignals(False)
                self._cliente_id = c.id
                self._mostrar_saldo_cliente()
                return True

        resp = QMessageBox.question(
            self, "Cliente no encontrado",
            f"El cliente '{texto}' no existe. ¿Querés crearlo ahora\n"
            "sin salir del pedido?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            self._nuevo_cliente_inline()
        return bool(self._cliente_id)

    def _on_cliente_rapido_creado(self, cliente_id: int, nombre: str) -> None:
        """Callback cuando se crea un cliente rápido: recarga y lo deja seleccionado."""
        self._cargar_combos(preservar_cliente_id=cliente_id)
        # Asegurar selección aunque _cargar_combos ya la puso
        idx = self.cmb_cliente.findData(cliente_id)
        if idx >= 0:
            self.cmb_cliente.blockSignals(True)
            self.cmb_cliente.setCurrentIndex(idx)
            self.cmb_cliente.blockSignals(False)
        self._cliente_id = cliente_id
        self._mostrar_saldo_cliente()

    # ─── ARCHIVO ──────────────────────────────────────────────────────────────

    def _adjuntar_archivo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Adjuntar archivo de diseño",
            str(Path.home()),
            "Todos los archivos (*.*)"
        )
        if ruta:
            self.inp_archivo.setText(ruta)

    def _abrir_archivo(self) -> None:
        ruta = self.inp_archivo.text()
        if ruta and Path(ruta).exists():
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))

    # ─── GUARDAR ──────────────────────────────────────────────────────────────

    def _validar(self) -> bool:
        if not self._verificar_cliente_nuevo():
            return False
        if not self._cliente_id:
            QMessageBox.warning(self, "Requerido", "Debe seleccionar un cliente.")
            self.cmb_cliente.setFocus()
            return False
        if self.tabla_detalle.rowCount() == 0:
            QMessageBox.warning(self, "Requerido", "Debe agregar al menos un ítem al pedido.")
            return False
        # Validar que todos los ítems tengan precio > 0 y cantidad > 0
        for row in range(self.tabla_detalle.rowCount()):
            spin_precio = self.tabla_detalle.cellWidget(row, COL_PRECIO)
            desc_item   = self.tabla_detalle.item(row, COL_DESC)
            if spin_precio and spin_precio.value() <= 0:
                QMessageBox.warning(self, "Error",
                    f"La fila {row+1} tiene precio 0. Completá el precio unitario.")
                return False
            if desc_item and not desc_item.text().strip():
                QMessageBox.warning(self, "Error",
                    f"La fila {row+1} no tiene descripción.")
                return False
        # Validar que descuento no supere subtotal (evita total negativo)
        try:
            subtotal_txt = self.lbl_subtotal.text().replace("$", "").replace(".", "").replace(",", ".")
            subtotal_val = float(subtotal_txt)
            if self.spin_descuento.value() > subtotal_val:
                QMessageBox.warning(self, "Error",
                    "El descuento no puede ser mayor al subtotal.")
                return False
        except ValueError:
            pass
        return True

    def _guardar(self) -> None:
        if not self._validar():
            return

        # Construir objeto Pedido
        from models.usuario_model import UsuarioModel
        usuario_actual = UsuarioModel.usuario_actual()
        pedido = Pedido(
            id=self.pedido_id,
            nro_pedido=self._nro_pedido,
            cliente_id=self._cliente_id,
            fecha_creacion=self.date_creacion.date().toString("yyyy-MM-dd"),
            fecha_entrega=self.date_entrega.date().toString("yyyy-MM-dd"),
            estado=self.cmb_estado.currentText(),
            descuento=self.spin_descuento.value(),
            sena=self.spin_sena.value(),
            observaciones=self.inp_obs.toPlainText().strip(),
            archivo_diseno_path=self.inp_archivo.text().strip(),
            usuario_id=usuario_actual.id if usuario_actual else 0,
        )

        es_nuevo = not bool(self.pedido_id)
        if self.pedido_id:
            ok = self.pedido_model.actualizar(pedido)
        else:
            nuevo_id = self.pedido_model.insertar(pedido)
            ok = bool(nuevo_id)
            if ok:
                self.pedido_id = nuevo_id

        if not ok:
            QMessageBox.critical(self, "Error", "No se pudo guardar el pedido.")
            return

        # Guardar detalle: borrar existente y re-insertar
        self.detalle_model.eliminar_por_pedido(self.pedido_id)
        for row in range(self.tabla_detalle.rowCount()):
            spin_cant   = self.tabla_detalle.cellWidget(row, COL_CANT)
            cmb_prod    = self.tabla_detalle.cellWidget(row, COL_PROD)
            spin_ancho  = self.tabla_detalle.cellWidget(row, COL_ANCHO)
            spin_alto   = self.tabla_detalle.cellWidget(row, COL_ALTO)
            desc_item   = self.tabla_detalle.item(row, COL_DESC)
            spin_precio = self.tabla_detalle.cellWidget(row, COL_PRECIO)

            cant   = spin_cant.value() if spin_cant else 1
            ancho  = spin_ancho.value() if spin_ancho else 0
            alto   = spin_alto.value() if spin_alto else 0
            precio = spin_precio.value() if spin_precio else 0
            desc   = desc_item.text() if desc_item else ""
            prod_id = cmb_prod.currentData() if cmb_prod else None

            if ancho > 0 and alto > 0:
                sub = cant * ancho * alto * precio
            else:
                sub = cant * precio

            det = PedidoDetalle(
                pedido_id=self.pedido_id,
                producto_id=prod_id,
                descripcion=desc,
                cantidad=cant,
                ancho=ancho,
                alto=alto,
                precio_unitario=precio,
                subtotal=sub,
            )
            self.detalle_model.insertar(det)

        # Log de creación/modificación
        try:
            from models.pedido_log_model import PedidoLogModel
            log = PedidoLogModel()
            if not es_nuevo:
                log.registrar_modificacion(self.pedido_id, f"Estado: {pedido.estado}")
            else:
                log.registrar(self.pedido_id, "creacion",
                              f"Pedido creado en estado '{pedido.estado}'")
        except Exception:
            pass
        self.pedido_guardado.emit(self.pedido_id)
        self.accept()

    def _guardar_e_imprimir(self) -> None:
        self._guardar()
        if self.result() == QDialog.DialogCode.Accepted:
            self._imprimir_pdf()

    def _imprimir_pdf(self) -> None:
        """Genera y abre el PDF del presupuesto."""
        try:
            from utils.pdf_generator import generar_presupuesto
            from models.config_model import ConfigModel
            from models.cliente_model import ClienteModel
            from db.database import DatabaseManager
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            pedido  = self.pedido_model.get_by_id(self.pedido_id)
            items   = self.detalle_model.get_by_pedido(self.pedido_id)
            cliente = get_provider().clientes.get_by_id(pedido.cliente_id)
            config  = get_provider().config.get_datos_imprenta()

            db_mgr   = DatabaseManager()
            out_path = str(db_mgr.presupuestos_dir / f"{pedido.nro_pedido}.pdf")
            generar_presupuesto(pedido, items, cliente, config, out_path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(out_path))
        except Exception as e:
            QMessageBox.warning(self, "Error PDF", f"No se pudo generar el PDF:\n{e}")

    def _enviar_whatsapp(self) -> None:
        """Guarda si es nuevo y luego abre WhatsApp."""
        if not self.pedido_id:
            self._guardar()
            if self.result() != QDialog.DialogCode.Accepted:
                return
        pedido  = self.pedido_model.get_by_id(self.pedido_id)
        cliente = self.cliente_model.get_by_id(pedido.cliente_id)
        if not abrir_whatsapp_presupuesto(
            cliente.nombre, cliente.whatsapp,
            pedido.nro_pedido, pedido.total, pedido.fecha_creacion
        ):
            QMessageBox.warning(self, "WhatsApp",
                "El cliente no tiene número de WhatsApp registrado.")
