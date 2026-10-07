"""
Diálogos para gestión de clientes:
- DialogoClienteRapido: mini-form para crear cliente desde pedido
- DialogoCliente: form completo para ABM
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QGroupBox, QMessageBox, QDialogButtonBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal

from models.cliente_model import ClienteModel, Cliente
from network.data_provider import get_provider


class DialogoClienteRapido(QDialog):
    """Mini-form para crear cliente rápido desde el diálogo de pedido."""

    cliente_creado = Signal(int, str)  # (id, nombre)

    def __init__(self, nombre_inicial: str = "", parent=None) -> None:
        super().__init__(parent)
        self.model = get_provider().clientes
        self.setWindowTitle("Nuevo Cliente")
        self.setMinimumWidth(380)
        self.setModal(True)
        self._build_ui(nombre_inicial)

    def _build_ui(self, nombre_inicial: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        titulo = QLabel("👤  Nuevo Cliente — sin salir del pedido")
        titulo.setObjectName("lbl_header")
        layout.addWidget(titulo)

        info = QLabel("Solo el nombre es obligatorio. Podés completar el resto después desde Ver/Editar.")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(8)

        self.inp_nombre = QLineEdit(nombre_inicial)
        self.inp_nombre.setPlaceholderText("Nombre completo o empresa *")
        self.inp_tel    = QLineEdit()
        self.inp_tel.setPlaceholderText("Teléfono")
        self.inp_wa     = QLineEdit()
        self.inp_wa.setPlaceholderText("Número WhatsApp (ej: 3460123456)")
        self.inp_email  = QLineEdit()
        self.inp_email.setPlaceholderText("email@ejemplo.com")
        self.inp_cuit   = QLineEdit()
        self.inp_cuit.setPlaceholderText("20-12345678-9")
        self.inp_dir    = QLineEdit()
        self.inp_dir.setPlaceholderText("Dirección")

        form.addRow("Nombre *:", self.inp_nombre)
        form.addRow("Teléfono:", self.inp_tel)
        form.addRow("WhatsApp:", self.inp_wa)
        form.addRow("Email:", self.inp_email)
        form.addRow("CUIT:", self.inp_cuit)
        form.addRow("Dirección:", self.inp_dir)
        layout.addLayout(form)

        # Botones
        btn_layout = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_guardar  = QPushButton("💾  Guardar")
        btn_guardar.setObjectName("btn_primary")
        btn_guardar.setDefault(True)
        btn_cancelar.clicked.connect(self.reject)
        btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(btn_cancelar)
        btn_layout.addWidget(btn_guardar)
        layout.addLayout(btn_layout)

        self.inp_nombre.setFocus()
        # Enter guarda, Esc cancela (comportamiento estándar de QDialog)
        self.inp_nombre.returnPressed.connect(self._guardar)

    def _guardar(self) -> None:
        nombre = self.inp_nombre.text().strip()
        tel    = self.inp_tel.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Requerido", "El nombre es obligatorio.")
            self.inp_nombre.setFocus()
            return

        # Evitar duplicados (mismo nombre, case-insensitive)
        try:
            for c in self.model.get_all(solo_activos=False):
                if c.nombre.lower() == nombre.lower():
                    QMessageBox.warning(
                        self, "Duplicado",
                        f"Ya existe un cliente llamado '{c.nombre}'.")
                    return
        except Exception:
            pass

        cliente = Cliente(
            nombre=nombre,
            telefono=tel,
            whatsapp=self.inp_wa.text().strip() or tel,
            email=self.inp_email.text().strip(),
            cuit=self.inp_cuit.text().strip(),
            direccion=self.inp_dir.text().strip(),
        )
        nuevo_id = self.model.insertar(cliente)
        if nuevo_id:
            self.cliente_creado.emit(nuevo_id, nombre)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo crear el cliente.")


class DialogoCliente(QDialog):
    """Form completo para crear o editar un cliente."""

    def __init__(self, cliente_id: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.model = get_provider().clientes
        self.cliente_id = cliente_id
        self.setWindowTitle("Nuevo Cliente" if not cliente_id else "Editar Cliente")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._build_ui()
        if cliente_id:
            self._cargar_cliente()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        grp = QGroupBox("Datos del cliente")
        form = QFormLayout(grp)
        form.setSpacing(10)

        self.inp_nombre = QLineEdit()
        self.inp_tel    = QLineEdit()
        self.inp_wa     = QLineEdit()
        self.inp_email  = QLineEdit()
        self.inp_cuit   = QLineEdit()
        self.inp_dir    = QLineEdit()
        self.inp_notas  = QTextEdit()
        self.inp_notas.setMaximumHeight(70)
        self.chk_activo = QCheckBox("Cliente activo")
        self.chk_activo.setChecked(True)

        form.addRow("Nombre *:", self.inp_nombre)
        form.addRow("Teléfono:", self.inp_tel)
        form.addRow("WhatsApp:", self.inp_wa)
        form.addRow("Email:", self.inp_email)
        form.addRow("CUIT:", self.inp_cuit)
        form.addRow("Dirección:", self.inp_dir)
        form.addRow("Notas:", self.inp_notas)
        form.addRow("", self.chk_activo)
        layout.addWidget(grp)

        # Botones
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Save).setText("💾  Guardar")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._guardar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _cargar_cliente(self) -> None:
        c = self.model.get_by_id(self.cliente_id)
        if not c:
            return
        self.inp_nombre.setText(c.nombre)
        self.inp_tel.setText(c.telefono)
        self.inp_wa.setText(c.whatsapp)
        self.inp_email.setText(c.email)
        self.inp_cuit.setText(c.cuit)
        self.inp_dir.setText(c.direccion)
        self.inp_notas.setPlainText(c.notas)
        self.chk_activo.setChecked(c.activo)

    def _guardar(self) -> None:
        nombre = self.inp_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Requerido", "El nombre es obligatorio.")
            return

        c = Cliente(
            id=self.cliente_id,
            nombre=nombre,
            telefono=self.inp_tel.text().strip(),
            whatsapp=self.inp_wa.text().strip(),
            email=self.inp_email.text().strip(),
            cuit=self.inp_cuit.text().strip(),
            direccion=self.inp_dir.text().strip(),
            notas=self.inp_notas.toPlainText().strip(),
            activo=self.chk_activo.isChecked(),
        )
        ok = self.model.insertar(c) if not self.cliente_id else self.model.actualizar(c)
        if ok:
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo guardar el cliente.")
