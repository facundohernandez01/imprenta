"""
Ventanas ABM: Clientes, Productos, Tipos de Trabajo, Insumos.
Todas comparten el mismo patrón: QTableWidget + botones Nuevo/Editar/Eliminar.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMessageBox,
    QLineEdit, QDoubleSpinBox, QFormLayout, QGroupBox, QComboBox,
    QDialogButtonBox, QCheckBox, QWidget
)
from PySide6.QtCore import Qt

from utils.styles import AppStyles
from network.data_provider import get_provider


# ─── ABM CLIENTES ─────────────────────────────────────────────────────────────

class ABMClientes(QDialog):
    """Ventana ABM completa para clientes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from models.cliente_model import ClienteModel
        self.model = get_provider().clientes
        self.setWindowTitle("Gestión de Clientes")
        self.setMinimumSize(800, 500)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Toolbar
        tb = QHBoxLayout()
        btn_nuevo   = QPushButton("➕  Nuevo")
        btn_editar  = QPushButton("✏️  Editar")
        btn_eliminar = QPushButton("🗑️  Dar de baja")
        btn_eliminar.setObjectName("btn_danger")
        btn_nuevo.clicked.connect(self._nuevo)
        btn_editar.clicked.connect(self._editar)
        btn_eliminar.clicked.connect(self._eliminar)
        for b in [btn_nuevo, btn_editar, btn_eliminar]:
            tb.addWidget(b)
        tb.addStretch()

        # Búsqueda
        self.inp_buscar = QLineEdit()
        self.inp_buscar.setPlaceholderText("Buscar cliente...")
        self.inp_buscar.setFixedWidth(200)
        self.inp_buscar.textChanged.connect(self._filtrar)
        tb.addWidget(self.inp_buscar)
        layout.addLayout(tb)

        # Tabla
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels([
            "Nombre", "Teléfono", "WhatsApp", "Email", "CUIT", "Activo"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.doubleClicked.connect(self._editar)
        layout.addWidget(self.tabla)

    def _cargar(self) -> None:
        self._todos = self.model.get_all(solo_activos=False)
        self._poblar(self._todos)

    def _filtrar(self) -> None:
        texto = self.inp_buscar.text().lower()
        filtrados = [c for c in self._todos
                     if texto in c.nombre.lower() or texto in (c.email or "").lower()]
        self._poblar(filtrados)

    def _poblar(self, clientes) -> None:
        self.tabla.setRowCount(0)
        for c in clientes:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            for col, val in enumerate([
                c.nombre, c.telefono, c.whatsapp, c.email, c.cuit,
                "✅" if c.activo else "❌"
            ]):
                item = QTableWidgetItem(val or "")
                item.setData(Qt.ItemDataRole.UserRole, c.id)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col == 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(row, col, item)
            self.tabla.setRowHeight(row, 32)

    def _get_id_seleccionado(self) -> int:
        row = self.tabla.currentRow()
        if row < 0:
            return 0
        item = self.tabla.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else 0

    def _nuevo(self) -> None:
        from views.dialogs.dialogo_cliente import DialogoCliente
        dlg = DialogoCliente(parent=self)
        if dlg.exec():
            self._cargar()

    def _editar(self) -> None:
        cid = self._get_id_seleccionado()
        if not cid:
            QMessageBox.information(self, "Info", "Seleccioná un cliente.")
            return
        from views.dialogs.dialogo_cliente import DialogoCliente
        dlg = DialogoCliente(cid, self)
        if dlg.exec():
            self._cargar()

    def _eliminar(self) -> None:
        cid = self._get_id_seleccionado()
        if not cid:
            return
        resp = QMessageBox.question(
            self, "Confirmar", "¿Dar de baja este cliente?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.model.eliminar_logico(cid)
            self._cargar()


# ─── ABM TIPOS DE TRABAJO ─────────────────────────────────────────────────────

class ABMTiposTrabajo(QDialog):
    """Ventana ABM para tipos de trabajo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from models.models import TipoTrabajoModel
        self.model = get_provider().tipos
        self.setWindowTitle("Tipos de Trabajo")
        self.setMinimumSize(500, 400)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        tb = QHBoxLayout()
        btn_nuevo   = QPushButton("➕  Nuevo")
        btn_editar  = QPushButton("✏️  Editar")
        btn_eliminar = QPushButton("🗑️  Eliminar")
        btn_eliminar.setObjectName("btn_danger")
        btn_nuevo.clicked.connect(self._nuevo)
        btn_editar.clicked.connect(self._editar)
        btn_eliminar.clicked.connect(self._eliminar)
        for b in [btn_nuevo, btn_editar, btn_eliminar]:
            tb.addWidget(b)
        tb.addStretch()
        layout.addLayout(tb)

        self.inp_buscar_tipo = QLineEdit()
        self.inp_buscar_tipo.setPlaceholderText("Buscar tipo...")
        self.inp_buscar_tipo.setFixedWidth(180)
        self.inp_buscar_tipo.textChanged.connect(self._filtrar_tipo)
        tb.addWidget(self.inp_buscar_tipo)

        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Nombre", "Descripción"])
        self.tabla.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 150)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.doubleClicked.connect(self._editar)
        layout.addWidget(self.tabla)

    def _cargar(self) -> None:
        self._todos_tipo = self.model.get_all()
        self._poblar_tipo(self._todos_tipo)

    def _filtrar_tipo(self) -> None:
        texto = self.inp_buscar_tipo.text().lower()
        filtrados = [t for t in self._todos_tipo if texto in t.nombre.lower()]
        self._poblar_tipo(filtrados)

    def _poblar_tipo(self, tipos) -> None:
        self.tabla.setRowCount(0)
        for t in tipos:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            for col, val in enumerate([t.nombre, t.descripcion]):
                item = QTableWidgetItem(val or "")
                item.setData(Qt.ItemDataRole.UserRole, t.id)
                self.tabla.setItem(row, col, item)
            self.tabla.setRowHeight(row, 30)

    def _get_id(self) -> int:
        row = self.tabla.currentRow()
        if row < 0:
            return 0
        item = self.tabla.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else 0

    def _nuevo(self) -> None:
        from models.models import TipoTrabajo
        dlg = _FormSimple("Nuevo Tipo de Trabajo", ["Nombre *", "Descripción"], self)
        if dlg.exec():
            vals = dlg.get_valores()
            if not vals[0]:
                QMessageBox.warning(self, "Requerido", "El nombre es obligatorio.")
                return
            self.model.insertar(TipoTrabajo(nombre=vals[0], descripcion=vals[1]))
            self._cargar()

    def _editar(self) -> None:
        tid = self._get_id()
        if not tid:
            return
        from models.models import TipoTrabajo
        tipos = self.model.get_all()
        t = next((x for x in tipos if x.id == tid), None)
        if not t:
            return
        dlg = _FormSimple("Editar Tipo", ["Nombre *", "Descripción"],
                           self, [t.nombre, t.descripcion])
        if dlg.exec():
            vals = dlg.get_valores()
            self.model.actualizar(TipoTrabajo(id=tid, nombre=vals[0], descripcion=vals[1]))
            self._cargar()

    def _eliminar(self) -> None:
        tid = self._get_id()
        if not tid:
            return
        resp = QMessageBox.question(self, "Confirmar", "¿Eliminar este tipo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp == QMessageBox.StandardButton.Yes:
            self.model.eliminar(tid)
            self._cargar()


# ─── ABM PRODUCTOS ────────────────────────────────────────────────────────────

class ABMProductos(QDialog):
    """Ventana ABM para productos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from models.models import ProductoModel
        self.model = get_provider().productos
        self.setWindowTitle("Gestión de Productos")
        self.setMinimumSize(700, 450)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        tb = QHBoxLayout()
        btn_nuevo   = QPushButton("➕  Nuevo")
        btn_editar  = QPushButton("✏️  Editar")
        btn_eliminar = QPushButton("🗑️  Dar de baja")
        btn_eliminar.setObjectName("btn_danger")
        btn_nuevo.clicked.connect(self._nuevo)
        btn_editar.clicked.connect(self._editar)
        btn_eliminar.clicked.connect(self._eliminar)
        for b in [btn_nuevo, btn_editar, btn_eliminar]:
            tb.addWidget(b)
        tb.addStretch()
        self.inp_buscar_prod = QLineEdit()
        self.inp_buscar_prod.setPlaceholderText("Buscar producto...")
        self.inp_buscar_prod.setFixedWidth(200)
        self.inp_buscar_prod.textChanged.connect(self._filtrar_prod)
        tb.addWidget(self.inp_buscar_prod)
        tb.addStretch()
        layout.addLayout(tb)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels([
            "Nombre", "Tipo", "Unidad", "Precio Base", "Activo"
        ])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(1, 130)
        self.tabla.setColumnWidth(2, 80)
        self.tabla.setColumnWidth(3, 100)
        self.tabla.setColumnWidth(4, 60)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.doubleClicked.connect(self._editar)
        layout.addWidget(self.tabla)

    def _cargar(self) -> None:
        self._todos_prod = self.model.get_all(solo_activos=False)
        self._poblar_prod(self._todos_prod)

    def _filtrar_prod(self) -> None:
        texto = self.inp_buscar_prod.text().lower()
        filtrados = [p for p in self._todos_prod
                     if texto in p.nombre.lower() or texto in p.tipo_nombre.lower()]
        self._poblar_prod(filtrados)

    def _poblar_prod(self, productos) -> None:
        from utils.helpers import fmt_moneda
        self.tabla.setRowCount(0)
        for p in productos:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            for col, val in enumerate([
                p.nombre, p.tipo_nombre, p.unidad,
                fmt_moneda(p.precio_base), "✅" if p.activo else "❌"
            ]):
                item = QTableWidgetItem(val or "")
                item.setData(Qt.ItemDataRole.UserRole, p.id)
                if col in (3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(row, col, item)
            self.tabla.setRowHeight(row, 30)

    def _get_id(self) -> int:
        row = self.tabla.currentRow()
        if row < 0:
            return 0
        item = self.tabla.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else 0

    def _nuevo(self) -> None:
        dlg = _FormProducto(parent=self)
        if dlg.exec():
            self._cargar()

    def _editar(self) -> None:
        pid = self._get_id()
        if not pid:
            return
        dlg = _FormProducto(prod_id=pid, parent=self)
        if dlg.exec():
            self._cargar()

    def _eliminar(self) -> None:
        pid = self._get_id()
        if not pid:
            return
        resp = QMessageBox.question(self, "Confirmar", "¿Dar de baja este producto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp == QMessageBox.StandardButton.Yes:
            self.model.eliminar_logico(pid)
            self._cargar()


class _FormProducto(QDialog):
    """Formulario interno para crear/editar producto."""

    def __init__(self, prod_id: int = 0, parent=None):
        super().__init__(parent)
        from models.models import ProductoModel, TipoTrabajoModel
        self.prod_model = get_provider().productos
        self.tipo_model = get_provider().tipos
        self.prod_id = prod_id
        self.setWindowTitle("Nuevo Producto" if not prod_id else "Editar Producto")
        self.setMinimumWidth(400)
        self._build_ui()
        if prod_id:
            self._cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.inp_nombre = QLineEdit()
        # Combo tipo con botón "+" para crear tipo inline
        tipo_row_widget = QWidget()
        tipo_hlay = QHBoxLayout(tipo_row_widget)
        tipo_hlay.setContentsMargins(0, 0, 0, 0); tipo_hlay.setSpacing(4)
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.setMinimumWidth(200)
        self._recargar_tipos()
        btn_nuevo_tipo = QPushButton("➕")
        btn_nuevo_tipo.setToolTip("Crear nuevo tipo de trabajo")
        btn_nuevo_tipo.setFixedWidth(32)
        btn_nuevo_tipo.clicked.connect(self._nuevo_tipo_inline)
        tipo_hlay.addWidget(self.cmb_tipo, 1)
        tipo_hlay.addWidget(btn_nuevo_tipo)
        self.inp_unidad = QLineEdit("unidad")
        self.spin_precio = QDoubleSpinBox()
        self.spin_precio.setRange(0, 9_999_999)
        self.spin_precio.setDecimals(2)
        self.spin_precio.setPrefix("$ ")
        self.chk_activo = QCheckBox("Activo")
        self.chk_activo.setChecked(True)
        form.addRow("Nombre *:", self.inp_nombre)
        form.addRow("Tipo:", tipo_row_widget)
        form.addRow("Unidad:", self.inp_unidad)
        form.addRow("Precio base:", self.spin_precio)
        form.addRow("", self.chk_activo)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._guardar)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _recargar_tipos(self, seleccionar_id=None) -> None:
        """Recarga el combo de tipos de trabajo."""
        current_id = seleccionar_id or self.cmb_tipo.currentData()
        self.cmb_tipo.clear()
        self.cmb_tipo.addItem("-- Sin tipo --", None)
        for t in self.tipo_model.get_all():
            self.cmb_tipo.addItem(t.nombre, t.id)
        if current_id:
            idx = self.cmb_tipo.findData(current_id)
            if idx >= 0:
                self.cmb_tipo.setCurrentIndex(idx)

    def _nuevo_tipo_inline(self) -> None:
        """Crea un tipo de trabajo sin cerrar el formulario de producto."""
        from models.models import TipoTrabajo
        dlg = _FormSimple("Nuevo Tipo de Trabajo", ["Nombre *", "Descripción"], self)
        if dlg.exec():
            vals = dlg.get_valores()
            if not vals[0]:
                QMessageBox.warning(self, "Requerido", "El nombre es obligatorio.")
                return
            nuevo_id = self.tipo_model.insertar(TipoTrabajo(nombre=vals[0], descripcion=vals[1]))
            if nuevo_id:
                self._recargar_tipos(seleccionar_id=nuevo_id)
            else:
                QMessageBox.warning(self, "Error", "No se pudo crear el tipo (¿nombre duplicado?).")

    def _cargar(self) -> None:
        p = self.prod_model.get_by_id(self.prod_id)
        if not p:
            return
        self.inp_nombre.setText(p.nombre)
        idx = self.cmb_tipo.findData(p.tipo_trabajo_id)
        if idx >= 0:
            self.cmb_tipo.setCurrentIndex(idx)
        self.inp_unidad.setText(p.unidad)
        self.spin_precio.setValue(p.precio_base)
        self.chk_activo.setChecked(p.activo)

    def _guardar(self) -> None:
        from models.models import Producto
        nombre = self.inp_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Requerido", "El nombre es obligatorio.")
            return
        p = Producto(
            id=self.prod_id,
            nombre=nombre,
            tipo_trabajo_id=self.cmb_tipo.currentData(),
            unidad=self.inp_unidad.text().strip() or "unidad",
            precio_base=self.spin_precio.value(),
            activo=self.chk_activo.isChecked(),
        )
        ok = self.prod_model.insertar(p) if not self.prod_id else self.prod_model.actualizar(p)
        if ok:
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo guardar.")


# ─── ABM INSUMOS ──────────────────────────────────────────────────────────────

class ABMInsumos(QDialog):
    """Ventana ABM para insumos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from models.models import InsumoModel
        self.model = get_provider().insumos
        self.setWindowTitle("Gestión de Insumos")
        self.setMinimumSize(550, 400)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        tb = QHBoxLayout()
        btn_nuevo   = QPushButton("➕  Nuevo")
        btn_editar  = QPushButton("✏️  Editar")
        btn_eliminar = QPushButton("🗑️  Eliminar")
        btn_eliminar.setObjectName("btn_danger")
        btn_nuevo.clicked.connect(self._nuevo)
        btn_editar.clicked.connect(self._editar)
        btn_eliminar.clicked.connect(self._eliminar)
        for b in [btn_nuevo, btn_editar, btn_eliminar]:
            tb.addWidget(b)
        tb.addStretch()
        layout.addLayout(tb)

        self.inp_buscar_ins = QLineEdit()
        self.inp_buscar_ins.setPlaceholderText("Buscar insumo...")
        self.inp_buscar_ins.setFixedWidth(180)
        self.inp_buscar_ins.textChanged.connect(self._filtrar_ins)
        tb.addWidget(self.inp_buscar_ins)

        self.tabla = QTableWidget(0, 3)
        self.tabla.setHorizontalHeaderLabels(["Nombre", "Costo Unitario", "Stock Actual"])
        self.tabla.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(1, 130)
        self.tabla.setColumnWidth(2, 130)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.doubleClicked.connect(self._editar)
        layout.addWidget(self.tabla)

    def _cargar(self) -> None:
        self._todos_ins = self.model.get_all()
        self._poblar_ins(self._todos_ins)

    def _filtrar_ins(self) -> None:
        texto = self.inp_buscar_ins.text().lower()
        filtrados = [i for i in self._todos_ins if texto in i.nombre.lower()]
        self._poblar_ins(filtrados)

    def _poblar_ins(self, insumos) -> None:
        from utils.helpers import fmt_moneda
        self.tabla.setRowCount(0)
        for i in insumos:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            for col, val in enumerate([
                i.nombre, fmt_moneda(i.costo_unitario), str(i.stock_actual)
            ]):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, i.id)
                if col > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tabla.setItem(row, col, item)
            self.tabla.setRowHeight(row, 30)

    def _get_id(self) -> int:
        row = self.tabla.currentRow()
        if row < 0:
            return 0
        item = self.tabla.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else 0

    def _nuevo(self) -> None:
        dlg = _FormSimple("Nuevo Insumo",
                           ["Nombre *", "Costo Unitario ($)", "Stock Actual"], self)
        if dlg.exec():
            vals = dlg.get_valores()
            if not vals[0]:
                return
            from models.models import Insumo
            self.model.insertar(Insumo(
                nombre=vals[0],
                costo_unitario=float(vals[1] or 0),
                stock_actual=float(vals[2] or 0),
            ))
            self._cargar()

    def _editar(self) -> None:
        iid = self._get_id()
        if not iid:
            return
        insumos = self.model.get_all()
        ins = next((x for x in insumos if x.id == iid), None)
        if not ins:
            return
        dlg = _FormSimple("Editar Insumo",
                           ["Nombre *", "Costo Unitario ($)", "Stock Actual"],
                           self, [ins.nombre, str(ins.costo_unitario), str(ins.stock_actual)])
        if dlg.exec():
            vals = dlg.get_valores()
            from models.models import Insumo
            self.model.actualizar(Insumo(
                id=iid, nombre=vals[0],
                costo_unitario=float(vals[1] or 0),
                stock_actual=float(vals[2] or 0),
            ))
            self._cargar()

    def _eliminar(self) -> None:
        iid = self._get_id()
        if not iid:
            return
        resp = QMessageBox.question(self, "Confirmar", "¿Eliminar este insumo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp == QMessageBox.StandardButton.Yes:
            self.model.eliminar(iid)
            self._cargar()


# ─── FORM SIMPLE GENÉRICO ─────────────────────────────────────────────────────

class _FormSimple(QDialog):
    """Formulario genérico de N campos de texto."""

    def __init__(self, titulo: str, campos: list[str],
                 parent=None, valores: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumWidth(360)
        self._inputs: list[QLineEdit] = []
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for i, campo in enumerate(campos):
            inp = QLineEdit()
            if valores and i < len(valores):
                inp.setText(str(valores[i]))
            form.addRow(campo + ":", inp)
            self._inputs.append(inp)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_valores(self) -> list[str]:
        return [inp.text().strip() for inp in self._inputs]
