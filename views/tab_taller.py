"""
Tab 2: Taller. Kanban con buscador, paginación y drag&drop.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel,
    QFrame, QScrollArea, QSizePolicy, QMessageBox, QLineEdit,
    QSpinBox, QComboBox
)
from PySide6.QtCore import Qt, QMimeData, QByteArray, Signal
from PySide6.QtGui import QDrag

from models.pedido_model import Pedido, ESTADO_COLORES
from network.data_provider import get_provider
from utils.helpers import fmt_moneda, fmt_fecha, es_vencida
from utils.styles import AppStyles

COLUMNAS_KANBAN = [
    ("🎨  Diseño / Aprobación",  ["Diseño", "Aprobación Cliente"]),
    ("🔧  En Taller",            ["En Taller"]),
    ("✅  Listo para Entregar",  ["Listo para Entregar"]),
]
PAGE_SIZE = 20


class KanbanCard(QFrame):
    sig_click = Signal(int)

    def __init__(self, pedido: Pedido, parent=None):
        super().__init__(parent)
        self.pedido = pedido
        self.setObjectName("kanban_card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(10,8,10,8); lay.setSpacing(2)
        lbl_nro = QLabel(f"<b>{self.pedido.nro_pedido}</b>")
        lbl_nro.setStyleSheet(f"color:{AppStyles.ACCENT};font-size:10pt;background:transparent;border:none;")
        lay.addWidget(lbl_nro)
        lbl_cli = QLabel(self.pedido.cliente_nombre)
        lbl_cli.setStyleSheet(f"color:{AppStyles.TEXT_MAIN};background:transparent;border:none;")
        lay.addWidget(lbl_cli)
        if self.pedido.usuario_nombre:
            lbl_usr = QLabel(f"👤 {self.pedido.usuario_nombre}")
            lbl_usr.setStyleSheet(f"color:{AppStyles.TEXT_DIM};font-size:8pt;background:transparent;border:none;")
            lay.addWidget(lbl_usr)
        if self.pedido.fecha_entrega:
            vencida = es_vencida(self.pedido.fecha_entrega, self.pedido.estado)
            color = AppStyles.DANGER if vencida else AppStyles.TEXT_DIM
            lbl_f = QLabel(f"📅 {fmt_fecha(self.pedido.fecha_entrega)}{' ⚠️' if vencida else ''}")
            lbl_f.setStyleSheet(f"color:{color};font-size:8pt;background:transparent;border:none;")
            lay.addWidget(lbl_f)
        lbl_tot = QLabel(fmt_moneda(self.pedido.total))
        lbl_tot.setStyleSheet(f"color:{AppStyles.SUCCESS};font-size:8pt;background:transparent;border:none;")
        lay.addWidget(lbl_tot)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._drag_start = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.MouseButton.LeftButton): return
        if not hasattr(self,"_drag_start"): return
        if (e.position().toPoint()-self._drag_start).manhattanLength() < 10: return
        drag = QDrag(self); mime = QMimeData()
        mime.setData("application/pedido-id", QByteArray(str(self.pedido.id).encode()))
        drag.setMimeData(mime); drag.exec(Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, e):
        self.sig_click.emit(self.pedido.id); super().mouseDoubleClickEvent(e)


class KanbanColumna(QGroupBox):
    sig_cambio = Signal(int, str)

    def __init__(self, titulo, estados, parent=None):
        super().__init__(titulo, parent)
        self.estados = estados
        self.setAcceptDrops(True)
        self.setMinimumWidth(230)
        self._cards: list[KanbanCard] = []
        self._pagina = 0

        layout = QVBoxLayout(self); layout.setSpacing(4); layout.setContentsMargins(6,16,6,6)
        self.lbl_count = QLabel("0 pedidos")
        self.lbl_count.setStyleSheet(f"color:{AppStyles.TEXT_DIM};font-size:8pt;")
        layout.addWidget(self.lbl_count)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setSpacing(5); self._cards_layout.setContentsMargins(0,0,0,0)
        self._cards_layout.addStretch()
        scroll.setWidget(self._cards_widget); layout.addWidget(scroll, stretch=1)

        # Paginación
        nav = QHBoxLayout()
        self.btn_prev = QPushButton("◀"); self.btn_prev.setFixedWidth(30)
        self.btn_prev.clicked.connect(lambda: self._ir_pagina(self._pagina-1))
        self.lbl_pag = QLabel(""); self.lbl_pag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pag.setStyleSheet(f"color:{AppStyles.TEXT_DIM};font-size:8pt;")
        self.btn_next = QPushButton("▶"); self.btn_next.setFixedWidth(30)
        self.btn_next.clicked.connect(lambda: self._ir_pagina(self._pagina+1))
        nav.addWidget(self.btn_prev); nav.addWidget(self.lbl_pag,1); nav.addWidget(self.btn_next)
        layout.addLayout(nav)
        self._all_pedidos: list[Pedido] = []

    def cargar(self, pedidos: list[Pedido], busqueda: str = ""):
        self._all_pedidos = pedidos
        if busqueda:
            b = busqueda.lower()
            self._all_pedidos = [p for p in pedidos
                if b in p.nro_pedido.lower() or b in p.cliente_nombre.lower()
                or b in (p.usuario_nombre or "").lower()]
        self._pagina = 0
        self._mostrar_pagina()

    def _ir_pagina(self, n):
        total_pages = max(1, (len(self._all_pedidos) + PAGE_SIZE - 1) // PAGE_SIZE)
        self._pagina = max(0, min(n, total_pages - 1))
        self._mostrar_pagina()

    def _mostrar_pagina(self):
        # Limpiar
        for c in self._cards:
            self._cards_layout.removeWidget(c); c.deleteLater()
        self._cards.clear()
        total = len(self._all_pedidos)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        start = self._pagina * PAGE_SIZE
        pagina_items = self._all_pedidos[start:start + PAGE_SIZE]
        for p in pagina_items:
            card = KanbanCard(p)
            card.sig_click.connect(self._on_click)
            self._cards_layout.insertWidget(self._cards_layout.count()-1, card)
            self._cards.append(card)
        self.lbl_count.setText(f"{total} pedido{'s' if total!=1 else ''}")
        if total_pages > 1:
            self.lbl_pag.setText(f"{self._pagina+1}/{total_pages}")
            self.btn_prev.setEnabled(self._pagina > 0)
            self.btn_next.setEnabled(self._pagina < total_pages-1)
            self.btn_prev.setVisible(True); self.btn_next.setVisible(True)
        else:
            self.lbl_pag.setText(""); self.btn_prev.setVisible(False); self.btn_next.setVisible(False)

    def _on_click(self, pid):
        from views.dialogs.dialogo_pedido import DialogoPedido
        DialogoPedido(pedido_id=pid, parent=self).exec()

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/pedido-id"):
            e.acceptProposedAction()
            self.setStyleSheet(self.styleSheet() + f"QGroupBox{{border-color:{AppStyles.ACCENT};}}")

    def dragLeaveEvent(self, e): self.setStyleSheet("")

    def dropEvent(self, e):
        self.setStyleSheet("")
        pid = int(e.mimeData().data("application/pedido-id").toStdString())
        self.sig_cambio.emit(pid, self.estados[0])
        e.acceptProposedAction()


class TabTaller(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._columnas: list[KanbanColumna] = []
        self._build_ui()
        self.refrescar()

    def _build_ui(self):
        layout = QVBoxLayout(self); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        # Toolbar
        tb = QHBoxLayout()
        lbl = QLabel("🔧  Taller"); lbl.setObjectName("lbl_header"); tb.addWidget(lbl)

        # Buscador
        self.inp_buscar = QLineEdit(); self.inp_buscar.setPlaceholderText("🔍 Buscar pedido, cliente...")
        self.inp_buscar.setFixedWidth(240)
        self.inp_buscar.textChanged.connect(lambda _: self._actualizar_busqueda())
        tb.addWidget(self.inp_buscar)

        # Filtro de estado visible
        self.cmb_filtro = QComboBox()
        self.cmb_filtro.addItems(["Todos los estados", "Diseño/Aprobación", "En Taller", "Listo para Entregar"])
        self.cmb_filtro.currentIndexChanged.connect(lambda _: self.refrescar())
        tb.addWidget(self.cmb_filtro)

        tb.addStretch()
        btn_orden = QPushButton("🖨️ Orden de Taller PDF"); btn_orden.clicked.connect(self._pdf_taller)
        btn_ref   = QPushButton("🔄 Refrescar"); btn_ref.clicked.connect(self.refrescar)
        tb.addWidget(btn_orden); tb.addWidget(btn_ref)
        layout.addLayout(tb)

        # Columnas kanban
        kl = QHBoxLayout(); kl.setSpacing(10)
        for titulo, estados in COLUMNAS_KANBAN:
            col = KanbanColumna(titulo, estados)
            col.sig_cambio.connect(self._cambiar_estado)
            self._columnas.append(col); kl.addWidget(col)
        layout.addLayout(kl, stretch=1)

    def _actualizar_busqueda(self):
        busqueda = self.inp_buscar.text().strip()
        todos_estados = [e for _, estados in COLUMNAS_KANBAN for e in estados]
        pedidos = get_provider().pedidos.get_por_estado(todos_estados)
        for col in self._columnas:
            pedidos_col = [p for p in pedidos if p.estado in col.estados]
            col.cargar(pedidos_col, busqueda)

    def refrescar(self):
        todos_estados = [e for _, estados in COLUMNAS_KANBAN for e in estados]
        pedidos = get_provider().pedidos.get_por_estado(todos_estados)
        busqueda = self.inp_buscar.text().strip()
        filtro_idx = self.cmb_filtro.currentIndex()
        for col in self._columnas:
            if filtro_idx == 0:
                pedidos_col = [p for p in pedidos if p.estado in col.estados]
            else:
                estados_map = {1:["Diseño","Aprobación Cliente"], 2:["En Taller"], 3:["Listo para Entregar"]}
                estados_deseados = estados_map.get(filtro_idx, col.estados)
                pedidos_col = [p for p in pedidos if p.estado in col.estados and p.estado in estados_deseados]
            col.cargar(pedidos_col, busqueda)

    def _cambiar_estado(self, pid, estado):
        if get_provider().pedidos.cambiar_estado(pid, estado): self.refrescar()
        else: QMessageBox.warning(self,"Error","No se pudo cambiar el estado.")

    def _pdf_taller(self):
        try:
            from utils.pdf_generator import generar_orden_taller
            from db.database import DatabaseManager
            from PySide6.QtCore import QUrl; from PySide6.QtGui import QDesktopServices
            from utils.helpers import hoy_str
            pedidos = get_provider().pedidos.get_por_estado(["En Taller"])
            if not pedidos: QMessageBox.information(self,"Sin pedidos","No hay pedidos 'En Taller'."); return
            detalle_map = {p.id: get_provider().detalle.get_by_pedido(p.id) for p in pedidos}
            out = str(DatabaseManager().presupuestos_dir/f"orden_taller_{hoy_str()}.pdf")
            generar_orden_taller(pedidos, detalle_map, out)
            QDesktopServices.openUrl(QUrl.fromLocalFile(out))
        except Exception as e: QMessageBox.warning(self,"Error PDF",str(e))
