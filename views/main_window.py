"""
MainWindow: ventana principal con QTabWidget, menús y statusbar.
"""
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel,
    QMenuBar, QMenu, QMessageBox, QApplication
)
from PySide6.QtGui import QAction, QKeySequence, QFont, QIcon
from PySide6.QtCore import Qt, QTimer

from db.database import DatabaseManager
from utils.styles import AppStyles
from network.data_provider import get_provider


class MainWindow(QMainWindow):
    """Ventana principal de Gestión Imprenta Pro."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        super().__init__()
        self.db_manager = db_manager
        self.setWindowTitle("Gestión Imprenta Pro v1.0")
        self.setMinimumSize(1200, 720)
        self.resize(1400, 800)

        self._build_ui()
        self._build_menus()
        self._build_statusbar()
        self._setup_shortcuts()

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construye el QTabWidget principal."""
        from views.tab_pedidos import TabPedidos
        from views.tab_taller import TabTaller
        from views.tab_cuenta_corriente import TabCuentaCorriente

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.setCentralWidget(self.tabs)

        self.tab_pedidos = TabPedidos()
        self.tab_taller  = TabTaller()
        self.tab_cc      = TabCuentaCorriente()

        self.tabs.addTab(self.tab_pedidos, "📋  Pedidos")
        self.tabs.addTab(self.tab_taller,  "🔧  Taller")
        self.tabs.addTab(self.tab_cc,      "💰  Cuenta Corriente")

        self.tabs.currentChanged.connect(self._on_tab_cambiado)

    # ─── MENÚS ────────────────────────────────────────────────────────────────

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        # ── Archivo ──
        menu_archivo = menubar.addMenu("&Archivo")

        act_nuevo = QAction("➕  Nuevo Pedido", self)
        act_nuevo.setShortcut(QKeySequence("Ctrl+N"))
        act_nuevo.triggered.connect(self._nuevo_pedido)
        menu_archivo.addAction(act_nuevo)

        menu_archivo.addSeparator()

        act_backup = QAction("💾  Hacer Backup Ahora", self)
        act_backup.triggered.connect(self._hacer_backup)
        menu_archivo.addAction(act_backup)

        menu_archivo.addSeparator()

        act_salir = QAction("🚪  Salir", self)
        act_salir.setShortcut(QKeySequence("Alt+F4"))
        act_salir.triggered.connect(self.close)
        menu_archivo.addAction(act_salir)

        # ── Datos ──
        menu_datos = menubar.addMenu("&Datos")

        act_clientes = QAction("👥  Clientes", self)
        act_clientes.triggered.connect(self._abm_clientes)
        menu_datos.addAction(act_clientes)

        act_productos = QAction("📦  Productos", self)
        act_productos.triggered.connect(self._abm_productos)
        menu_datos.addAction(act_productos)

        act_tipos = QAction("🏷️  Tipos de Trabajo", self)
        act_tipos.triggered.connect(self._abm_tipos)
        menu_datos.addAction(act_tipos)

        act_insumos = QAction("🧰  Insumos", self)
        act_insumos.triggered.connect(self._abm_insumos)
        menu_datos.addAction(act_insumos)

        # ── Reportes ──
        menu_rep = menubar.addMenu("&Reportes")

        act_ventas = QAction("📊  Ventas del Mes", self)
        act_ventas.triggered.connect(self._reporte_ventas)
        menu_rep.addAction(act_ventas)

        act_balance = QAction("💼  Balance General", self)
        act_balance.triggered.connect(self._reporte_balance)
        menu_rep.addAction(act_balance)

        act_productos_rep = QAction("🏆  Productos Más Vendidos", self)
        act_productos_rep.triggered.connect(self._reporte_productos)
        menu_rep.addAction(act_productos_rep)

        # ── Configuración ──
        menu_config = menubar.addMenu("&Configuración")

        act_config = QAction("⚙️  Datos de la Imprenta", self)
        act_config.triggered.connect(self._config_imprenta)
        menu_config.addAction(act_config)

        act_afip = QAction("🔐  AFIP / Facturación Electrónica", self)
        act_afip.triggered.connect(self._config_afip)
        menu_config.addAction(act_afip)

        act_lan = QAction("🌐  Red LAN / Modo servidor o cliente", self)
        act_lan.triggered.connect(self._config_lan)
        menu_config.addAction(act_lan)

        menu_config.addSeparator()

        act_usuarios = QAction("👥  Gestión de Usuarios", self)
        act_usuarios.triggered.connect(self._abm_usuarios)
        menu_config.addAction(act_usuarios)

        act_cambiar_pass = QAction("🔑  Cambiar Contraseña", self)
        act_cambiar_pass.triggered.connect(self._cambiar_password)
        menu_config.addAction(act_cambiar_pass)

        # ── Ayuda ──
        menu_ayuda = menubar.addMenu("&Ayuda")

        act_ayuda = QAction("❓  Ayuda (F1)", self)
        act_ayuda.setShortcut(QKeySequence("F1"))
        act_ayuda.triggered.connect(self._mostrar_ayuda)
        menu_ayuda.addAction(act_ayuda)

        act_acerca = QAction("ℹ️  Acerca de...", self)
        act_acerca.triggered.connect(self._acerca_de)
        menu_ayuda.addAction(act_acerca)

    # ─── STATUSBAR ────────────────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.lbl_status = QLabel("✅  Sistema listo")
        self.statusbar.addWidget(self.lbl_status)

        db_path_txt = str(self.db_manager.db_path) if self.db_manager else "Modo cliente"
        self.lbl_db_path = QLabel(f"DB: {db_path_txt}")
        self.lbl_db_path.setStyleSheet(f"color: {AppStyles.TEXT_DIM}; font-size: 8pt;")
        self.statusbar.addPermanentWidget(self.lbl_db_path)

        razon = get_provider().config.get("razon_social")
        if razon:
            self.setWindowTitle(f"Gestión Imprenta Pro v1.0 — {razon}")
        from models.usuario_model import UsuarioModel
        usuario = UsuarioModel.usuario_actual()
        if usuario:
            lbl_user = QLabel(f"👤  {usuario.nombre}  ({usuario.rol})")
            lbl_user.setStyleSheet(f"color: #40c060; font-size: 9pt; padding-right: 8px;")
            self.statusbar.addPermanentWidget(lbl_user)
        # Badge modo LAN
        from network.net_config import get_modo, MODO_LOCAL, MODO_SERVER, MODO_CLIENT
        modo_lan = get_modo()
        if modo_lan != MODO_LOCAL:
            iconos = {MODO_SERVER: "🖥️ SERVIDOR", MODO_CLIENT: "🔗 CLIENTE"}
            colores = {MODO_SERVER: "#4080e0", MODO_CLIENT: "#e0a040"}
            lbl_lan = QLabel(iconos.get(modo_lan, "🌐 LAN"))
            lbl_lan.setStyleSheet(
                f"color: {colores.get(modo_lan,'#e0e0e0')}; "
                f"font-size: 8pt; font-weight: bold; padding: 2px 6px;"
                f"background: #1a2a3a; border-radius: 3px; margin-right: 4px;"
            )
            lbl_lan.setToolTip("Modo de red LAN activo")
            self.statusbar.addPermanentWidget(lbl_lan)

    # ─── SHORTCUTS ────────────────────────────────────────────────────────────

    def _setup_shortcuts(self) -> None:
        from PySide6.QtGui import QShortcut
        QShortcut(QKeySequence("F5"), self).activated.connect(self._refrescar_tab_actual)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._nuevo_pedido)

    # ─── SLOTS ────────────────────────────────────────────────────────────────

    def _on_tab_cambiado(self, index: int) -> None:
        """Refresca el tab al cambiar."""
        tabs_refrescables = [self.tab_pedidos, self.tab_taller, self.tab_cc]
        if index < len(tabs_refrescables):
            tabs_refrescables[index].refrescar()

    def _refrescar_tab_actual(self) -> None:
        idx = self.tabs.currentIndex()
        self._on_tab_cambiado(idx)
        self.lbl_status.setText("🔄  Datos actualizados")
        QTimer.singleShot(2000, lambda: self.lbl_status.setText("✅  Sistema listo"))

    def _nuevo_pedido(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.tab_pedidos._nuevo_pedido()

    # ── ABM ──────────────────────────────────────────────────────────────────

    def _abm_clientes(self) -> None:
        from views.abm.abm_views import ABMClientes
        ABMClientes(self).exec()

    def _abm_productos(self) -> None:
        from views.abm.abm_views import ABMProductos
        ABMProductos(self).exec()

    def _abm_tipos(self) -> None:
        from views.abm.abm_views import ABMTiposTrabajo
        ABMTiposTrabajo(self).exec()

    def _abm_insumos(self) -> None:
        from views.abm.abm_views import ABMInsumos
        ABMInsumos(self).exec()

    # ── REPORTES ─────────────────────────────────────────────────────────────

    def _reporte_ventas(self) -> None:
        from views.reportes.reportes import ReporteVentasMes
        ReporteVentasMes(self).exec()

    def _reporte_balance(self) -> None:
        from views.reportes.reportes import ReporteBalance
        ReporteBalance(self).exec()

    def _reporte_productos(self) -> None:
        from views.reportes.reportes import ReporteProductos
        ReporteProductos(self).exec()

    # ── CONFIG ───────────────────────────────────────────────────────────────

    def _config_imprenta(self) -> None:
        from views.dialogs.dialogo_config import DialogoConfig
        dlg = DialogoConfig(self)
        if dlg.exec():
            razon = get_provider().config.get("razon_social")
            self.setWindowTitle(f"Gestión Imprenta Pro v1.0 — {razon}")

    # ── BACKUP ───────────────────────────────────────────────────────────────

    def _hacer_backup(self) -> None:
        from controllers.backup_controller import BackupController
        ruta = BackupController().hacer_backup()
        if ruta:
            QMessageBox.information(self, "Backup",
                f"Backup creado exitosamente en:\n{ruta}")
        else:
            QMessageBox.warning(self, "Error", "No se pudo crear el backup.")

    # ── AYUDA ────────────────────────────────────────────────────────────────

    def _mostrar_ayuda(self) -> None:
        QMessageBox.information(self, "Ayuda",
            "Atajos de teclado:\n\n"
            "Ctrl+N  →  Nuevo Pedido\n"
            "Ctrl+S  →  Guardar (en diálogos)\n"
            "F5      →  Refrescar\n"
            "F1      →  Ayuda\n"
            "Supr    →  Eliminar línea (en tabla detalle)\n"
            "Alt+F4  →  Salir\n\n"
            "Doble click en una fila → Editar pedido"
        )

    def _acerca_de(self) -> None:
        QMessageBox.about(self, "Acerca de",
            "<h2>Gestión Imprenta Pro v1.0</h2>"
            "<p>Sistema de gestión para imprentas.</p>"
            "<p>Desarrollado con Python 3.11 + PySide6 + SQLite.</p>"
        )

    def _config_afip(self) -> None:
        from views.dialogs.dialogo_config_afip import DialogoConfigAFIP
        DialogoConfigAFIP(self).exec()

    def _config_lan(self) -> None:
        from views.dialogs.dialogo_red import DialogoConfigRed
        DialogoConfigRed(self).exec()

    def _abm_usuarios(self) -> None:
        from views.abm.abm_usuarios import ABMUsuarios
        ABMUsuarios(self).exec()

    def _cambiar_password(self) -> None:
        from views.abm.abm_usuarios import DialogoCambiarPassword
        from models.usuario_model import UsuarioModel
        usuario = UsuarioModel.usuario_actual()
        if usuario:
            DialogoCambiarPassword(usuario, self).exec()

    # ─── CIERRE ───────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Backup automático al cerrar."""
        from controllers.backup_controller import BackupController
        BackupController().hacer_backup()
        event.accept()
