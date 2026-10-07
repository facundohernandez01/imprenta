# Gestión Imprenta Pro v1.0

Sistema de gestión para imprentas. Desarrollado con Python 3.11 + PySide6 + SQLite.

## Requisitos

- Python 3.11+
- Windows 10/11 (también funciona en Linux/macOS)

## Instalación

```bash
# 1. Clonar / descomprimir el proyecto
cd gestion_imprenta

# 2. Crear entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 3. Instalar dependencias
pip install -r requirements.txt
```

## Ejecutar

```bash
python main.py
```

En el primer inicio se pedirán los datos de la imprenta (razón social, CUIT, etc.).

## Estructura del proyecto

```
gestion_imprenta/
├── main.py                  # Entry point
├── db/                      # Conexión y esquema SQLite
├── models/                  # Dataclasses + CRUD con QSqlQuery
├── views/                   # Toda la UI PySide6
│   ├── dialogs/             # Diálogos: Pedido, Cliente, Pago, Config
│   ├── abm/                 # Ventanas ABM
│   └── reportes/            # Reportes matplotlib
├── controllers/             # Lógica de negocio y backup
├── utils/                   # PDF (ReportLab), helpers, estilos QSS
└── requirements.txt
```

## Base de datos

La DB se guarda en:
- **Windows:** `%APPDATA%\ImprentaPro\gestion_imprenta.db`
- **Linux:**   `~/.local/share/ImprentaPro/gestion_imprenta.db`

Backups automáticos al cerrar: misma carpeta en `/backups/db_YYYYMMDD_HHMM.db`

Los PDFs generados se guardan en `/presupuestos/`.

## Compilar a .exe (PyInstaller)

```bash
pip install pyinstaller

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "GestionImprentaPro" ^
  --icon resources/icon.ico ^
  --add-data "resources;resources" ^
  main.py
```

El ejecutable queda en `dist/GestionImprentaPro.exe`.

> **Nota:** En Windows usar `^` para continuar línea. En Linux/macOS usar `\`.

### Opción NSIS (instalador Windows)

Después de compilar con PyInstaller, podés usar NSIS para generar un instalador `.exe` completo.

## Atajos de teclado

| Atajo     | Acción                          |
|-----------|---------------------------------|
| Ctrl+N    | Nuevo Pedido                    |
| Ctrl+S    | Guardar (en diálogos)           |
| F5        | Refrescar tabla                 |
| F1        | Ayuda                           |
| Supr      | Eliminar línea en detalle       |
| Alt+F4    | Salir                           |

## Estados de pedido

`Presupuesto` → `Diseño` → `Aprobación Cliente` → `En Taller` → `Listo para Entregar` → `Entregado` → `Pendiente de Cobro` → `Cobrado`

El estado `Cancelado` se puede asignar en cualquier momento.

## Funcionalidades principales

- **Pedidos completos** con detalle, medidas (m²), descuento y seña
- **Numeración automática** por año: `2026-0001`, `2026-0002`...
- **PDF presupuesto** con logo, datos del cliente e ítems (ReportLab)
- **WhatsApp** directo con mensaje pre-armado
- **Kanban** del taller con drag & drop entre columnas
- **Cuenta corriente** por cliente con historial de pagos
- **Reportes** con gráficos matplotlib: ventas del mes, balance, productos
- **ABM completos** para clientes, productos, tipos de trabajo e insumos
- **Backup automático** al cerrar la aplicación
