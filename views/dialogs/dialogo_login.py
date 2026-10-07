"""
Diálogo de login. Muestra en splash antes de la app principal.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut

from models.usuario_model import UsuarioModel, Usuario
from network.data_provider import get_provider


class DialogoLogin(QDialog):
    """Pantalla de login con opción recordar usuario."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.model = get_provider().usuarios
        self.usuario_logueado: Usuario | None = None
        self.setWindowTitle("Gestión Imprenta Pro — Acceso")
        self.setFixedSize(380, 320)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self._build_ui()
        self._pre_cargar_usuario()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(30, 24, 30, 24)

        # Logo/título
        lbl_titulo = QLabel("🖨️  Gestión Imprenta Pro")
        lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_titulo.setStyleSheet(
            "font-size: 16pt; font-weight: bold; color: #e94560;"
        )
        layout.addWidget(lbl_titulo)

        lbl_sub = QLabel("Ingresá tus credenciales para continuar")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setStyleSheet("color: #a0a0b0; font-size: 9pt;")
        layout.addWidget(lbl_sub)

        # Formulario
        form = QFormLayout()
        form.setSpacing(10)

        self.inp_user = QLineEdit()
        self.inp_user.setPlaceholderText("usuario")
        self.inp_user.setMinimumHeight(34)

        self.inp_pass = QLineEdit()
        self.inp_pass.setPlaceholderText("contraseña")
        self.inp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_pass.setMinimumHeight(34)
        self.inp_pass.returnPressed.connect(self._login)

        form.addRow("Usuario:", self.inp_user)
        form.addRow("Contraseña:", self.inp_pass)
        layout.addLayout(form)

        self.chk_recordar = QCheckBox("Recordar usuario en este equipo")
        layout.addWidget(self.chk_recordar)

        # Botón
        self.btn_login = QPushButton("🔐  Ingresar")
        self.btn_login.setObjectName("btn_primary")
        self.btn_login.setMinimumHeight(38)
        self.btn_login.clicked.connect(self._login)
        layout.addWidget(self.btn_login)

        self.lbl_error = QLabel("")
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_error.setStyleSheet("color: #e04040; font-size: 9pt;")
        layout.addWidget(self.lbl_error)

        QShortcut(QKeySequence("Return"), self).activated.connect(self._login)

    def _pre_cargar_usuario(self) -> None:
        """Pre-carga el usuario si tenía 'recordar' activo."""
        recordado = self.model.get_usuario_recordado()
        if recordado:
            self.inp_user.setText(recordado)
            self.chk_recordar.setChecked(True)
            self.inp_pass.setFocus()
        else:
            self.inp_user.setFocus()

    def _login(self) -> None:
        username = self.inp_user.text().strip()
        password = self.inp_pass.text()

        if not username or not password:
            self.lbl_error.setText("Completá usuario y contraseña.")
            return

        usuario = self.model.autenticar(username, password)
        if not usuario:
            self.lbl_error.setText("❌  Usuario o contraseña incorrectos.")
            self.inp_pass.clear()
            self.inp_pass.setFocus()
            return

        # Guardar preferencia recordar
        recordar = self.chk_recordar.isChecked()
        self.model.guardar_recordar(username, recordar)
        if not recordar:
            # Limpiar cualquier recordar previo de otros usuarios
            for u in self.model.get_all():
                if u.username != username and u.recordar:
                    self.model.guardar_recordar(u.username, False)

        self.usuario_logueado = usuario
        self.accept()
