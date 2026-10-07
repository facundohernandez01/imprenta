"""
Tab 1: Pedidos v2.
- Estado multi-select, rangos rápidos, vistas guardadas, ordenamiento por columna
- Trazabilidad usuario, menú contextual, QDateEdit con calendarPopup
"""
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QLineEdit, QDateEdit, QHeaderView,
    QAbstractItemView, QCompleter, QMenu, QFrame, QDialog, QFormLayout,
    QDialogButtonBox, QMessageBox, QWidgetAction, QCheckBox
)
from PySide6.QtCore import Qt, QDate, Signal, QPoint
from PySide6.QtGui import QColor, QAction

from models.pedido_model import ESTADOS_PEDIDO, ESTADO_COLORES, Pedido
from network.data_provider import get_provider
from utils.helpers import fmt_moneda, fmt_fecha, es_vencida
from utils.styles import AppStyles

C_NRO=0; C_FECHA=1; C_ENTREG=2; C_CLI=3; C_USUARIO=4
C_ESTADO=5; C_TOTAL=6; C_SENA=7; C_SALDO=8; C_ACC=9


class _MultiEstadoBtn(QPushButton):
    changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__("Estado: Todos ▾", parent)
        self._estados = {e: False for e in ESTADOS_PEDIDO}
        self.setMinimumWidth(170)
        self.clicked.connect(self._popup)

    def _popup(self):
        menu = QMenu(self)
        # Opción "Todos"
        act_todos = QAction("✔  Todos / Ninguno", self)
        act_todos.triggered.connect(self._toggle_todos)
        menu.addAction(act_todos)
        menu.addSeparator()
        for estado in ESTADOS_PEDIDO:
            bg, fg = ESTADO_COLORES.get(estado, ("#3a3a5c", "#a0a0d0"))
            chk = QCheckBox(estado)
            chk.setChecked(self._estados.get(estado, False))
            chk.setStyleSheet(f"QCheckBox {{ padding:4px 10px; color:{fg}; }}")
            chk.toggled.connect(lambda checked, e=estado: self._toggle(e, checked))
            w = QWidget(); lay = QHBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(chk)
            wa = QWidgetAction(self); wa.setDefaultWidget(w)
            menu.addAction(wa)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))
        self._update_label()
        self.changed.emit(self.get_sel())

    def _toggle(self, e, v): self._estados[e] = v
    def _toggle_todos(self):
        hay = any(self._estados.values())
        for e in self._estados: self._estados[e] = not hay

    def get_sel(self): return [e for e, v in self._estados.items() if v]
    def set_sel(self, lst):
        for e in self._estados: self._estados[e] = e in lst
        self._update_label()

    def _update_label(self):
        sel = self.get_sel()
        if not sel: self.setText("Estado: Todos ▾")
        elif len(sel) == 1: self.setText(f"Estado: {sel[0]} ▾")
        else: self.setText(f"Estado: {len(sel)} sel. ▾")


class _DlgGuardarVista(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guardar Vista")
        self.setFixedWidth(300)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.inp = QLineEdit(); self.inp.setPlaceholderText("Ej: Solo Presupuestos")
        form.addRow("Nombre:", self.inp)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        lay.addWidget(btns)
    def nombre(self): return self.inp.text().strip()


class TabPedidos(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pedidos: list[Pedido] = []
        self._build_ui()
        self.refrescar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 8, 10, 8)

        # Toolbar
        tb = QHBoxLayout()
        btn_nuevo = QPushButton("➕  Nuevo Pedido")
        btn_nuevo.setObjectName("btn_primary")
        btn_nuevo.setShortcut("Ctrl+N")
        btn_nuevo.clicked.connect(self._nuevo_pedido)
        btn_ref = QPushButton("🔄"); btn_ref.setShortcut("F5"); btn_ref.setFixedWidth(36)
        btn_ref.clicked.connect(self.refrescar)
        btn_xls = QPushButton("📊 Exportar"); btn_xls.clicked.connect(self._exportar)
        for b in [btn_nuevo, btn_ref, btn_xls]: tb.addWidget(b)
        tb.addStretch()
        layout.addLayout(tb)

        # Rangos rápidos
        rr = QHBoxLayout()
        rr.addWidget(QLabel("Rango:"))
        self._rangos_btns = []
        for texto, dias in [("Hoy",0),("7d",7),("30d",30),("3m",90),("Año",-1),("Todo",-2)]:
            b = QPushButton(texto)
            b.setCheckable(True)
            b.setFixedHeight(24)
            b.setStyleSheet(
                f"QPushButton{{padding:2px 8px;border:1px solid {AppStyles.BORDER};"
                f"border-radius:3px;color:{AppStyles.TEXT_DIM};}}"
                f"QPushButton:checked{{color:{AppStyles.ACCENT};background:#1a1a3a;"
                f"border-color:{AppStyles.ACCENT};font-weight:bold;}}"
                f"QPushButton:hover{{border-color:{AppStyles.ACCENT};}}"
            )
            b.clicked.connect(lambda _,d=dias: self._rango_rapido(d))
            self._rangos_btns.append((b, dias))
            rr.addWidget(b)
        rr.addStretch()
        layout.addLayout(rr)

        # Frame de filtros
        ff = QFrame()
        ff.setStyleSheet(f"background:{AppStyles.BG_LIGHT};border-radius:4px;border:1px solid {AppStyles.BORDER};")
        fl = QHBoxLayout(ff); fl.setContentsMargins(8,5,8,5); fl.setSpacing(8)

        self.btn_estado = _MultiEstadoBtn()
        self.btn_estado.changed.connect(lambda _: self._filtrar())
        fl.addWidget(self.btn_estado)

        fl.addWidget(QLabel("Cliente:"))
        self.cmb_cli = QComboBox(); self.cmb_cli.setEditable(True); self.cmb_cli.setMinimumWidth(150)
        self._cargar_clientes_combo()
        self.cmb_cli.currentIndexChanged.connect(self._filtrar)
        fl.addWidget(self.cmb_cli)

        fl.addWidget(QLabel("Desde:"))
        self.date_desde = QDateEdit(QDate.currentDate().addMonths(-3))
        self.date_desde.setCalendarPopup(True)
        self.date_desde.setDisplayFormat("dd/MM/yyyy")
        self.date_desde.setFixedWidth(110)
        self.date_desde.dateChanged.connect(self._on_fecha_manual)
        fl.addWidget(self.date_desde)

        fl.addWidget(QLabel("Hasta:"))
        self.date_hasta = QDateEdit(QDate.currentDate())
        self.date_hasta.setCalendarPopup(True)
        self.date_hasta.setDisplayFormat("dd/MM/yyyy")
        self.date_hasta.setFixedWidth(110)
        self.date_hasta.dateChanged.connect(self._on_fecha_manual)
        fl.addWidget(self.date_hasta)

        self.inp_buscar = QLineEdit()
        self.inp_buscar.setPlaceholderText("🔍 Nro, cliente...")
        self.inp_buscar.setMinimumWidth(150)
        self.inp_buscar.textChanged.connect(self._filtrar)
        fl.addWidget(self.inp_buscar)

        btn_limpiar = QPushButton("✖"); btn_limpiar.setFixedSize(28,28)
        btn_limpiar.clicked.connect(self._limpiar)
        fl.addWidget(btn_limpiar)
        layout.addWidget(ff)

        # Vistas guardadas
        vl = QHBoxLayout()
        vl.addWidget(QLabel("Vistas:"))
        self.cmb_vistas = QComboBox(); self.cmb_vistas.setMinimumWidth(180)
        self.cmb_vistas.currentIndexChanged.connect(self._aplicar_vista)
        vl.addWidget(self.cmb_vistas)
        btn_sv = QPushButton("💾 Guardar vista"); btn_sv.clicked.connect(self._guardar_vista)
        btn_dv = QPushButton("🗑"); btn_dv.setFixedWidth(28); btn_dv.clicked.connect(self._eliminar_vista)
        vl.addWidget(btn_sv); vl.addWidget(btn_dv)
        vl.addStretch()
        self.lbl_count = QLabel(""); self.lbl_count.setStyleSheet(f"color:{AppStyles.TEXT_DIM};font-size:9pt;")
        vl.addWidget(self.lbl_count)
        layout.addLayout(vl)

        # Tabla
        self.tabla = QTableWidget(0, 10)
        self.tabla.setHorizontalHeaderLabels([
            "N° Pedido","Creación","Entrega","Cliente","Usuario",
            "Estado","Total","Seña","Saldo","Acciones"
        ])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(C_CLI, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(C_ACC, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(C_ESTADO, QHeaderView.ResizeMode.Interactive)
        hh.setSortIndicatorShown(True)
        hh.sectionClicked.connect(self._sort_col)
        for col, w in {C_NRO:105,C_FECHA:90,C_ENTREG:90,C_USUARIO:100,
                       C_ESTADO:155,C_TOTAL:90,C_SENA:80,C_SALDO:90,C_ACC:145}.items():
            self.tabla.setColumnWidth(col, w)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.doubleClicked.connect(lambda idx: self._editar(
            self.tabla.item(idx.row(), C_NRO).data(Qt.ItemDataRole.UserRole)
            if self.tabla.item(idx.row(), C_NRO) else None))
        self.tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabla.customContextMenuRequested.connect(self._ctx_menu)
        layout.addWidget(self.tabla)

        self.lbl_footer = QLabel("")
        self.lbl_footer.setStyleSheet(f"color:{AppStyles.TEXT_DIM};font-size:9pt;")
        layout.addWidget(self.lbl_footer)

        self._sort_ascending = False
        self._sort_last_col  = C_FECHA
        self._cargar_vistas()

    def _cargar_clientes_combo(self):
        self.cmb_cli.clear()
        self.cmb_cli.addItem("Todos", 0)
        clientes = get_provider().clientes.get_all()
        for c in clientes: self.cmb_cli.addItem(c.nombre, c.id)
        comp = QCompleter([c.nombre for c in clientes])
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.cmb_cli.setCompleter(comp)

    def _rango_rapido(self, dias):
        for b, d in self._rangos_btns: b.setChecked(d == dias)
        hoy = QDate.currentDate()
        self.date_desde.blockSignals(True); self.date_hasta.blockSignals(True)
        if   dias ==  0: self.date_desde.setDate(hoy);                       self.date_hasta.setDate(hoy)
        elif dias == -1: self.date_desde.setDate(QDate(hoy.year(),1,1));     self.date_hasta.setDate(hoy)
        elif dias == -2: self.date_desde.setDate(QDate(2020,1,1));           self.date_hasta.setDate(hoy)
        else:            self.date_desde.setDate(hoy.addDays(-dias));        self.date_hasta.setDate(hoy)
        self.date_desde.blockSignals(False); self.date_hasta.blockSignals(False)
        self._filtrar()

    def _on_fecha_manual(self):
        for b, _ in self._rangos_btns: b.setChecked(False)
        self._filtrar()

    def refrescar(self): self._filtrar()

    def _filtrar(self):
        filtros: dict = {}
        estados = self.btn_estado.get_sel()
        if estados: filtros["estados"] = estados
        cli_id = self.cmb_cli.currentData()
        if cli_id: filtros["cliente_id"] = cli_id
        filtros["desde"] = self.date_desde.date().toString("yyyy-MM-dd")
        filtros["hasta"]  = self.date_hasta.date().toString("yyyy-MM-dd")
        b = self.inp_buscar.text().strip()
        if b: filtros["buscar"] = b
        self._pedidos = get_provider().pedidos.get_all(filtros)
        self._poblar()

    def _limpiar(self):
        self.btn_estado.set_sel([])
        self.cmb_cli.setCurrentIndex(0)
        for b, _ in self._rangos_btns: b.setChecked(False)
        self.date_desde.setDate(QDate.currentDate().addMonths(-3))
        self.date_hasta.setDate(QDate.currentDate())
        self.inp_buscar.clear()
        self._filtrar()

    def _poblar(self):
        self.tabla.setSortingEnabled(False)
        self.tabla.setRowCount(0)
        for p in self._pedidos:
            row = self.tabla.rowCount(); self.tabla.insertRow(row)
            bg, fg = ESTADO_COLORES.get(p.estado, ("#3a3a5c","#a0a0d0"))
            datos = [
                (C_NRO,     p.nro_pedido,              Qt.AlignmentFlag.AlignCenter),
                (C_FECHA,   fmt_fecha(p.fecha_creacion), Qt.AlignmentFlag.AlignCenter),
                (C_ENTREG,  fmt_fecha(p.fecha_entrega),  Qt.AlignmentFlag.AlignCenter),
                (C_CLI,     p.cliente_nombre,            Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter),
                (C_USUARIO, p.usuario_nombre or "—",     Qt.AlignmentFlag.AlignCenter),
                (C_ESTADO,  p.estado,                    Qt.AlignmentFlag.AlignCenter),
                (C_TOTAL,   fmt_moneda(p.total),         Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter),
                (C_SENA,    fmt_moneda(p.sena),          Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter),
                (C_SALDO,   fmt_moneda(p.saldo),         Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter),
            ]
            for col, txt, aln in datos:
                item = QTableWidgetItem(str(txt))
                item.setTextAlignment(int(aln))
                item.setData(Qt.ItemDataRole.UserRole, p.id)
                if col == C_ESTADO:
                    item.setForeground(QColor(fg)); item.setBackground(QColor(bg))
                self.tabla.setItem(row, col, item)
            self.tabla.setCellWidget(row, C_ACC, self._acciones_widget(p.id))
            if es_vencida(p.fecha_entrega, p.estado):
                for c in range(C_ACC):
                    it = self.tabla.item(row, c)
                    if it and c != C_ESTADO: it.setBackground(QColor("#3a1515"))
            self.tabla.setRowHeight(row, 36)
        self.tabla.setSortingEnabled(True)
        stats = get_provider().pedidos.get_stats_footer()
        n = len(self._pedidos)
        self.lbl_count.setText(f"{n} pedidos")
        self.lbl_footer.setText(
            f"Mostrando {n}  |  Facturado total: {fmt_moneda(stats.get('facturado',0))}"
            f"  |  Pendiente cobro: {fmt_moneda(stats.get('pendiente',0))}"
        )

    def _acciones_widget(self, pid):
        w = QWidget(); lay = QHBoxLayout(w)
        lay.setContentsMargins(2,0,2,0); lay.setSpacing(2)
        def _b(ico, tip, fn):
            b = QPushButton(ico); b.setToolTip(tip)
            b.setObjectName("btn_flat"); b.setFixedSize(28,26)
            b.clicked.connect(lambda: fn(pid)); lay.addWidget(b)
        _b("✏️","Editar",        self._editar)
        _b("📱","WhatsApp",      self._wa)
        _b("🖨️","PDF",           self._pdf)
        _b("💰","Registrar pago",self._pago)
        return w

    def _sort_col(self, col):
        if col == C_ACC: return
        if self._sort_last_col == col: self._sort_ascending = not self._sort_ascending
        else: self._sort_ascending = True; self._sort_last_col = col
        self.tabla.sortItems(col, Qt.SortOrder.AscendingOrder if self._sort_ascending else Qt.SortOrder.DescendingOrder)

    def _ctx_menu(self, pos):
        row = self.tabla.rowAt(pos.y())
        if row < 0: return
        it = self.tabla.item(row, C_NRO)
        if not it: return
        pid = it.data(Qt.ItemDataRole.UserRole)

        # Obtener estado actual de la fila
        it_estado = self.tabla.item(row, C_ESTADO)
        estado_actual = it_estado.text() if it_estado else ""
        estados_facturables = {"Cobrado", "Entregado", "Pendiente de Cobro"}
        puede_facturar = estado_actual in estados_facturables

        m = QMenu(self)
        m.addAction("✏️  Editar pedido",            lambda: self._editar(pid))
        m.addSeparator()

        # Enviar a Taller (solo si no está ya en taller o en estados finales)
        estados_no_taller = {"En Taller","Listo para Entregar","Entregado","Cobrado","Cancelado"}
        act_taller = m.addAction("🔧  Enviar a Taller",
                                  lambda: self._enviar_a_taller(pid))
        if estado_actual in estados_no_taller:
            act_taller.setEnabled(False)
            act_taller.setToolTip(f"Estado '{estado_actual}' no permite esta acción")

        m.addSeparator()
        m.addAction("💰  Registrar pago",           lambda: self._pago(pid))

        act_fac = m.addAction("🧾  Emitir Factura ARCA", lambda: self._factura(pid))
        if not puede_facturar:
            act_fac.setEnabled(False)
            act_fac.setToolTip(
                f"Solo disponible en: {', '.join(sorted(estados_facturables))} | "
                f"Estado actual: '{estado_actual}'"
            )
        m.addAction("📄  Emitir Recibo",            lambda: self._recibo(pid))
        m.addSeparator()
        m.addAction("🖨️  Imprimir presupuesto PDF",  lambda: self._pdf(pid))
        m.addAction("📱  Enviar WhatsApp",           lambda: self._wa(pid))
        m.exec(self.tabla.viewport().mapToGlobal(pos))

    def _enviar_a_taller(self, pid: int) -> None:
        """Cambia estado a 'En Taller' directamente."""
        ok = get_provider().pedidos.cambiar_estado(pid, "En Taller")
        if ok:
            self.refrescar()
        else:
            QMessageBox.warning(self, "Error", "No se pudo cambiar el estado.")

    # Guardar / cargar vistas
    def _get_filtro_actual(self):
        return {
            "estados": self.btn_estado.get_sel(),
            "desde":   self.date_desde.date().toString("yyyy-MM-dd"),
            "hasta":   self.date_hasta.date().toString("yyyy-MM-dd"),
            "buscar":  self.inp_buscar.text().strip(),
            "cli_id":  self.cmb_cli.currentData() or 0,
        }

    def _guardar_vista(self):
        dlg = _DlgGuardarVista(self)
        if not dlg.exec() or not dlg.nombre(): return
        filtro = self._get_filtro_actual(); filtro["nombre"] = dlg.nombre()
        try:
            cfg = get_provider().config
            raw = cfg.get("filtros_guardados_pedidos", "[]")
            lst = json.loads(raw)
            lst = [f for f in lst if f.get("nombre") != dlg.nombre()]
            lst.append(filtro)
            cfg.set("filtros_guardados_pedidos", json.dumps(lst))
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e)); return
        self._cargar_vistas()
        idx = self.cmb_vistas.findText(dlg.nombre())
        if idx >= 0:
            self.cmb_vistas.blockSignals(True); self.cmb_vistas.setCurrentIndex(idx); self.cmb_vistas.blockSignals(False)

    def _eliminar_vista(self):
        nombre = self.cmb_vistas.currentText()
        if not nombre: return
        try:
            cfg = get_provider().config
            raw = cfg.get("filtros_guardados_pedidos", "[]")
            lst = json.loads(raw)
            lst = [f for f in lst if f.get("nombre") != nombre]
            cfg.set("filtros_guardados_pedidos", json.dumps(lst))
        except Exception: pass
        self._cargar_vistas()

    def _cargar_vistas(self):
        self.cmb_vistas.blockSignals(True); self.cmb_vistas.clear(); self.cmb_vistas.addItem("")
        try:
            raw = get_provider().config.get("filtros_guardados_pedidos", "[]")
            for f in json.loads(raw): self.cmb_vistas.addItem(f.get("nombre",""), f)
        except Exception: pass
        self.cmb_vistas.blockSignals(False)

    def _aplicar_vista(self, idx):
        if idx <= 0: return
        f = self.cmb_vistas.currentData()
        if not f: return
        self.btn_estado.set_sel(f.get("estados",[]))
        if f.get("desde"): self.date_desde.setDate(QDate.fromString(f["desde"],"yyyy-MM-dd"))
        if f.get("hasta"): self.date_hasta.setDate(QDate.fromString(f["hasta"],"yyyy-MM-dd"))
        self.inp_buscar.setText(f.get("buscar",""))
        if f.get("cli_id"):
            i = self.cmb_cli.findData(f["cli_id"])
            if i >= 0: self.cmb_cli.setCurrentIndex(i)
        self._filtrar()

    # Acciones
    def _editar(self, pid):
        if not pid: return
        from views.dialogs.dialogo_pedido import DialogoPedido
        dlg = DialogoPedido(pedido_id=pid, parent=self)
        dlg.pedido_guardado.connect(lambda _: self.refrescar())
        dlg.exec()

    def _nuevo_pedido(self):
        from views.dialogs.dialogo_pedido import DialogoPedido
        dlg = DialogoPedido(parent=self)
        dlg.pedido_guardado.connect(lambda _: self.refrescar())
        dlg.exec()

    def _wa(self, pid):
        p = get_provider().pedidos.get_by_id(pid)
        c = get_provider().clientes.get_by_id(p.cliente_id)
        from utils.helpers import abrir_whatsapp_presupuesto
        if not abrir_whatsapp_presupuesto(c.nombre,c.whatsapp,p.nro_pedido,p.total,p.fecha_creacion):
            QMessageBox.warning(self,"WhatsApp","Sin WhatsApp registrado.")

    def _pdf(self, pid):
        try:
            from utils.pdf_generator import generar_presupuesto
            from db.database import DatabaseManager
            from PySide6.QtCore import QUrl; from PySide6.QtGui import QDesktopServices
            p=get_provider().pedidos.get_by_id(pid); items=get_provider().detalle.get_by_pedido(pid)
            c=get_provider().clientes.get_by_id(p.cliente_id); cfg=get_provider().config.get_datos_imprenta()
            out=str(DatabaseManager().presupuestos_dir/f"{p.nro_pedido}.pdf")
            generar_presupuesto(p,items,c,cfg,out); QDesktopServices.openUrl(QUrl.fromLocalFile(out))
        except Exception as e: QMessageBox.warning(self,"Error PDF",str(e))

    def _pago(self, pid):
        from views.dialogs.dialogo_pago import DialogoPago
        p = get_provider().pedidos.get_by_id(pid)
        if DialogoPago(pid, p.saldo, self).exec(): self.refrescar()

    def _factura(self, pid):
        from views.dialogs.dialogo_factura import DialogoEmitirFactura
        p=get_provider().pedidos.get_by_id(pid); c=get_provider().clientes.get_by_id(p.cliente_id)
        if DialogoEmitirFactura(pedido=p,cliente=c,parent=self).exec(): self.refrescar()

    def _recibo(self, pid):
        from views.dialogs.dialogo_recibo import DialogoRecibo
        p=get_provider().pedidos.get_by_id(pid); c=get_provider().clientes.get_by_id(p.cliente_id)
        if DialogoRecibo(pedido=p,cliente=c,parent=self).exec(): self.refrescar()

    def _exportar(self):
        from PySide6.QtWidgets import QFileDialog; from pathlib import Path
        ruta,_=QFileDialog.getSaveFileName(self,"Exportar",str(Path.home()/"pedidos.csv"),"CSV (*.csv)")
        if not ruta: return
        try:
            with open(ruta,"w",encoding="utf-8-sig") as f:
                f.write("N°;Creación;Entrega;Cliente;Usuario;Estado;Total;Seña;Saldo\n")
                for p in self._pedidos:
                    f.write(";".join([p.nro_pedido,fmt_fecha(p.fecha_creacion),fmt_fecha(p.fecha_entrega),
                        p.cliente_nombre,p.usuario_nombre,p.estado,str(p.total),str(p.sena),str(p.saldo)])+"\n")
            QMessageBox.information(self,"OK",f"Guardado:\n{ruta}")
        except Exception as e: QMessageBox.warning(self,"Error",str(e))
