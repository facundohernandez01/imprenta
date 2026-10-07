"""
views/dialogs/dialogo_red.py
─────────────────────────────
Wizard de configuración de red LAN.
Máximo simple: 3 clics para configurar servidor o cliente.
"""
import socket
import threading
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QStackedWidget, QWidget,
    QLabel, QPushButton, QLineEdit, QFrame, QProgressBar,
    QTextEdit, QMessageBox, QSpinBox, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont

from network.net_config import (
    cargar, guardar, MODO_LOCAL, MODO_SERVER, MODO_CLIENT,
    generar_api_key, DEFAULT_PORT, get_port
)
from utils.styles import AppStyles


class _TestWorker(QObject):
    done = Signal(dict)

    def __init__(self, ip, port, key):
        super().__init__()
        self.ip = ip; self.port = port; self.key = key

    def run(self):
        from network.http_client import test_conexion
        self.done.emit(test_conexion(self.ip, self.port, self.key))


class DialogoConfigRed(QDialog):
    """Wizard LAN en 3 pasos, máximo simple para usuario no técnico."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = cargar()
        self._hilo = None
        self.setWindowTitle("Configuración de Red — Gestión Imprenta Pro")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Barra de título coloreada
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet(f"background: {AppStyles.BG_DARK}; border-bottom: 2px solid {AppStyles.ACCENT};")
        hlay = QHBoxLayout(header)
        lbl_h = QLabel("🌐  Configuración de Red LAN")
        lbl_h.setStyleSheet(f"color: {AppStyles.TEXT_MAIN}; font-size: 14pt; font-weight: bold;")
        hlay.addWidget(lbl_h)
        root.addWidget(header)

        # Stack de páginas
        body = QWidget()
        body.setStyleSheet(f"background: {AppStyles.BG_MEDIUM};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(30, 20, 30, 20)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_modo())        # 0
        self.stack.addWidget(self._page_servidor())    # 1
        self.stack.addWidget(self._page_cliente())     # 2
        self.stack.addWidget(self._page_verificando()) # 3
        self.stack.addWidget(self._page_resultado())   # 4
        body_lay.addWidget(self.stack)

        # Navegación
        nav = QHBoxLayout()
        self.btn_back = QPushButton("← Volver")
        self.btn_back.setVisible(False)
        self.btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_back.clicked.connect(lambda: self._update_nav(0))
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_next = QPushButton("Continuar →")
        self.btn_next.setObjectName("btn_primary")
        self.btn_next.clicked.connect(self._on_next)
        nav.addWidget(self.btn_back)
        nav.addStretch()
        nav.addWidget(self.btn_cancel)
        nav.addWidget(self.btn_next)
        body_lay.addLayout(nav)
        root.addWidget(body)

        # Pre-cargar según config actual
        self._pre_cargar()

    def _card(self, emoji: str, titulo: str, desc: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: {AppStyles.BG_LIGHT}; border: 1px solid {AppStyles.BORDER};"
            f" border-radius: 8px; }}"
            f"QFrame:hover {{ border-color: {AppStyles.ACCENT}; }}"
        )
        f.setFixedHeight(90)
        f.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(f); lay.setContentsMargins(16, 12, 16, 12)
        lbl_ico = QLabel(emoji)
        lbl_ico.setStyleSheet("font-size: 28pt; background: transparent; border: none;")
        lbl_ico.setFixedWidth(50)
        txt = QVBoxLayout()
        lbl_t = QLabel(titulo)
        lbl_t.setStyleSheet(f"background:transparent; border:none; font-size:11pt; font-weight:bold; color:{AppStyles.TEXT_MAIN};")
        lbl_d = QLabel(desc)
        lbl_d.setStyleSheet(f"background:transparent; border:none; font-size:9pt; color:{AppStyles.TEXT_DIM};")
        lbl_d.setWordWrap(True)
        txt.addWidget(lbl_t); txt.addWidget(lbl_d)
        lay.addWidget(lbl_ico); lay.addLayout(txt)
        return f

    def _page_modo(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)

        lbl = QLabel("¿Cómo vas a usar esta PC?")
        lbl.setStyleSheet("font-size: 12pt; font-weight: bold;")
        lay.addWidget(lbl)

        self._card_local   = self._card("💻", "Solo en esta PC",
            "La base de datos vive en esta PC únicamente. Sin red.")
        self._card_servidor = self._card("🖥️", "Esta PC es el SERVIDOR",
            "Comparte la base de datos con otras PCs. Debe estar siempre encendida.")
        self._card_cliente  = self._card("🔗", "Esta PC es CLIENTE",
            "Se conecta a otro servidor. Necesitás la IP del servidor.")

        self._modo_sel = MODO_LOCAL
        for card, modo in [(self._card_local, MODO_LOCAL),
                            (self._card_servidor, MODO_SERVER),
                            (self._card_cliente, MODO_CLIENT)]:
            card.mousePressEvent = lambda e, m=modo: self._select_modo(m)
            lay.addWidget(card)

        lay.addStretch()
        return w

    def _select_modo(self, modo: str):
        self._modo_sel = modo
        accent = f"border: 2px solid {AppStyles.ACCENT};"
        normal = f"border: 1px solid {AppStyles.BORDER};"
        for card, m in [(self._card_local, MODO_LOCAL),
                         (self._card_servidor, MODO_SERVER),
                         (self._card_cliente, MODO_CLIENT)]:
            style_base = (
                f"QFrame {{ background: {AppStyles.BG_LIGHT}; border-radius: 8px; "
                f"{accent if m == modo else normal} }}"
                f"QFrame:hover {{ border-color: {AppStyles.ACCENT}; }}"
            )
            card.setStyleSheet(style_base)

    def _page_servidor(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(14)

        lbl = QLabel("🖥️  Configurar esta PC como Servidor")
        lbl.setStyleSheet("font-size: 12pt; font-weight: bold;")
        lay.addWidget(lbl)

        # IP local
        ip_actual = self._get_ip_local()
        hostname  = socket.gethostname()
        info_box = QFrame()
        info_box.setStyleSheet(
            f"background: #1a3a1a; border: 1px solid {AppStyles.SUCCESS}; border-radius: 6px;")
        ibl = QVBoxLayout(info_box); ibl.setContentsMargins(14, 10, 14, 10)
        ibl.addWidget(QLabel(f"📍  Esta PC: <b>{hostname}</b>"))
        lbl_ip = QLabel(f"🌐  IP en la red: <b>{ip_actual}</b>")
        lbl_ip.setStyleSheet(f"color: {AppStyles.SUCCESS}; font-size: 11pt;")
        ibl.addWidget(lbl_ip)
        ibl.addWidget(QLabel(f"Los clientes deben usar esta IP: <b>{ip_actual}</b>"))
        lay.addWidget(info_box)

        # Puerto
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Puerto:"))
        self.spin_port_srv = QSpinBox()
        self.spin_port_srv.setRange(1024, 65535)
        self.spin_port_srv.setValue(self.cfg.get("server_port", DEFAULT_PORT))
        self.spin_port_srv.setFixedWidth(100)
        port_row.addWidget(self.spin_port_srv)
        lbl_port_hint = QLabel("(no cambiar salvo conflicto)")
        lbl_port_hint.setStyleSheet(f"color: {AppStyles.TEXT_DIM}; font-size: 8pt;")
        port_row.addWidget(lbl_port_hint)
        port_row.addStretch()
        lay.addLayout(port_row)

        # API Key
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Clave de acceso:"))
        self.inp_key_srv = QLineEdit()
        self.inp_key_srv.setPlaceholderText("Se genera automáticamente")
        existing_key = self.cfg.get("api_key", "")
        if not existing_key:
            existing_key = generar_api_key()
        self.inp_key_srv.setText(existing_key)
        self.inp_key_srv.setMinimumWidth(220)
        key_row.addWidget(self.inp_key_srv)
        btn_regen = QPushButton("🔄 Nueva")
        btn_regen.setFixedWidth(70)
        btn_regen.clicked.connect(lambda: self.inp_key_srv.setText(generar_api_key()))
        key_row.addWidget(btn_regen)
        key_row.addStretch()
        lay.addLayout(key_row)

        lbl_hint = QLabel(
            "ℹ️  Copiá la 'Clave de acceso' para configurar los clientes.\n"
            "El servidor arrancará automáticamente cada vez que abras la app."
        )
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet(f"color: {AppStyles.TEXT_DIM}; font-size: 8pt;")
        lay.addWidget(lbl_hint)

        # Firewall hint
        fw_box = QFrame()
        fw_box.setStyleSheet(
            f"background: #2a2a1a; border: 1px solid {AppStyles.WARNING}; border-radius: 6px;")
        fbl = QVBoxLayout(fw_box); fbl.setContentsMargins(12, 8, 12, 8)
        fbl.addWidget(QLabel(
            f"⚠️  Primera vez: Windows te pedirá permiso para la red.\n"
            f"   Hacé clic en 'Permitir acceso' cuando aparezca el aviso."
        ))
        lay.addWidget(fw_box)
        lay.addStretch()
        return w

    def _page_cliente(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(14)

        lbl = QLabel("🔗  Conectar al Servidor")
        lbl.setStyleSheet("font-size: 12pt; font-weight: bold;")
        lay.addWidget(lbl)

        form_box = QFrame()
        form_box.setStyleSheet(
            f"background: {AppStyles.BG_LIGHT}; border-radius: 6px;")
        flay = QVBoxLayout(form_box); flay.setContentsMargins(16, 14, 16, 14); flay.setSpacing(12)

        flay.addWidget(QLabel("IP del servidor:"))
        self.inp_ip = QLineEdit()
        self.inp_ip.setPlaceholderText("Ej: 192.168.1.100")
        self.inp_ip.setMinimumHeight(36)
        flay.addWidget(self.inp_ip)

        flay.addWidget(QLabel("Puerto:"))
        self.spin_port_cli = QSpinBox()
        self.spin_port_cli.setRange(1024, 65535)
        self.spin_port_cli.setValue(self.cfg.get("server_port", DEFAULT_PORT))
        self.spin_port_cli.setFixedWidth(100)
        flay.addWidget(self.spin_port_cli)

        flay.addWidget(QLabel("Clave de acceso:"))
        self.inp_key_cli = QLineEdit()
        self.inp_key_cli.setPlaceholderText("La misma que configuraste en el servidor")
        self.inp_key_cli.setMinimumHeight(36)
        flay.addWidget(self.inp_key_cli)

        lay.addWidget(form_box)

        # Auto-detectar
        btn_detect = QPushButton("🔍  Detectar servidor automáticamente en la red")
        btn_detect.clicked.connect(self._detectar)
        lay.addWidget(btn_detect)
        self.lbl_detect = QLabel("")
        self.lbl_detect.setStyleSheet(f"color: {AppStyles.TEXT_DIM}; font-size: 8pt;")
        lay.addWidget(self.lbl_detect)
        lay.addStretch()
        return w

    def _page_verificando(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_verify = QLabel("Verificando conexión...")
        self.lbl_verify.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_verify.setStyleSheet("font-size: 11pt;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(320)
        lay.addWidget(self.lbl_verify)
        lay.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    def _page_resultado(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)
        self.lbl_res_titulo = QLabel("")
        self.lbl_res_titulo.setStyleSheet("font-size: 13pt; font-weight: bold;")
        self.txt_res = QTextEdit()
        self.txt_res.setReadOnly(True)
        self.txt_res.setStyleSheet(
            f"background: {AppStyles.BG_LIGHT}; font-family: 'Consolas', monospace; font-size: 9pt;")
        lay.addWidget(self.lbl_res_titulo)
        lay.addWidget(self.txt_res)
        return w

    # ── Navegación ────────────────────────────────────────────────────────

    def _pre_cargar(self):
        modo = self.cfg.get("modo", MODO_LOCAL)
        self._select_modo(modo)
        if self.cfg.get("server_ip"):
            self.inp_ip.setText(self.cfg["server_ip"])
        if self.cfg.get("api_key"):
            self.inp_key_cli.setText(self.cfg["api_key"])
        self._update_nav(0)

    def _update_nav(self, page: int):
        self.btn_back.setVisible(page > 0 and page < 3)
        labels = {0: "Continuar →", 1: "🚀  Activar Servidor", 2: "🔌  Conectar", 4: "✅  Cerrar"}
        self.btn_next.setText(labels.get(page, "Continuar →"))
        self.btn_next.setEnabled(page != 3)

    def _on_next(self):
        page = self.stack.currentIndex()
        if page == 0:
            if self._modo_sel == MODO_LOCAL:
                self._guardar_local()
                return
            elif self._modo_sel == MODO_SERVER:
                self.stack.setCurrentIndex(1)
            else:
                self.stack.setCurrentIndex(2)
            self._update_nav(self.stack.currentIndex())
        elif page == 1:
            self._activar_servidor()
        elif page == 2:
            self._conectar_cliente()
        elif page == 4:
            self.accept()

    # ── Acciones ──────────────────────────────────────────────────────────

    def _guardar_local(self):
        cfg = cargar()
        cfg["modo"] = MODO_LOCAL
        guardar(cfg)
        from network.data_provider import reset_provider
        reset_provider()
        QMessageBox.information(self, "Guardado",
            "Modo local activado.\nReiniciá la aplicación para aplicar los cambios.")
        self.accept()

    def _activar_servidor(self):
        port = self.spin_port_srv.value()
        key  = self.inp_key_srv.text().strip()

        cfg = cargar()
        cfg["modo"]        = MODO_SERVER
        cfg["server_port"] = port
        cfg["api_key"]     = key
        guardar(cfg)

        # Intentar arrancar el servidor ahora mismo
        try:
            from server.flask_server import start_server, is_running
            if not is_running():
                start_server(port=port, api_key=key)
        except ModuleNotFoundError:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self,
                "Flask no instalado",
                "Falta instalar Flask para el modo servidor.\n\n"
                "Ejecutá en la terminal:\n"
                "    pip install flask requests\n\n"
                "Luego reiniciá la aplicación."
            )
            return

        from network.data_provider import reset_provider
        reset_provider()

        ip = self._get_ip_local()
        self.lbl_res_titulo.setText("✅  Servidor activado")
        self.lbl_res_titulo.setStyleSheet(
            f"font-size: 13pt; font-weight: bold; color: {AppStyles.SUCCESS};")
        self.txt_res.setPlainText(
            f"¡Listo! Esta PC ahora es el servidor.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Para configurar las demás PCs (clientes):\n\n"
            f"  IP del servidor:    {ip}\n"
            f"  Puerto:             {port}\n"
            f"  Clave de acceso:    {key}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"En cada PC cliente:\n"
            f"  1. Abrí Gestión Imprenta Pro\n"
            f"  2. Menú Configuración → Red LAN\n"
            f"  3. Elegí 'Esta PC es CLIENTE'\n"
            f"  4. Ingresá los datos de arriba\n\n"
            f"Nota: La primera vez Windows puede pedir\n"
            f"permiso de red — hacé clic en 'Permitir'."
        )
        self.stack.setCurrentIndex(4)
        self._update_nav(4)

    def _conectar_cliente(self):
        ip   = self.inp_ip.text().strip()
        port = self.spin_port_cli.value()
        key  = self.inp_key_cli.text().strip()

        if not ip:
            QMessageBox.warning(self, "Requerido", "Ingresá la IP del servidor.")
            return

        self.stack.setCurrentIndex(3)
        self._update_nav(3)
        self.lbl_verify.setText(f"Conectando a {ip}:{port}...")
        QApplication.processEvents()

        self._hilo = QThread()
        self._worker = _TestWorker(ip, port, key)
        self._worker.moveToThread(self._hilo)
        self._worker.done.connect(lambda r: self._on_test_done(r, ip, port, key))
        self._hilo.started.connect(self._worker.run)
        self._hilo.start()

    def _on_test_done(self, resultado: dict, ip, port, key):
        if self._hilo:
            self._hilo.quit()

        if resultado["ok"]:
            cfg = cargar()
            cfg["modo"]        = MODO_CLIENT
            cfg["server_ip"]   = ip
            cfg["server_port"] = port
            cfg["api_key"]     = key
            guardar(cfg)

            from network.data_provider import reset_provider
            reset_provider()

            self.lbl_res_titulo.setText("✅  Conectado al servidor")
            self.lbl_res_titulo.setStyleSheet(
                f"font-size: 13pt; font-weight: bold; color: {AppStyles.SUCCESS};")
            self.txt_res.setPlainText(
                f"¡Conexión exitosa!\n\n"
                f"Servidor: {ip}:{port}\n"
                f"{resultado['mensaje']}\n\n"
                f"Esta PC usará la base de datos del servidor.\n\n"
                f"⚠️  Reiniciá la aplicación para aplicar\n"
                f"   completamente el modo cliente."
            )
        else:
            self.lbl_res_titulo.setText("❌  No se pudo conectar")
            self.lbl_res_titulo.setStyleSheet(
                f"font-size: 13pt; font-weight: bold; color: {AppStyles.DANGER};")
            self.txt_res.setPlainText(resultado["mensaje"])

        self.stack.setCurrentIndex(4)
        self._update_nav(4)

    def _detectar(self):
        """Escaneo rápido de la subred local buscando el puerto del servidor."""
        self.lbl_detect.setText("🔍  Escaneando red... (puede tardar unos segundos)")
        QApplication.processEvents()

        ip_local = self._get_ip_local()
        port     = self.spin_port_cli.value()
        prefijo  = ".".join(ip_local.split(".")[:3])

        encontrados = []
        lock = threading.Lock()

        def _probe(ip_target):
            import socket as _s
            try:
                with _s.create_connection((ip_target, port), timeout=0.3):
                    with lock:
                        encontrados.append(ip_target)
            except OSError:
                pass

        hilos = []
        for i in range(1, 255):
            ip_t = f"{prefijo}.{i}"
            if ip_t == ip_local:
                continue
            t = threading.Thread(target=_probe, args=(ip_t,), daemon=True)
            hilos.append(t); t.start()
        for t in hilos:
            t.join(timeout=0.5)

        if encontrados:
            self.inp_ip.setText(encontrados[0])
            self.lbl_detect.setText(
                f"✅  Encontrado: {', '.join(encontrados)}"
            )
            self.lbl_detect.setStyleSheet(f"color: {AppStyles.SUCCESS};")
        else:
            self.lbl_detect.setText(
                "No se encontró ningún servidor. Ingresá la IP manualmente."
            )
            self.lbl_detect.setStyleSheet(f"color: {AppStyles.TEXT_DIM};")

    @staticmethod
    def _get_ip_local() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return socket.gethostbyname(socket.gethostname())
