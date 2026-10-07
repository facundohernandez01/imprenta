"""
Temas visuales QSS para la aplicación.
"""


class AppStyles:
    """Proveedor de estilos QSS."""

    # Paleta de colores dark
    BG_DARK    = "#0f0f1a"
    BG_MEDIUM  = "#1a1a2e"
    BG_LIGHT   = "#16213e"
    BG_WIDGET  = "#0f3460"
    ACCENT     = "#e94560"
    ACCENT2    = "#533483"
    TEXT_MAIN  = "#eaeaea"
    TEXT_DIM   = "#a0a0b0"
    BORDER     = "#2a2a4a"
    SUCCESS    = "#40c060"
    WARNING    = "#e0c040"
    DANGER     = "#e04040"
    INFO       = "#4080e0"

    @classmethod
    def _resource_url(cls, filename: str) -> str:
        """Retorna ruta absoluta de un recurso (funciona en dev y en .exe).

        QSS exige `image: url(...)` con archivos reales: los triángulos con
        bordes CSS y las flechas nativas no se dibujan cuando se personaliza
        ::drop-down / ::up-button, por eso se usan estos PNG.
        Nota: debe ser ruta plana, el esquema file:// no lo toma.
        """
        import sys
        from pathlib import Path
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        return str(base / "resources" / filename).replace("\\", "/")

    @classmethod
    def get_dark_theme(cls) -> str:
        url_down = cls._resource_url("arrow_down.png")
        url_up = cls._resource_url("arrow_up.png")
        return f"""
        /* ── BASE ── */
        QWidget {{
            background-color: {cls.BG_MEDIUM};
            color: {cls.TEXT_MAIN};
            font-family: "Segoe UI", "Arial", sans-serif;
            font-size: 10pt;
        }}
        QMainWindow {{
            background-color: {cls.BG_DARK};
        }}

        /* ── TABS ── */
        QTabWidget::pane {{
            border: 1px solid {cls.BORDER};
            background-color: {cls.BG_MEDIUM};
            border-radius: 4px;
        }}
        QTabBar::tab {{
            background-color: {cls.BG_LIGHT};
            color: {cls.TEXT_DIM};
            padding: 10px 22px;
            border: 1px solid {cls.BORDER};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            min-width: 120px;
        }}
        QTabBar::tab:selected {{
            background-color: {cls.BG_MEDIUM};
            color: {cls.ACCENT};
            border-bottom: 2px solid {cls.ACCENT};
        }}
        QTabBar::tab:hover {{
            background-color: {cls.BG_WIDGET};
            color: {cls.TEXT_MAIN};
        }}

        /* ── BOTONES ── */
        QPushButton {{
            background-color: {cls.BG_WIDGET};
            color: {cls.TEXT_MAIN};
            border: 1px solid {cls.BORDER};
            border-radius: 5px;
            padding: 7px 16px;
            min-height: 28px;
        }}
        QPushButton:hover {{
            background-color: {cls.ACCENT};
            border-color: {cls.ACCENT};
        }}
        QPushButton:pressed {{
            background-color: #c0304a;
        }}
        QPushButton:disabled {{
            background-color: #1a1a2e;
            color: #505060;
            border-color: #2a2a3a;
        }}
        QPushButton#btn_primary {{
            background-color: {cls.ACCENT};
            font-weight: bold;
        }}
        QPushButton#btn_success {{
            background-color: #1a5a2a;
            color: {cls.SUCCESS};
            border-color: {cls.SUCCESS};
        }}
        QPushButton#btn_success:hover {{
            background-color: {cls.SUCCESS};
            color: #000;
        }}
        QPushButton#btn_danger {{
            background-color: #3a1a1a;
            color: {cls.DANGER};
            border-color: {cls.DANGER};
        }}
        QPushButton#btn_danger:hover {{
            background-color: {cls.DANGER};
            color: #fff;
        }}
        QPushButton#btn_flat {{
            background-color: transparent;
            border: none;
            padding: 4px 8px;
        }}
        QPushButton#btn_flat:hover {{
            background-color: {cls.BG_WIDGET};
            border-radius: 4px;
        }}

        /* ── INPUTS ── */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {cls.BG_LIGHT};
            color: {cls.TEXT_MAIN};
            border: 1px solid {cls.BORDER};
            border-radius: 4px;
            padding: 6px 10px;
            selection-background-color: {cls.ACCENT};
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border-color: {cls.ACCENT};
        }}
        QSpinBox, QDoubleSpinBox {{
            background-color: {cls.BG_LIGHT};
            color: {cls.TEXT_MAIN};
            border: 1px solid {cls.BORDER};
            border-radius: 4px;
            padding: 5px 8px;
            padding-right: 24px;
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {cls.ACCENT};
        }}
        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            background-color: {cls.BG_WIDGET};
            border: none;
            border-top-right-radius: 4px;
            width: 20px;
            height: 16px;
        }}
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            background-color: {cls.BG_WIDGET};
            border: none;
            border-bottom-right-radius: 4px;
            width: 20px;
            height: 16px;
        }}
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {cls.ACCENT};
        }}
        /* Flechas con imagen (sin esto, al personalizar
           ::up-button/::down-button Qt oculta las flechas nativas
           y los contadores quedan "vacíos"). */
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            image: url({url_up});
            width: 14px;
            height: 10px;
        }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
            image: url({url_down});
            width: 14px;
            height: 10px;
        }}

        /* ── COMBOBOX ── */
        QComboBox {{
            background-color: {cls.BG_LIGHT};
            color: {cls.TEXT_MAIN};
            border: 1px solid {cls.BORDER};
            border-radius: 4px;
            padding: 6px 10px;
            padding-right: 30px;
            min-height: 28px;
        }}
        QComboBox:focus {{
            border-color: {cls.ACCENT};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            border: none;
            border-left: 1px solid {cls.BORDER};
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
            background-color: {cls.BG_WIDGET};
            width: 24px;
        }}
        QComboBox::drop-down:hover {{
            background-color: {cls.ACCENT};
        }}
        /* Flecha con imagen (sin esto, al personalizar ::drop-down
           Qt oculta la flecha nativa y el combo queda sin indicador). */
        QComboBox::down-arrow {{
            image: url({url_down});
            width: 14px;
            height: 10px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {cls.BG_LIGHT};
            color: {cls.TEXT_MAIN};
            border: 1px solid {cls.BORDER};
            selection-background-color: {cls.ACCENT};
        }}

        /* ── DATE EDIT ── */
        QDateEdit {{
            background-color: {cls.BG_LIGHT};
            color: {cls.TEXT_MAIN};
            border: 1px solid {cls.BORDER};
            border-radius: 4px;
            padding: 5px 8px;
            padding-right: 30px;
        }}
        QDateEdit:focus {{
            border-color: {cls.ACCENT};
        }}
        QDateEdit::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            border: none;
            border-left: 1px solid {cls.BORDER};
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
            background-color: {cls.BG_WIDGET};
            width: 24px;
        }}
        QDateEdit::drop-down:hover {{
            background-color: {cls.ACCENT};
        }}
        QDateEdit::down-arrow {{
            image: url({url_down});
            width: 14px;
            height: 10px;
        }}

        /* ── TABLAS ── */
        QTableView, QTableWidget {{
            background-color: {cls.BG_LIGHT};
            color: {cls.TEXT_MAIN};
            gridline-color: {cls.BORDER};
            border: 1px solid {cls.BORDER};
            border-radius: 4px;
            selection-background-color: #1a2a4a;
            selection-color: {cls.TEXT_MAIN};
            alternate-background-color: #131325;
        }}
        QTableView::item:selected, QTableWidget::item:selected {{
            background-color: #1e2e5a;
            color: {cls.TEXT_MAIN};
        }}
        QHeaderView::section {{
            background-color: {cls.BG_DARK};
            color: {cls.TEXT_DIM};
            padding: 8px;
            border: none;
            border-right: 1px solid {cls.BORDER};
            border-bottom: 1px solid {cls.BORDER};
            font-weight: bold;
        }}
        QHeaderView::section:hover {{
            background-color: {cls.BG_WIDGET};
            color: {cls.TEXT_MAIN};
        }}

        /* ── SCROLLBAR ── */
        QScrollBar:vertical {{
            background-color: {cls.BG_DARK};
            width: 10px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {cls.BG_WIDGET};
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {cls.ACCENT};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background-color: {cls.BG_DARK};
            height: 10px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {cls.BG_WIDGET};
            border-radius: 5px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {cls.ACCENT};
        }}

        /* ── GROUPBOX ── */
        QGroupBox {{
            color: {cls.TEXT_DIM};
            border: 1px solid {cls.BORDER};
            border-radius: 6px;
            margin-top: 14px;
            padding-top: 8px;
            font-weight: bold;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            color: {cls.ACCENT};
        }}

        /* ── DIALOG ── */
        QDialog {{
            background-color: {cls.BG_MEDIUM};
        }}

        /* ── MENSAJES ── */
        QMessageBox {{
            background-color: {cls.BG_MEDIUM};
        }}
        QMessageBox QPushButton {{
            min-width: 80px;
        }}

        /* ── TOOLBAR ── */
        QToolBar {{
            background-color: {cls.BG_DARK};
            border: none;
            border-bottom: 1px solid {cls.BORDER};
            padding: 4px;
            spacing: 4px;
        }}
        QToolButton {{
            background-color: transparent;
            color: {cls.TEXT_MAIN};
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 6px 12px;
        }}
        QToolButton:hover {{
            background-color: {cls.BG_WIDGET};
            border-color: {cls.BORDER};
        }}

        /* ── MENUBAR ── */
        QMenuBar {{
            background-color: {cls.BG_DARK};
            color: {cls.TEXT_MAIN};
            border-bottom: 1px solid {cls.BORDER};
        }}
        QMenuBar::item {{
            padding: 6px 14px;
        }}
        QMenuBar::item:selected {{
            background-color: {cls.BG_WIDGET};
        }}
        QMenu {{
            background-color: {cls.BG_LIGHT};
            color: {cls.TEXT_MAIN};
            border: 1px solid {cls.BORDER};
        }}
        QMenu::item:selected {{
            background-color: {cls.ACCENT};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {cls.BORDER};
        }}

        /* ── STATUSBAR ── */
        QStatusBar {{
            background-color: {cls.BG_DARK};
            color: {cls.TEXT_DIM};
            border-top: 1px solid {cls.BORDER};
        }}

        /* ── LABELS ESPECIALES ── */
        QLabel#lbl_total {{
            font-size: 16pt;
            font-weight: bold;
            color: {cls.SUCCESS};
        }}
        QLabel#lbl_saldo_rojo {{
            color: {cls.DANGER};
            font-weight: bold;
        }}
        QLabel#lbl_header {{
            font-size: 13pt;
            font-weight: bold;
            color: {cls.TEXT_MAIN};
        }}
        QLabel#lbl_nro_pedido {{
            font-size: 14pt;
            font-weight: bold;
            color: {cls.ACCENT};
        }}

        /* ── SPLITTER ── */
        QSplitter::handle {{
            background-color: {cls.BORDER};
        }}

        /* ── TOOLTIP ── */
        QToolTip {{
            background-color: {cls.BG_DARK};
            color: {cls.TEXT_MAIN};
            border: 1px solid {cls.BORDER};
            padding: 4px;
        }}

        /* ── CHECKBOX / RADIO ── */
        QCheckBox {{
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {cls.BORDER};
            border-radius: 3px;
            background-color: {cls.BG_LIGHT};
        }}
        QCheckBox::indicator:checked {{
            background-color: {cls.ACCENT};
            border-color: {cls.ACCENT};
        }}

        /* ── FRAME KANBAN ── */
        QFrame#kanban_card {{
            background-color: {cls.BG_LIGHT};
            border: 1px solid {cls.BORDER};
            border-radius: 6px;
        }}
        QFrame#kanban_card:hover {{
            border-color: {cls.ACCENT};
            background-color: #1a1a38;
        }}
        """

    @classmethod
    def badge_style(cls, estado: str) -> str:
        """Retorna estilo CSS inline para badge de estado."""
        from models.pedido_model import ESTADO_COLORES
        bg, fg = ESTADO_COLORES.get(estado, ("#3a3a5c", "#a0a0d0"))
        return (
            f"background-color: {bg}; color: {fg}; "
            f"border-radius: 4px; padding: 3px 8px; "
            f"font-weight: bold; font-size: 9pt;"
        )
