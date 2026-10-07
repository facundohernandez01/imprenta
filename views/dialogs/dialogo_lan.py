"""
views/dialogs/dialogo_lan.py
────────────────────────────
Wizard de configuración LAN. Accessible desde Configuración → Red LAN.
Pasos:
  1. Elegir modo: Local / Servidor / Cliente
  2a. (Servidor) Crear share automáticamente
  2b. (Cliente) Ingresar IP/hostname del servidor
  3. Verificar y guardar
"""
import socket
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QWidget, QLabel, QPushButton, QLineEdit, QRadioButton,
    QGroupBox, QButtonGroup, QTextEdit, QProgressBar,
    QMessageBox, QApplication, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont

from lan.lan_config import (
    cargar, guardar, MODO_LOCAL, MODO_SERVER, MODO_CLIENT,
    get_db_path
)
from utils.styles import AppStyles


class _WorkerSetup(QObject):
    """Corre operaciones de red en hilo separado."""
    progreso = Signal(str)
    terminado = Signal(dict)

    def __init__(self, modo: str, share_name: str, unc_path: str):
        super().__init__()
        self.modo       = modo
        self.share_name = share_name
        self.unc_path   = unc_path

    def run(self) -> None:
        from lan.lan_setup import (
            servidor_verificar_smb_activo, servidor_crear_share,
            servidor_get_ip, servidor_get_hostname,
            cliente_verificar_acceso, _CONFIG_DIR
        )
        resultado = {}

        if self.modo == MODO_SERVER:
            self.progreso.emit("Verificando servicio SMB...")
            smb = servidor_verificar_smb_activo()
            resultado["smb"] = smb

            self.progreso.emit("Creando carpeta compartida...")
            db_dir = _CONFIG_DIR / "shared_db"
            share  = servidor_crear_share(self.share_name, db_dir)
            resultado["share"] = share

            resultado["ip"]       = servidor_get_ip()
            resultado["hostname"] = servidor_get_hostname()
            resultado["unc"]      = share.get("unc", f"\\\\{servidor_get_hostname()}\\{self.share_name}")
            resultado["success"]  = share["success"]
            resultado["message"]  = share["message"]

        elif self.modo == MODO_CLIENT:
            self.progreso.emit(f"Verificando acceso a {self.unc_path}...")
            acceso = cliente_verificar_acceso(self.unc_path)
            resultado.update(acceso)
            resultado["success"] = acceso["ok"]
            resultado["message"] = acceso["mensaje"]

        self.terminado.emit(resultado)


class DialogoConfigLAN(QDialog):
    """Wizard de configuración LAN en 3 pasos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg     = cargar()
        self._thread = None
        self._worker = None
        self.setWindowTitle("Configuración de Red LAN")
        self.setMinimumSize(580, 480)
        self.setModal(True)
        self._build_ui()
        self._cargar_estado_actual()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Título
        titulo = QLabel("🌐  Configuración de Red LAN")
        titulo.setObjectName("lbl_header")
        layout.addWidget(titulo)

        sub = QLabel(
            "Permite que múltiples PCs en la misma red compartan la misma base de datos."
        )
        sub.setStyleSheet(f"color: {AppStyles.TEXT_DIM}; font-size: 9pt;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Stack de pasos
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        self.stack.addWidget(self._page_modo())       # 0
        self.stack.addWidget(self._page_servidor())   # 1
        self.stack.addWidget(self._page_cliente())    # 2
        self.stack.addWidget(self._page_procesando()) # 3
        self.stack.addWidget(self._page_resultado())  # 4

        # Navegación
        nav = QHBoxLayout()
        self.btn_atras   = QPushButton("← Atrás")
        self.btn_atras.setVisible(False)
        self.btn_atras.clicked.connect(self._atras)
        self.btn_siguiente = QPushButton("Siguiente →")
        self.btn_siguiente.setObjectName("btn_primary")
        self.btn_siguiente.clicked.connect(self._siguiente)
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.clicked.connect(self.reject)
        nav.addWidget(self.btn_atras)
        nav.addStretch()
        nav.addWidget(self.btn_cerrar)
        nav.addWidget(self.btn_siguiente)
        layout.addLayout(nav)

    def _page_modo(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(14)

        lbl = QLabel("Paso 1 — ¿Cómo usará esta PC?")
        lbl.setStyleSheet("font-weight: bold; font-size: 11pt;")
        lay.addWidget(lbl)

        self.btn_grp = QButtonGroup(w)
        opciones = [
            ("💻  Solo en esta PC (modo local)",
             "Sin red. La base de datos vive en esta PC solamente.",
             MODO_LOCAL),
            ("🖥️  Esta PC es el SERVIDOR",
             "Esta PC tiene la DB y la comparte con las demás.\n"
             "Debe estar siempre encendida mientras otros la usen.",
             MODO_SERVER),
            ("🖥️→🖥️  Esta PC es CLIENTE",
             "Esta PC se conecta a la DB que está en el servidor.\n"
             "Necesitás la IP o nombre del servidor.",
             MODO_CLIENT),
        ]
        self._radio_modos = {}
        for texto, desc, modo_val in opciones:
            frame = QFrame()
            frame.setStyleSheet(
                f"QFrame {{ background: {AppStyles.BG_LIGHT}; border: 1px solid {AppStyles.BORDER};"
                f"border-radius: 6px; }}"
                f"QFrame:hover {{ border-color: {AppStyles.ACCENT}; }}"
            )
            fl = QVBoxLayout(frame); fl.setContentsMargins(12, 10, 12, 10)
            rb = QRadioButton(texto)
            rb.setStyleSheet("font-size: 10pt; font-weight: bold;")
            lbl_desc = QLabel(desc)
            lbl_desc.setStyleSheet(f"color: {AppStyles.TEXT_DIM}; font-size: 8pt;")
            lbl_desc.setWordWrap(True)
            fl.addWidget(rb); fl.addWidget(lbl_desc)
            self.btn_grp.addButton(rb)
            self._radio_modos[modo_val] = rb
            lay.addWidget(frame)

        self._radio_modos[MODO_LOCAL].setChecked(True)
        lay.addStretch()
        return w

    def _page_servidor(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)
        lbl = QLabel("Paso 2 — Configurar Servidor")
        lbl.setStyleSheet("font-weight: bold; font-size: 11pt;")
        lay.addWidget(lbl)

        info = QLabel(
            "Esta PC compartirá la base de datos en la red.\n"
            "Se creará automáticamente una carpeta compartida llamada 'ImprentaDB'.\n\n"
            "Las demás PCs solo necesitarán la IP o nombre de esta PC."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {AppStyles.TEXT_DIM}; padding: 8px; "
                           f"background: {AppStyles.BG_LIGHT}; border-radius: 4px;")
        lay.addWidget(info)

        from lan.lan_setup import servidor_get_ip, servidor_get_hostname
        ip_actual = servidor_get_ip()
        host_actual = servidor_get_hostname()

        lbl_ip = QLabel(
            f"📍  Esta PC: <b>{host_actual}</b> — IP: <b>{ip_actual}</b>\n"
            f"Los clientes deberán conectarse con esa IP o nombre."
        )
        lbl_ip.setStyleSheet(
            f"color: {AppStyles.SUCCESS}; font-size: 10pt; "
            f"background: #1a3a1a; padding: 8px; border-radius: 4px;"
        )
        lbl_ip.setWordWrap(True)
        lay.addWidget(lbl_ip)

        lbl_share = QLabel("Nombre del recurso compartido:")
        lay.addWidget(lbl_share)
        self.inp_share_name = QLineEdit("ImprentaDB")
        self.inp_share_name.setMaximumWidth(200)
        lay.addWidget(self.inp_share_name)

        aviso = QLabel(
            "⚠️  Requisito: 'Compartir archivos e impresoras' debe estar habilitado\n"
            "en el Firewall de Windows. El sistema intentará habilitarlo automáticamente."
        )
        aviso.setWordWrap(True)
        aviso.setStyleSheet(f"color: {AppStyles.WARNING}; font-size: 8pt;")
        lay.addWidget(aviso)
        lay.addStretch()
        return w

    def _page_cliente(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)
        lbl = QLabel("Paso 2 — Conectar al Servidor")
        lbl.setStyleSheet("font-weight: bold; font-size: 11pt;")
        lay.addWidget(lbl)

        info = QLabel(
            "Ingresá la IP o nombre de la PC servidor.\n"
            "El servidor debe tener Gestión Imprenta Pro configurado en modo Servidor."
        )
        info.setWordWrap(True); info.setStyleSheet(f"color: {AppStyles.TEXT_DIM};")
        lay.addWidget(info)

        lay.addWidget(QLabel("IP o nombre del servidor:"))
        self.inp_server_ip = QLineEdit()
        self.inp_server_ip.setPlaceholderText("Ej: 192.168.1.100  o  PC-MARIO")
        lay.addWidget(self.inp_server_ip)

        lay.addWidget(QLabel("Nombre del recurso compartido:"))
        self.inp_client_share = QLineEdit("ImprentaDB")
        self.inp_client_share.setMaximumWidth(200)
        lay.addWidget(self.inp_client_share)

        # Botón auto-detectar
        btn_detectar = QPushButton("🔍  Detectar servidores en la red")
        btn_detectar.clicked.connect(self._detectar_servidores)
        lay.addWidget(btn_detectar)

        self.lbl_detectados = QLabel("")
        self.lbl_detectados.setStyleSheet(f"color: {AppStyles.TEXT_DIM}; font-size: 8pt;")
        lay.addWidget(self.lbl_detectados)
        lay.addStretch()
        return w

    def _page_procesando(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_procesando = QLabel("Configurando...")
        self.lbl_procesando.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_procesando.setStyleSheet("font-size: 11pt;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminado
        self.progress.setMaximumWidth(300)
        lay.addWidget(self.lbl_procesando)
        lay.addWidget(self.progress)
        return w

    def _page_resultado(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.lbl_resultado_titulo = QLabel("Resultado")
        self.lbl_resultado_titulo.setStyleSheet("font-size: 12pt; font-weight: bold;")
        lay.addWidget(self.lbl_resultado_titulo)
        self.txt_resultado = QTextEdit()
        self.txt_resultado.setReadOnly(True)
        self.txt_resultado.setStyleSheet(
            f"background: {AppStyles.BG_LIGHT}; font-family: monospace; font-size: 9pt;"
        )
        lay.addWidget(self.txt_resultado)
        return w

    # ── Navegación ────────────────────────────────────────────────────────

    def _cargar_estado_actual(self) -> None:
        """Pre-carga el modo actual."""
        modo = self.cfg.get("modo", MODO_LOCAL)
        if modo in self._radio_modos:
            self._radio_modos[modo].setChecked(True)
        if self.cfg.get("server_name"):
            self.inp_server_ip.setText(self.cfg["server_name"])
        if self.cfg.get("share_name"):
            share = self.cfg["share_name"]
            self.inp_share_name.setText(share)
            self.inp_client_share.setText(share)

    def _get_modo_seleccionado(self) -> str:
        for modo, rb in self._radio_modos.items():
            if rb.isChecked():
                return modo
        return MODO_LOCAL

    def _siguiente(self) -> None:
        page = self.stack.currentIndex()

        if page == 0:
            modo = self._get_modo_seleccionado()
            if modo == MODO_LOCAL:
                # Guardar config local y cerrar
                self._guardar_config_local()
                return
            elif modo == MODO_SERVER:
                self.stack.setCurrentIndex(1)
                self.btn_atras.setVisible(True)
                self.btn_siguiente.setText("🚀  Configurar Servidor")
            elif modo == MODO_CLIENT:
                self.stack.setCurrentIndex(2)
                self.btn_atras.setVisible(True)
                self.btn_siguiente.setText("🔌  Conectar")

        elif page == 1:  # Servidor → Procesar
            self._iniciar_configuracion_servidor()

        elif page == 2:  # Cliente → Procesar
            self._iniciar_configuracion_cliente()

        elif page == 4:  # Resultado → Cerrar
            self.accept()

    def _atras(self) -> None:
        self.stack.setCurrentIndex(0)
        self.btn_atras.setVisible(False)
        self.btn_siguiente.setText("Siguiente →")

    # ── Configuración ─────────────────────────────────────────────────────

    def _guardar_config_local(self) -> None:
        cfg = cargar()
        cfg["modo"] = MODO_LOCAL
        guardar(cfg)
        QMessageBox.information(self, "Guardado",
            "Modo local activado. La base de datos permanece en esta PC.")
        self.accept()

    def _iniciar_configuracion_servidor(self) -> None:
        share_name = self.inp_share_name.text().strip() or "ImprentaDB"
        self.stack.setCurrentIndex(3)
        self.btn_siguiente.setEnabled(False)
        self.btn_atras.setEnabled(False)

        self._thread = QThread()
        self._worker = _WorkerSetup(MODO_SERVER, share_name, "")
        self._worker.moveToThread(self._thread)
        self._worker.progreso.connect(self.lbl_procesando.setText)
        self._worker.terminado.connect(self._on_servidor_configurado)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def _on_servidor_configurado(self, resultado: dict) -> None:
        self._thread.quit()
        self.btn_siguiente.setEnabled(True)
        self.btn_atras.setEnabled(True)

        share_name = self.inp_share_name.text().strip() or "ImprentaDB"

        if resultado.get("success"):
            unc = resultado.get("unc", "")
            # Guardar config
            cfg = cargar()
            cfg["modo"]       = MODO_SERVER
            cfg["share_name"] = share_name
            cfg["unc_path"]   = unc
            guardar(cfg)

            # Aplicar patch LAN inmediatamente
            from lan.lan_db import aplicar_patch_lan
            aplicar_patch_lan()

            self.lbl_resultado_titulo.setText("✅  Servidor Configurado")
            self.lbl_resultado_titulo.setStyleSheet(
                f"font-size: 12pt; font-weight: bold; color: {AppStyles.SUCCESS};"
            )
            texto = (
                f"¡Servidor configurado correctamente!\n\n"
                f"📁 Recurso compartido: {share_name}\n"
                f"🌐 UNC para clientes: {unc}\n"
                f"💻 IP de este servidor: {resultado.get('ip', '')}\n"
                f"🔤 Nombre: {resultado.get('hostname', '')}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"En las demás PCs (clientes):\n"
                f"  1. Abrí Gestión Imprenta Pro\n"
                f"  2. Configuración → Red LAN\n"
                f"  3. Elegí 'Cliente'\n"
                f"  4. Ingresá la IP: {resultado.get('ip', '')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"La base de datos ahora se guarda en:\n"
                f"  {get_db_path() or '(calculando...)'}"
            )
        else:
            self.lbl_resultado_titulo.setText("❌  Error al configurar")
            self.lbl_resultado_titulo.setStyleSheet(
                f"font-size: 12pt; font-weight: bold; color: {AppStyles.DANGER};"
            )
            texto = f"No se pudo configurar el servidor:\n\n{resultado.get('message', '')}"

        self.txt_resultado.setPlainText(texto)
        self.stack.setCurrentIndex(4)
        self.btn_siguiente.setText("Cerrar")
        self.btn_atras.setVisible(False)

    def _iniciar_configuracion_cliente(self) -> None:
        server = self.inp_server_ip.text().strip()
        if not server:
            QMessageBox.warning(self, "Requerido",
                "Ingresá la IP o nombre del servidor."); return

        share = self.inp_client_share.text().strip() or "ImprentaDB"
        unc   = f"\\\\{server}\\{share}"

        self.stack.setCurrentIndex(3)
        self.btn_siguiente.setEnabled(False)
        self.btn_atras.setEnabled(False)

        self._thread = QThread()
        self._worker = _WorkerSetup(MODO_CLIENT, share, unc)
        self._worker.moveToThread(self._thread)
        self._worker.progreso.connect(self.lbl_procesando.setText)
        self._worker.terminado.connect(
            lambda r: self._on_cliente_configurado(r, server, share, unc)
        )
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def _on_cliente_configurado(self, resultado: dict,
                                  server: str, share: str, unc: str) -> None:
        self._thread.quit()
        self.btn_siguiente.setEnabled(True)
        self.btn_atras.setEnabled(True)

        if resultado.get("success") or resultado.get("ok"):
            cfg = cargar()
            cfg["modo"]        = MODO_CLIENT
            cfg["server_name"] = server
            cfg["share_name"]  = share
            cfg["unc_path"]    = unc
            guardar(cfg)

            from lan.lan_db import aplicar_patch_lan
            aplicar_patch_lan()

            self.lbl_resultado_titulo.setText("✅  Conectado al Servidor")
            self.lbl_resultado_titulo.setStyleSheet(
                f"font-size: 12pt; font-weight: bold; color: {AppStyles.SUCCESS};"
            )
            texto = (
                f"Conexión exitosa al servidor.\n\n"
                f"🖥️  Servidor: {server}\n"
                f"📁 Share: {share}\n"
                f"🔗 UNC: {unc}\n\n"
                f"La base de datos compartida es:\n"
                f"  {get_db_path() or unc}\n\n"
                f"⚠️  IMPORTANTE: Reiniciá la aplicación para\n"
                f"   que los cambios tomen efecto completo."
            )
        else:
            self.lbl_resultado_titulo.setText("❌  No se pudo conectar")
            self.lbl_resultado_titulo.setStyleSheet(
                f"font-size: 12pt; font-weight: bold; color: {AppStyles.DANGER};"
            )
            texto = resultado.get("message", resultado.get("mensaje", "Error desconocido"))

        self.txt_resultado.setPlainText(texto)
        self.stack.setCurrentIndex(4)
        self.btn_siguiente.setText("Cerrar")
        self.btn_atras.setVisible(False)

    def _detectar_servidores(self) -> None:
        self.lbl_detectados.setText("🔍  Buscando en la red...")
        QApplication.processEvents()
        try:
            from lan.lan_setup import cliente_detectar_servidores_lan
            encontrados = cliente_detectar_servidores_lan()
            if encontrados:
                self.inp_server_ip.setText(encontrados[0]["ip"] or encontrados[0]["hostname"])
                self.lbl_detectados.setText(
                    "Encontrados: " + ", ".join(
                        f"{s['hostname']} ({s['ip']})" for s in encontrados
                    )
                )
                self.lbl_detectados.setStyleSheet(f"color: {AppStyles.SUCCESS};")
            else:
                self.lbl_detectados.setText(
                    "No se encontraron servidores. Ingresá la IP manualmente."
                )
                self.lbl_detectados.setStyleSheet(f"color: {AppStyles.TEXT_DIM};")
        except Exception as e:
            self.lbl_detectados.setText(f"Error: {e}")
