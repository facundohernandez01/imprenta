"""
ABM de usuarios del sistema y diálogo cambio de contraseña.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialogButtonBox, QCheckBox
)
from PySide6.QtCore import Qt

from models.usuario_model import UsuarioModel, Usuario
from network.data_provider import get_provider


class ABMUsuarios(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = get_provider().usuarios
        self.setWindowTitle("Gestión de Usuarios")
        self.setMinimumSize(600, 400)
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        tb = QHBoxLayout()
        btn_nuevo    = QPushButton("➕  Nuevo")
        btn_editar   = QPushButton("✏️  Editar")
        btn_desact   = QPushButton("🚫  Desactivar")
        btn_desact.setObjectName("btn_danger")
        btn_nuevo.clicked.connect(self._nuevo)
        btn_editar.clicked.connect(self._editar)
        btn_desact.clicked.connect(self._desactivar)
        for b in [btn_nuevo, btn_editar, btn_desact]:
            tb.addWidget(b)
        tb.addStretch()
        layout.addLayout(tb)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(
            ["Usuario", "Nombre", "Rol", "Activo", "Último login"]
        )
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 120)
        self.tabla.setColumnWidth(2, 100)
        self.tabla.setColumnWidth(3, 70)
        self.tabla.setColumnWidth(4, 160)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.doubleClicked.connect(self._editar)
        layout.addWidget(self.tabla)

    def _cargar(self):
        self.tabla.setRowCount(0)
        for u in self.model.get_all():
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            for col, val in enumerate([
                u.username, u.nombre, u.rol,
                "✅" if u.activo else "❌", u.ultimo_login or ""
            ]):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, u.id)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter
                    if col in (0,2,3) else Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.tabla.setItem(row, col, item)
            self.tabla.setRowHeight(row, 30)

    def _get_id(self):
        row = self.tabla.currentRow()
        if row < 0: return 0
        item = self.tabla.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else 0

    def _nuevo(self):
        dlg = _FormUsuario(parent=self)
        if dlg.exec(): self._cargar()

    def _editar(self):
        uid = self._get_id()
        if not uid: return
        u = next((x for x in self.model.get_all() if x.id == uid), None)
        if not u: return
        dlg = _FormUsuario(usuario=u, parent=self)
        if dlg.exec(): self._cargar()

    def _desactivar(self):
        uid = self._get_id()
        if not uid: return
        usuario_actual = UsuarioModel.usuario_actual()
        if usuario_actual and usuario_actual.id == uid:
            QMessageBox.warning(self, "Error", "No podés desactivar tu propio usuario.")
            return
        resp = QMessageBox.question(self, "Confirmar", "¿Desactivar este usuario?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp == QMessageBox.StandardButton.Yes:
            u = next((x for x in self.model.get_all() if x.id == uid), None)
            if u:
                u.activo = False
                self.model.actualizar(u)
                self._cargar()


class _FormUsuario(QDialog):
    def __init__(self, usuario: Usuario = None, parent=None):
        super().__init__(parent)
        self.model   = get_provider().usuarios
        self.usuario = usuario
        self.setWindowTitle("Nuevo Usuario" if not usuario else "Editar Usuario")
        self.setMinimumWidth(380)
        self._build_ui()
        if usuario: self._cargar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout(); form.setSpacing(10)
        self.inp_user   = QLineEdit()
        self.inp_nombre = QLineEdit()
        self.cmb_rol    = QComboBox()
        self.cmb_rol.addItems(["operador", "admin", "supervisor"])
        self.inp_pass   = QLineEdit(); self.inp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_pass.setPlaceholderText("Dejar vacío para no cambiar" if self.usuario else "Contraseña *")
        self.inp_pass2  = QLineEdit(); self.inp_pass2.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_pass2.setPlaceholderText("Confirmar contraseña")
        self.chk_activo = QCheckBox("Activo"); self.chk_activo.setChecked(True)
        form.addRow("Usuario *:", self.inp_user)
        form.addRow("Nombre *:", self.inp_nombre)
        form.addRow("Rol:", self.cmb_rol)
        form.addRow("Contraseña:", self.inp_pass)
        form.addRow("Confirmar:", self.inp_pass2)
        form.addRow("", self.chk_activo)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._guardar); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _cargar(self):
        u = self.usuario
        self.inp_user.setText(u.username); self.inp_user.setReadOnly(True)
        self.inp_nombre.setText(u.nombre)
        self.cmb_rol.setCurrentText(u.rol)
        self.chk_activo.setChecked(u.activo)

    def _guardar(self):
        user   = self.inp_user.text().strip()
        nombre = self.inp_nombre.text().strip()
        if not user or not nombre:
            QMessageBox.warning(self, "Requerido", "Usuario y Nombre son obligatorios."); return
        pwd  = self.inp_pass.text()
        pwd2 = self.inp_pass2.text()
        if pwd and pwd != pwd2:
            QMessageBox.warning(self, "Error", "Las contraseñas no coinciden."); return
        if not self.usuario and not pwd:
            QMessageBox.warning(self, "Requerido", "La contraseña es obligatoria para nuevo usuario."); return
        u = Usuario(
            id=self.usuario.id if self.usuario else 0,
            username=user, nombre=nombre,
            rol=self.cmb_rol.currentText(),
            activo=self.chk_activo.isChecked(),
        )
        if self.usuario:
            ok = self.model.actualizar(u, nueva_password=pwd)
        else:
            ok = bool(self.model.insertar(u, password=pwd))
        if ok: self.accept()
        else: QMessageBox.critical(self, "Error", "No se pudo guardar. El usuario puede estar duplicado.")


class DialogoCambiarPassword(QDialog):
    def __init__(self, usuario: Usuario, parent=None):
        super().__init__(parent)
        self.model   = get_provider().usuarios
        self.usuario = usuario
        self.setWindowTitle("Cambiar Contraseña")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)
        form = QFormLayout(); form.setSpacing(10)
        self.inp_actual = QLineEdit(); self.inp_actual.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_nueva  = QLineEdit(); self.inp_nueva.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_conf   = QLineEdit(); self.inp_conf.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Contraseña actual:", self.inp_actual)
        form.addRow("Nueva contraseña:", self.inp_nueva)
        form.addRow("Confirmar:", self.inp_conf)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._guardar); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _guardar(self):
        actual = self.inp_actual.text()
        nueva  = self.inp_nueva.text()
        conf   = self.inp_conf.text()
        if not self.model.autenticar(self.usuario.username, actual):
            QMessageBox.warning(self, "Error", "Contraseña actual incorrecta."); return
        if len(nueva) < 4:
            QMessageBox.warning(self, "Error", "La nueva contraseña debe tener al menos 4 caracteres."); return
        if nueva != conf:
            QMessageBox.warning(self, "Error", "Las contraseñas no coinciden."); return
        self.model.actualizar(self.usuario, nueva_password=nueva)
        QMessageBox.information(self, "✅", "Contraseña cambiada correctamente.")
        self.accept()
