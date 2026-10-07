"""
Gestión Imprenta Pro v1.0
Entry point principal.
"""
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from PySide6.QtWidgets import QApplication, QSplashScreen, QMessageBox, QDialog
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt, QTimer

from db.database import DatabaseManager
from utils.styles import AppStyles


def crear_splash() -> QSplashScreen:
    pixmap = QPixmap(500, 300)
    pixmap.fill(QColor("#1a1a2e"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("#e94560"))
    font = QFont("Segoe UI", 26, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter,
                     "🖨️ Gestión Imprenta Pro")
    painter.setPen(QColor("#a0a0b0"))
    font2 = QFont("Segoe UI", 10)
    painter.setFont(font2)
    painter.drawText(pixmap.rect().adjusted(0, 70, 0, 0),
                     Qt.AlignmentFlag.AlignCenter, "v1.0 — Iniciando...")
    painter.end()
    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    return splash


def _splash_msg(splash, msg: str):
    splash.showMessage(msg,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#a0a0b0"))
    QApplication.processEvents()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Gestión Imprenta Pro")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("ImprentaPro")
    app.setFont(QFont("Segoe UI", 10))

    splash = crear_splash()
    splash.show()
    app.processEvents()

    # ── 1. Modo de red ───────────────────────────────────────────────────
    from network.net_config import get_modo, MODO_LOCAL, MODO_SERVER, MODO_CLIENT
    modo_red = get_modo()

    # ── 2. Si es SERVER o LOCAL: inicializar DB local ────────────────────
    if modo_red in (MODO_LOCAL, MODO_SERVER):
        _splash_msg(splash, "Iniciando base de datos...")
        db_manager = DatabaseManager()
        if not db_manager.inicializar():
            QMessageBox.critical(None, "Error", "No se pudo inicializar la base de datos.")
            sys.exit(1)
    else:
        # CLIENT: no necesita DB local
        db_manager = None

    # ── 3. Si es SERVER: arrancar Flask ──────────────────────────────────
    if modo_red == MODO_SERVER:
        from network.net_config import cargar, get_port
        _splash_msg(splash, "Iniciando servidor de red...")
        try:
            from server.flask_server import start_server, is_running
            cfg = cargar()
            if not is_running():
                start_server(port=get_port(), api_key=cfg.get("api_key", ""))
        except ModuleNotFoundError:
            QMessageBox.critical(
                None, "Flask no instalado",
                "Falta instalar Flask para el modo servidor.\n\n"
                "Ejecutá en la terminal:\n"
                "    pip install flask requests\n\n"
                "Luego reiniciá la aplicación."
            )
            sys.exit(1)

    # ── 4. Si es CLIENT: verificar conectividad ──────────────────────────
    if modo_red == MODO_CLIENT:
        _splash_msg(splash, "Conectando al servidor...")
        from network.net_config import cargar
        from network.http_client import test_conexion
        cfg = cargar()
        resultado = test_conexion(
            cfg.get("server_ip", ""),
            cfg.get("server_port", 7432),
            cfg.get("api_key", ""),
        )
        if not resultado["ok"]:
            splash.hide()
            resp = QMessageBox.critical(
                None, "Sin conexión al servidor",
                f"No se puede conectar al servidor:\n\n{resultado['mensaje']}\n\n"
                "¿Querés cambiar la configuración de red?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp == QMessageBox.StandardButton.Yes:
                app.setStyleSheet(AppStyles.get_dark_theme())
                from views.dialogs.dialogo_red import DialogoConfigRed
                DialogoConfigRed().exec()
                # Reiniciar después de reconfigurar
                QMessageBox.information(None, "Reiniciar",
                    "Reiniciá la aplicación para aplicar los cambios.")
            sys.exit(0)

    # ── 5. Estilos ───────────────────────────────────────────────────────
    app.setStyleSheet(AppStyles.get_dark_theme())

    # ── 6. Login ─────────────────────────────────────────────────────────
    _splash_msg(splash, "Cargando interfaz...")
    splash.hide()

    from views.dialogs.dialogo_login import DialogoLogin
    login = DialogoLogin()
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    # ── 7. MainWindow ────────────────────────────────────────────────────
    from views.main_window import MainWindow
    main_window = MainWindow(db_manager)

    # Config inicial (solo en local/server)
    if modo_red in (MODO_LOCAL, MODO_SERVER):
        from network.data_provider import get_provider
        if not get_provider().config.esta_configurado():
            from views.dialogs.dialogo_config import DialogoConfig
            DialogoConfig(main_window).exec()

    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
