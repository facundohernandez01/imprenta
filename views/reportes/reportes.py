"""
Ventanas de reportes con matplotlib embebido en Qt.
"""
from datetime import date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt

from controllers.reporte_controller import ReporteController
from utils.helpers import fmt_moneda
from utils.styles import AppStyles
from network.data_provider import get_provider

# Importación segura de matplotlib
try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False


# ─── REPORTE VENTAS DEL MES ───────────────────────────────────────────────────

class ReporteVentasMes(QDialog):
    """Gráfico de barras de ventas por día del mes actual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctrl = get_provider().reportes
        self.setWindowTitle("Ventas del Mes")
        self.setMinimumSize(800, 550)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Selector de mes/año
        ctrl_lay = QHBoxLayout()
        ctrl_lay.addWidget(QLabel("Mes:"))
        self.cmb_mes = QComboBox()
        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        self.cmb_mes.addItems(meses)
        self.cmb_mes.setCurrentIndex(date.today().month - 1)
        ctrl_lay.addWidget(self.cmb_mes)

        ctrl_lay.addWidget(QLabel("Año:"))
        self.cmb_anio = QComboBox()
        anio_actual = date.today().year
        for a in range(anio_actual - 2, anio_actual + 1):
            self.cmb_anio.addItem(str(a), a)
        self.cmb_anio.setCurrentIndex(self.cmb_anio.count() - 1)
        ctrl_lay.addWidget(self.cmb_anio)

        btn_cargar = QPushButton("🔄  Actualizar")
        btn_cargar.clicked.connect(self._cargar)
        ctrl_lay.addWidget(btn_cargar)
        ctrl_lay.addStretch()
        layout.addLayout(ctrl_lay)

        # Canvas matplotlib
        if MATPLOTLIB_OK:
            self.figure = Figure(figsize=(8, 4), facecolor="#1a1a2e")
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setMinimumHeight(280)
            layout.addWidget(self.canvas)
        else:
            lbl = QLabel("⚠️  matplotlib no disponible. Instalá con: pip install matplotlib")
            lbl.setStyleSheet("color: #e04040;")
            layout.addWidget(lbl)

        # Tabla resumen debajo del gráfico
        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Día", "Total Vendido"])
        self.tabla.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 80)
        self.tabla.setMaximumHeight(180)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        layout.addWidget(self.tabla)

        # Total del mes
        self.lbl_total_mes = QLabel("Total del mes: $0,00")
        self.lbl_total_mes.setObjectName("lbl_total")
        self.lbl_total_mes.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.lbl_total_mes)

    def _cargar(self) -> None:
        mes  = self.cmb_mes.currentIndex() + 1
        anio = self.cmb_anio.currentData()
        datos = self.ctrl.ventas_por_dia_mes(anio, mes)

        # Poblar gráfico
        if MATPLOTLIB_OK:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.set_facecolor("#16213e")
            self.figure.patch.set_facecolor("#1a1a2e")

            if datos:
                dias   = [d["dia"] for d in datos]
                totales = [d["total"] for d in datos]
                bars = ax.bar(dias, totales, color="#e94560", alpha=0.85, width=0.6)
                ax.set_xlabel("Día", color="#a0a0b0")
                ax.set_ylabel("$ Vendido", color="#a0a0b0")
                nombre_mes = self.cmb_mes.currentText()
                ax.set_title(f"Ventas — {nombre_mes} {anio}",
                             color="#eaeaea", fontsize=12)
                ax.tick_params(colors="#a0a0b0")
                ax.spines["bottom"].set_color("#2a2a4a")
                ax.spines["left"].set_color("#2a2a4a")
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                # Etiquetas sobre las barras
                for bar, val in zip(bars, totales):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(totales)*0.01,
                            f"${val:,.0f}", ha="center", va="bottom",
                            color="#eaeaea", fontsize=7)
            else:
                ax.text(0.5, 0.5, "Sin datos para este período",
                        ha="center", va="center", color="#a0a0b0", fontsize=12,
                        transform=ax.transAxes)
            self.canvas.draw()

        # Poblar tabla
        self.tabla.setRowCount(0)
        total_mes = 0.0
        for d in datos:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            self.tabla.setItem(row, 0, QTableWidgetItem(str(d["dia"])))
            item_total = QTableWidgetItem(fmt_moneda(d["total"]))
            item_total.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(row, 1, item_total)
            self.tabla.setRowHeight(row, 26)
            total_mes += d["total"]

        self.lbl_total_mes.setText(f"Total del mes: {fmt_moneda(total_mes)}")


# ─── REPORTE BALANCE GENERAL ──────────────────────────────────────────────────

class ReporteBalance(QDialog):
    """Balance histórico general."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctrl = get_provider().reportes
        self.setWindowTitle("Balance General")
        self.setMinimumSize(500, 380)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        titulo = QLabel("📊  Balance General Histórico")
        titulo.setObjectName("lbl_header")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titulo)

        self.grp = QGroupBox("Totales")
        form = QVBoxLayout(self.grp)

        def _fila(label: str, obj_name: str = "") -> tuple[QLabel, QLabel]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 11pt; color: #a0a0b0;")
            val = QLabel("$0,00")
            val.setStyleSheet("font-size: 13pt; font-weight: bold;")
            if obj_name:
                val.setObjectName(obj_name)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            form.addLayout(row)
            return lbl, val

        _, self.lbl_facturado  = _fila("💼  Total Facturado Histórico:")
        _, self.lbl_cobrado    = _fila("✅  Total Cobrado:")
        _, self.lbl_pendiente  = _fila("⏳  Total Pendiente de Cobro:")
        _, self.lbl_senas      = _fila("💰  Total en Señas:")
        layout.addWidget(self.grp)

        btn_refrescar = QPushButton("🔄  Actualizar")
        btn_refrescar.clicked.connect(self._cargar)
        layout.addWidget(btn_refrescar, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addStretch()

    def _cargar(self) -> None:
        data = self.ctrl.balance_general()
        self.lbl_facturado.setText(fmt_moneda(data["facturado"]))
        self.lbl_cobrado.setText(fmt_moneda(data["cobrado"]))
        self.lbl_pendiente.setText(fmt_moneda(data["pendiente"]))
        self.lbl_senas.setText(fmt_moneda(data["senas"]))
        # Color rojo si hay pendiente
        color = AppStyles.DANGER if data["pendiente"] > 0 else AppStyles.SUCCESS
        self.lbl_pendiente.setStyleSheet(
            f"font-size: 13pt; font-weight: bold; color: {color};"
        )


# ─── REPORTE PRODUCTOS MÁS VENDIDOS ──────────────────────────────────────────

class ReporteProductos(QDialog):
    """Top productos vendidos del mes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctrl = get_provider().reportes
        self.setWindowTitle("Productos Más Vendidos")
        self.setMinimumSize(600, 450)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        ctrl_lay = QHBoxLayout()
        ctrl_lay.addWidget(QLabel("Mes:"))
        self.cmb_mes = QComboBox()
        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        self.cmb_mes.addItems(meses)
        self.cmb_mes.setCurrentIndex(date.today().month - 1)
        ctrl_lay.addWidget(self.cmb_mes)

        ctrl_lay.addWidget(QLabel("Año:"))
        self.cmb_anio = QComboBox()
        anio_actual = date.today().year
        for a in range(anio_actual - 2, anio_actual + 1):
            self.cmb_anio.addItem(str(a), a)
        self.cmb_anio.setCurrentIndex(self.cmb_anio.count() - 1)
        ctrl_lay.addWidget(self.cmb_anio)

        btn_cargar = QPushButton("🔄  Actualizar")
        btn_cargar.clicked.connect(self._cargar)
        ctrl_lay.addWidget(btn_cargar)
        ctrl_lay.addStretch()
        layout.addLayout(ctrl_lay)

        self.tabla = QTableWidget(0, 3)
        self.tabla.setHorizontalHeaderLabels([
            "Producto / Descripción", "Cantidad", "Facturado"
        ])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(1, 90)
        self.tabla.setColumnWidth(2, 110)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla)

    def _cargar(self) -> None:
        mes  = self.cmb_mes.currentIndex() + 1
        anio = self.cmb_anio.currentData()
        datos = self.ctrl.productos_mas_vendidos(anio, mes)
        self.tabla.setRowCount(0)
        for d in datos:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            self.tabla.setItem(row, 0, QTableWidgetItem(d["producto"]))
            item_cant = QTableWidgetItem(str(d["cantidad"]))
            item_cant.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_fac  = QTableWidgetItem(fmt_moneda(d["facturado"]))
            item_fac.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(row, 1, item_cant)
            self.tabla.setItem(row, 2, item_fac)
            self.tabla.setRowHeight(row, 30)
