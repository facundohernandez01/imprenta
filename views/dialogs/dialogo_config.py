"""
Diálogo de configuración inicial de la imprenta.
Se muestra en el primer inicio o desde Menú > Configuración.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog,
    QGroupBox, QMessageBox, QDialogButtonBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from models.config_model import ConfigModel
from network.data_provider import get_provider


class DialogoConfig(QDialog):
    """Formulario de configuración de la imprenta."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.config_model = get_provider().config
        self.logo_path: str = ""
        self.setWindowTitle("Configuración de la Imprenta")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._build_ui()
        self._cargar_datos()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Título
        titulo = QLabel("⚙️  Datos de la Imprenta")
        titulo.setObjectName("lbl_header")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titulo)

        sub = QLabel("Complete los datos que aparecerán en los presupuestos.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #a0a0b0; font-size: 9pt;")
        layout.addWidget(sub)

        # Formulario
        grp = QGroupBox("Datos fiscales y de contacto")
        form = QFormLayout(grp)
        form.setSpacing(10)

        self.inp_razon    = QLineEdit(); self.inp_razon.setPlaceholderText("Imprenta El Sol S.R.L.")
        self.inp_cuit     = QLineEdit(); self.inp_cuit.setPlaceholderText("20-12345678-9")
        self.inp_dir      = QLineEdit(); self.inp_dir.setPlaceholderText("Av. San Martín 1234, Ciudad")
        self.inp_tel      = QLineEdit(); self.inp_tel.setPlaceholderText("03460 15-123456")
        self.inp_email    = QLineEdit(); self.inp_email.setPlaceholderText("imprenta@email.com")

        form.addRow("Razón Social *:", self.inp_razon)
        form.addRow("CUIT:", self.inp_cuit)
        form.addRow("Dirección:", self.inp_dir)
        form.addRow("Teléfono:", self.inp_tel)
        form.addRow("Email:", self.inp_email)
        layout.addWidget(grp)

        # Logo
        grp_logo = QGroupBox("Logo (opcional)")
        logo_lay = QHBoxLayout(grp_logo)
        self.lbl_logo = QLabel("Sin logo seleccionado")
        self.lbl_logo.setStyleSheet("color: #a0a0b0;")
        self.lbl_logo_preview = QLabel()
        self.lbl_logo_preview.setFixedSize(80, 50)
        self.lbl_logo_preview.setStyleSheet("border: 1px solid #2a2a4a;")
        btn_logo = QPushButton("📁  Seleccionar logo...")
        btn_logo.clicked.connect(self._seleccionar_logo)
        logo_lay.addWidget(self.lbl_logo_preview)
        logo_lay.addWidget(self.lbl_logo)
        logo_lay.addStretch()
        logo_lay.addWidget(btn_logo)
        layout.addWidget(grp_logo)

        # Botones
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Save).setText("💾  Guardar")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._guardar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _cargar_datos(self) -> None:
        """Carga datos existentes si hay configuración guardada."""
        self.inp_razon.setText(self.config_model.get("razon_social"))
        self.inp_cuit.setText(self.config_model.get("cuit"))
        self.inp_dir.setText(self.config_model.get("direccion"))
        self.inp_tel.setText(self.config_model.get("telefono"))
        self.inp_email.setText(self.config_model.get("email"))
        logo = self.config_model.get("logo_path")
        if logo and Path(logo).exists():
            self.logo_path = logo
            self._actualizar_preview(logo)

    def _seleccionar_logo(self) -> None:
        """Abre selector de archivo para el logo."""
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Logo",
            str(Path.home()),
            "Imágenes (*.png *.jpg *.jpeg *.bmp)"
        )
        if ruta:
            self.logo_path = ruta
            self._actualizar_preview(ruta)

    def _actualizar_preview(self, ruta: str) -> None:
        """Muestra preview del logo."""
        pixmap = QPixmap(ruta)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                80, 50,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_logo_preview.setPixmap(scaled)
            self.lbl_logo.setText(Path(ruta).name)

    def _guardar(self) -> None:
        """Valida y guarda la configuración."""
        razon = self.inp_razon.text().strip()
        if not razon:
            QMessageBox.warning(self, "Campo requerido", "La Razón Social es obligatoria.")
            self.inp_razon.setFocus()
            return

        datos = {
            "razon_social": razon,
            "cuit":         self.inp_cuit.text().strip(),
            "direccion":    self.inp_dir.text().strip(),
            "telefono":     self.inp_tel.text().strip(),
            "email":        self.inp_email.text().strip(),
            "logo_path":    self.logo_path,
        }
        if self.config_model.set_datos_imprenta(datos):
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo guardar la configuración.")
