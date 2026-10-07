"""
Diálogo de configuración AFIP: gestión de certificados + datos fiscales + email.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QWidget, QLabel, QLineEdit, QPushButton, QGroupBox,
    QFileDialog, QMessageBox, QDialogButtonBox, QSpinBox, QTextEdit
)
from PySide6.QtCore import Qt

from models.config_model import ConfigModel
from controllers.afip_controller import AFIPController
from utils.styles import AppStyles
from network.data_provider import get_provider


class DialogoConfigAFIP(QDialog):
    """Configuración AFIP, datos fiscales y email."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.config = get_provider().config
        self.afip   = AFIPController()
        self.setWindowTitle("Configuración — AFIP, Fiscales y Email")
        self.setMinimumSize(600, 560)
        self.setModal(True)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._tab_fiscal(),  "🏢  Datos Fiscales")
        self.tabs.addTab(self._tab_afip(),    "🔐  Certificados AFIP")
        self.tabs.addTab(self._tab_email(),   "📧  Email")

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Save).setText("💾  Guardar Todo")
        btns.accepted.connect(self._guardar)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ── Tab Fiscal ─────────────────────────────────────────────────────────

    def _tab_fiscal(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        self.inp_cuit_emisor   = QLineEdit()
        self.inp_cuit_emisor.setPlaceholderText("20-12345678-9")
        self.inp_iibb          = QLineEdit()
        self.inp_iibb.setPlaceholderText("N° Ingresos Brutos")
        self.inp_domfiscal     = QLineEdit()
        self.inp_domfiscal.setPlaceholderText("Av. San Martín 1234, Villa Constitución")
        self.spin_pv           = QSpinBox()
        self.spin_pv.setRange(1, 9999)
        self.spin_pv.setValue(1)
        self.inp_inicio_act    = QLineEdit()
        self.inp_inicio_act.setPlaceholderText("Fecha inicio actividades: DD/MM/YYYY")

        form.addRow("CUIT Emisor *:", self.inp_cuit_emisor)
        form.addRow("Ingresos Brutos:", self.inp_iibb)
        form.addRow("Domicilio Fiscal *:", self.inp_domfiscal)
        form.addRow("Punto de Venta:", self.spin_pv)
        form.addRow("Inicio de Actividades:", self.inp_inicio_act)
        return w

    # ── Tab AFIP ───────────────────────────────────────────────────────────

    def _tab_afip(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Estado actual
        grp_estado = QGroupBox("Estado de Certificados")
        est_lay = QVBoxLayout(grp_estado)
        self.lbl_cert_info = QLabel("Cargando...")
        self.lbl_cert_info.setWordWrap(True)
        self.lbl_cert_info.setStyleSheet(f"color: {AppStyles.TEXT_DIM}; font-size: 9pt;")
        btn_refrescar_cert = QPushButton("🔄  Verificar certificados")
        btn_refrescar_cert.clicked.connect(self._actualizar_info_cert)
        est_lay.addWidget(self.lbl_cert_info)
        est_lay.addWidget(btn_refrescar_cert, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(grp_estado)

        # Generar CSR
        grp_csr = QGroupBox("Paso 1 — Generar clave y CSR")
        csr_form = QFormLayout(grp_csr)
        self.inp_org_name = QLineEdit()
        self.inp_org_name.setPlaceholderText("Razón social para el certificado")
        self.lbl_csr_path = QLabel("Sin generar")
        self.lbl_csr_path.setStyleSheet(f"color: {AppStyles.TEXT_DIM};")
        btn_gen_csr = QPushButton("⚙️  Generar clave + CSR")
        btn_gen_csr.clicked.connect(self._generar_csr)
        csr_form.addRow("Organización:", self.inp_org_name)
        csr_form.addRow("CSR:", self.lbl_csr_path)
        csr_form.addRow("", btn_gen_csr)
        lbl_hint = QLabel(
            "Enviá el archivo .csr a AFIP (https://afip.gob.ar) → "
            "Administración de Certificados Digitales."
        )
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("color: #a0a0b0; font-size: 8pt;")
        csr_form.addRow("", lbl_hint)
        layout.addWidget(grp_csr)

        # Importar CRT
        grp_imp = QGroupBox("Paso 2 — Importar certificado (.crt)")
        imp_lay = QHBoxLayout(grp_imp)
        self.inp_crt_path = QLineEdit()
        self.inp_crt_path.setPlaceholderText("Ruta del .crt descargado de AFIP...")
        self.inp_crt_path.setReadOnly(True)
        btn_buscar_crt = QPushButton("📁")
        btn_buscar_crt.setFixedWidth(32)
        btn_buscar_crt.clicked.connect(self._buscar_crt)
        btn_importar = QPushButton("✅  Importar")
        btn_importar.clicked.connect(self._importar_crt)
        imp_lay.addWidget(self.inp_crt_path)
        imp_lay.addWidget(btn_buscar_crt)
        imp_lay.addWidget(btn_importar)
        layout.addWidget(grp_imp)

        # Test de conexión
        btn_test = QPushButton("🔌  Probar conexión con ARCA")
        btn_test.setObjectName("btn_success")
        btn_test.clicked.connect(self._test_conexion)
        layout.addWidget(btn_test)
        layout.addStretch()
        return w

    # ── Tab Email ──────────────────────────────────────────────────────────

    def _tab_email(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        self.inp_gmail = QLineEdit()
        self.inp_gmail.setPlaceholderText("tucuenta@gmail.com")
        self.inp_app_pass = QLineEdit()
        self.inp_app_pass.setPlaceholderText("App Password de 16 caracteres")
        self.inp_app_pass.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Cuenta Gmail:", self.inp_gmail)
        form.addRow("App Password *:", self.inp_app_pass)

        lbl_ayuda = QLabel(
            "ℹ️  Para obtener una App Password de Gmail:\n"
            "1. Activá verificación en 2 pasos en tu cuenta Google.\n"
            "2. Ir a Cuenta Google → Seguridad → Contraseñas de aplicaciones.\n"
            "3. Generá una para 'Otra aplicación' y pegala aquí."
        )
        lbl_ayuda.setWordWrap(True)
        lbl_ayuda.setStyleSheet("color: #a0a0b0; font-size: 8pt;")
        form.addRow("", lbl_ayuda)

        btn_test_email = QPushButton("📧  Probar envío de email")
        btn_test_email.clicked.connect(self._test_email)
        form.addRow("", btn_test_email)
        return w

    # ── Carga / Guardado ──────────────────────────────────────────────────

    def _cargar(self) -> None:
        self.inp_cuit_emisor.setText(self.config.get("cuit", ""))
        self.inp_iibb.setText(self.config.get("ingresos_brutos", ""))
        self.inp_domfiscal.setText(
            self.config.get("domicilio_fiscal") or self.config.get("direccion", "")
        )
        pv = int(self.config.get("punto_venta", "1") or 1)
        self.spin_pv.setValue(pv)
        self.inp_inicio_act.setText(self.config.get("inicio_actividades", ""))
        self.inp_gmail.setText(self.config.get("gmail_cuenta", ""))
        self.inp_app_pass.setText(self.config.get("gmail_app_pass", ""))
        razon = self.config.get("razon_social", "")
        self.inp_org_name.setText(razon)
        self._actualizar_info_cert()

    def _guardar(self) -> None:
        datos = {
            "cuit":               self.inp_cuit_emisor.text().strip(),
            "ingresos_brutos":    self.inp_iibb.text().strip(),
            "domicilio_fiscal":   self.inp_domfiscal.text().strip(),
            "punto_venta":        str(self.spin_pv.value()),
            "inicio_actividades": self.inp_inicio_act.text().strip(),
            "gmail_cuenta":       self.inp_gmail.text().strip(),
            "gmail_app_pass":     self.inp_app_pass.text().strip(),
        }
        if self.config.set_datos_imprenta(datos):
            QMessageBox.information(self, "Guardado", "Configuración guardada.")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo guardar.")

    # ── AFIP acciones ─────────────────────────────────────────────────────

    def _actualizar_info_cert(self) -> None:
        cuit = self.inp_cuit_emisor.text().strip() or self.config.get("cuit", "")
        if not cuit:
            self.lbl_cert_info.setText("⚠️  Configurá el CUIT primero.")
            return
        info = self.afip.info_certificado()
        if info.get("error"):
            self.lbl_cert_info.setText(f"Error: {info['error']}")
            return
        lineas = []
        lineas.append(f"📁 Directorio: {info.get('storage_dir','')}")
        lineas.append(f"🔑 Clave privada: {'✅' if info.get('key_exists') else '❌ No encontrada'}")
        lineas.append(f"📜 Certificado:   {'✅' if info.get('cert_exists') else '❌ No encontrado'}")
        if info.get("cert_valid_until"):
            valido = "✅ Vigente" if info.get("cert_is_valid") else "❌ VENCIDO"
            lineas.append(f"📅 Vencimiento: {info['cert_valid_until']} — {valido}")
        self.lbl_cert_info.setText("\n".join(lineas))

    def _generar_csr(self) -> None:
        cuit = self.inp_cuit_emisor.text().strip()
        if not cuit:
            QMessageBox.warning(self, "Requerido", "Ingresá el CUIT primero.")
            return
        org = self.inp_org_name.text().strip() or self.config.get("razon_social", "")
        resultado = self.afip.generar_csr(cuit, org)
        if resultado["success"]:
            csr_path = resultado["csr_path"]
            self.lbl_csr_path.setText(csr_path)
            self.lbl_csr_path.setStyleSheet(f"color: {AppStyles.SUCCESS};")
            QMessageBox.information(self, "CSR Generado",
                f"Clave privada y CSR generados en:\n{csr_path}\n\n"
                "Cargá el archivo .csr en AFIP para obtener el certificado.")
            self._actualizar_info_cert()
        else:
            QMessageBox.critical(self, "Error", resultado["message"])

    def _buscar_crt(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar certificado AFIP", str(Path.home()),
            "Certificados (*.crt *.pem *.cer)"
        )
        if ruta:
            self.inp_crt_path.setText(ruta)

    def _importar_crt(self) -> None:
        ruta = self.inp_crt_path.text().strip()
        cuit = self.inp_cuit_emisor.text().strip()
        if not ruta:
            QMessageBox.warning(self, "Requerido", "Seleccioná un archivo .crt.")
            return
        if not cuit:
            QMessageBox.warning(self, "Requerido", "Ingresá el CUIT primero.")
            return
        with open(ruta, "rb") as f:
            crt_bytes = f.read()
        resultado = self.afip.importar_certificado(cuit, crt_bytes)
        if resultado["success"]:
            QMessageBox.information(self, "✅  Importado",
                f"Certificado importado correctamente.\n{resultado['message']}")
            self._actualizar_info_cert()
        else:
            QMessageBox.critical(self, "Error", resultado["message"])

    def _test_conexion(self) -> None:
        # Guardar CUIT primero
        self.config.set("cuit", self.inp_cuit_emisor.text().strip())
        self.config.set("punto_venta", str(self.spin_pv.value()))
        resultado = self.afip.autenticar()
        if resultado["success"]:
            msg = "✅  Conexión exitosa con ARCA.\n"
            if resultado.get("reused"):
                msg += "Se reutilizó token vigente."
            else:
                msg += f"Token obtenido. Expira: {self.afip._expiration}"
            QMessageBox.information(self, "Conexión OK", msg)
        else:
            QMessageBox.critical(self, "Error", resultado["message"])

    def _test_email(self) -> None:
        cuenta = self.inp_gmail.text().strip()
        app_pass = self.inp_app_pass.text().strip()
        if not cuenta or not app_pass:
            QMessageBox.warning(self, "Requerido",
                "Completá la cuenta Gmail y App Password.")
            return
        # Guardar temporalmente para el test
        self.config.set("gmail_cuenta", cuenta)
        self.config.set("gmail_app_pass", app_pass)
        from utils.email_helper import enviar_email
        res = enviar_email(
            destinatario=cuenta,
            asunto="Test — Gestión Imprenta Pro",
            cuerpo_html="<p>Email de prueba enviado correctamente desde Gestión Imprenta Pro.</p>",
        )
        if res["success"]:
            QMessageBox.information(self, "✅  Email enviado",
                f"Email de prueba enviado a {cuenta}")
        else:
            QMessageBox.critical(self, "Error", res["message"])
