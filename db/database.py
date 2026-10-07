"""
Gestor de base de datos SQLite con QSqlDatabase.
Crea tablas, triggers e índices en el primer inicio.
"""
import os
from pathlib import Path
from PySide6.QtSql import QSqlDatabase, QSqlQuery
from PySide6.QtCore import QStandardPaths


class DatabaseManager:
    """Maneja la conexión y esquema de la base de datos."""

    DB_NAME = "gestion_imprenta.db"
    CONNECTION_NAME = "imprenta_main"

    def __init__(self) -> None:
        # Directorio de datos de la app
        data_dir = Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        ))
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = data_dir / self.DB_NAME
        self.backup_dir = data_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.presupuestos_dir = data_dir / "presupuestos"
        self.presupuestos_dir.mkdir(exist_ok=True)

    def inicializar(self) -> bool:
        """Conecta a SQLite y crea el esquema si no existe."""
        db = QSqlDatabase.addDatabase("QSQLITE", self.CONNECTION_NAME)
        db.setDatabaseName(str(self.db_path))

        if not db.open():
            print(f"Error DB: {db.lastError().text()}")
            return False

        query = QSqlQuery(db)
        # Habilitar foreign keys
        query.exec("PRAGMA foreign_keys = ON;")
        query.exec("PRAGMA journal_mode = WAL;")

        return self._crear_tablas(query)

    def _crear_tablas(self, query: QSqlQuery) -> bool:
        """Crea todas las tablas, triggers e índices."""
        sentencias = self._get_schema_sql()
        for sql in sentencias:
            if not query.exec(sql):
                print(f"Error creando esquema: {query.lastError().text()}")
                print(f"SQL: {sql[:100]}")
                return False
        # Migraciones seguras (columnas que pueden no existir)
        migraciones = [
            "ALTER TABLE pedidos ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id)",
            "ALTER TABLE clientes ADD COLUMN ingresos_brutos TEXT",
            """CREATE TABLE IF NOT EXISTS pedido_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id   INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                fecha       TEXT    DEFAULT (datetime('now','localtime')),
                usuario     TEXT    DEFAULT '',
                tipo        TEXT    DEFAULT 'cambio',
                descripcion TEXT    NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_pedido_log ON pedido_log(pedido_id)",
        ]
        for sql in migraciones:
            try:
                query.exec(sql)
            except Exception:
                pass  # columna ya existe

        # Usuario admin por defecto
        query.exec("""
            INSERT OR IGNORE INTO usuarios(username, nombre, password_hash, rol)
            VALUES('admin', 'Administrador',
                   'pbkdf2:sha256:admin123', 'admin')
        """)
        return True

    @staticmethod
    def get_db() -> QSqlDatabase:
        """Retorna la conexión activa."""
        return QSqlDatabase.database(DatabaseManager.CONNECTION_NAME)

    def _get_schema_sql(self) -> list[str]:
        """Retorna lista de sentencias SQL para crear el esquema completo."""
        return [
            # === TABLA CONFIG ===
            """
            CREATE TABLE IF NOT EXISTS config (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                clave TEXT UNIQUE NOT NULL,
                valor TEXT
            )
            """,

            # === TABLA CLIENTES ===
            """
            CREATE TABLE IF NOT EXISTS clientes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT NOT NULL,
                telefono    TEXT,
                whatsapp    TEXT,
                email       TEXT,
                cuit        TEXT,
                direccion   TEXT,
                notas       TEXT,
                fecha_alta  DATE DEFAULT CURRENT_DATE,
                activo      BOOLEAN DEFAULT 1
            )
            """,

            # === TABLA TIPOS_TRABAJO ===
            """
            CREATE TABLE IF NOT EXISTS tipos_trabajo (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT UNIQUE NOT NULL,
                descripcion TEXT
            )
            """,

            # === TABLA PRODUCTOS ===
            """
            CREATE TABLE IF NOT EXISTS productos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre          TEXT NOT NULL,
                tipo_trabajo_id INTEGER REFERENCES tipos_trabajo(id) ON DELETE SET NULL,
                unidad          TEXT DEFAULT 'unidad',
                precio_base     REAL DEFAULT 0,
                activo          BOOLEAN DEFAULT 1
            )
            """,

            # === TABLA INSUMOS ===
            """
            CREATE TABLE IF NOT EXISTS insumos (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre         TEXT NOT NULL,
                costo_unitario REAL DEFAULT 0,
                stock_actual   REAL DEFAULT 0
            )
            """,

            # === TABLA PEDIDOS ===
            """
            CREATE TABLE IF NOT EXISTS pedidos (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                nro_pedido           TEXT UNIQUE NOT NULL,
                cliente_id           INTEGER NOT NULL REFERENCES clientes(id),
                fecha_creacion       DATE DEFAULT CURRENT_DATE,
                fecha_entrega        DATE,
                estado               TEXT NOT NULL DEFAULT 'Presupuesto',
                subtotal             REAL DEFAULT 0,
                descuento            REAL DEFAULT 0,
                sena                 REAL DEFAULT 0,
                total                REAL DEFAULT 0,
                saldo                REAL DEFAULT 0,
                observaciones        TEXT,
                archivo_diseno_path  TEXT,
                fecha_entregado_real DATE,
                CHECK(estado IN (
                    'Presupuesto','Diseño','Aprobación Cliente',
                    'En Taller','Listo para Entregar','Entregado',
                    'Pendiente de Cobro','Cobrado','Cancelado'
                ))
            )
            """,

            # === TABLA PEDIDOS_DETALLE ===
            """
            CREATE TABLE IF NOT EXISTS pedidos_detalle (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id      INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                producto_id    INTEGER REFERENCES productos(id) ON DELETE SET NULL,
                descripcion    TEXT NOT NULL,
                cantidad       INTEGER NOT NULL CHECK(cantidad > 0),
                ancho          REAL DEFAULT 0,
                alto           REAL DEFAULT 0,
                precio_unitario REAL NOT NULL CHECK(precio_unitario >= 0),
                subtotal       REAL NOT NULL DEFAULT 0
            )
            """,

            # === TABLA PAGOS ===
            """
            CREATE TABLE IF NOT EXISTS pagos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id   INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                fecha       DATE DEFAULT CURRENT_DATE,
                monto       REAL NOT NULL CHECK(monto > 0),
                metodo      TEXT DEFAULT 'Efectivo',
                comprobante TEXT,
                nro_factura TEXT
            )
            """,

            # === ÍNDICES ===
            "CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos(cliente_id)",
            "CREATE INDEX IF NOT EXISTS idx_pedidos_estado ON pedidos(estado)",
            "CREATE INDEX IF NOT EXISTS idx_pedidos_fecha ON pedidos(fecha_creacion)",
            "CREATE INDEX IF NOT EXISTS idx_detalle_pedido ON pedidos_detalle(pedido_id)",
            "CREATE INDEX IF NOT EXISTS idx_pagos_pedido ON pagos(pedido_id)",

            # === TRIGGER: recalcular pedido al modificar detalle (INSERT) ===
            """
            CREATE TRIGGER IF NOT EXISTS trg_detalle_insert
            AFTER INSERT ON pedidos_detalle
            BEGIN
                UPDATE pedidos SET
                    subtotal = (SELECT COALESCE(SUM(subtotal),0) FROM pedidos_detalle WHERE pedido_id = NEW.pedido_id),
                    total    = (SELECT COALESCE(SUM(subtotal),0) FROM pedidos_detalle WHERE pedido_id = NEW.pedido_id) - descuento,
                    saldo    = (SELECT COALESCE(SUM(subtotal),0) FROM pedidos_detalle WHERE pedido_id = NEW.pedido_id) - descuento - sena
                             - (SELECT COALESCE(SUM(monto),0) FROM pagos WHERE pedido_id = NEW.pedido_id)
                WHERE id = NEW.pedido_id;
            END
            """,

            # === TRIGGER: recalcular pedido al modificar detalle (UPDATE) ===
            """
            CREATE TRIGGER IF NOT EXISTS trg_detalle_update
            AFTER UPDATE ON pedidos_detalle
            BEGIN
                UPDATE pedidos SET
                    subtotal = (SELECT COALESCE(SUM(subtotal),0) FROM pedidos_detalle WHERE pedido_id = NEW.pedido_id),
                    total    = (SELECT COALESCE(SUM(subtotal),0) FROM pedidos_detalle WHERE pedido_id = NEW.pedido_id) - descuento,
                    saldo    = (SELECT COALESCE(SUM(subtotal),0) FROM pedidos_detalle WHERE pedido_id = NEW.pedido_id) - descuento - sena
                             - (SELECT COALESCE(SUM(monto),0) FROM pagos WHERE pedido_id = NEW.pedido_id)
                WHERE id = NEW.pedido_id;
            END
            """,

            # === TRIGGER: recalcular pedido al eliminar detalle ===
            """
            CREATE TRIGGER IF NOT EXISTS trg_detalle_delete
            AFTER DELETE ON pedidos_detalle
            BEGIN
                UPDATE pedidos SET
                    subtotal = (SELECT COALESCE(SUM(subtotal),0) FROM pedidos_detalle WHERE pedido_id = OLD.pedido_id),
                    total    = (SELECT COALESCE(SUM(subtotal),0) FROM pedidos_detalle WHERE pedido_id = OLD.pedido_id) - descuento,
                    saldo    = (SELECT COALESCE(SUM(subtotal),0) FROM pedidos_detalle WHERE pedido_id = OLD.pedido_id) - descuento - sena
                             - (SELECT COALESCE(SUM(monto),0) FROM pagos WHERE pedido_id = OLD.pedido_id)
                WHERE id = OLD.pedido_id;
            END
            """,

            # === TRIGGER: recalcular saldo al insertar pago ===
            """
            CREATE TRIGGER IF NOT EXISTS trg_pago_insert
            AFTER INSERT ON pagos
            BEGIN
                UPDATE pedidos SET
                    saldo = total - sena - (SELECT COALESCE(SUM(monto),0) FROM pagos WHERE pedido_id = NEW.pedido_id)
                WHERE id = NEW.pedido_id;
            END
            """,

            # === TRIGGER: recalcular saldo al eliminar pago ===
            """
            CREATE TRIGGER IF NOT EXISTS trg_pago_delete
            AFTER DELETE ON pagos
            BEGIN
                UPDATE pedidos SET
                    saldo = total - sena - (SELECT COALESCE(SUM(monto),0) FROM pagos WHERE pedido_id = OLD.pedido_id)
                WHERE id = OLD.pedido_id;
            END
            """,

            # === TABLA USUARIOS ===
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT UNIQUE NOT NULL,
                nombre       TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                rol          TEXT DEFAULT 'operador',
                activo       BOOLEAN DEFAULT 1,
                recordar     BOOLEAN DEFAULT 0,
                ultimo_login TEXT
            )
            """,

            # === TABLA FACTURAS ELECTRONICAS ===
            """
            CREATE TABLE IF NOT EXISTS facturas (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id        INTEGER REFERENCES pedidos(id) ON DELETE SET NULL,
                pago_id          INTEGER REFERENCES pagos(id) ON DELETE SET NULL,
                cliente_id       INTEGER NOT NULL REFERENCES clientes(id),
                usuario_id       INTEGER REFERENCES usuarios(id),
                nro_factura      TEXT,
                tipo_cbte        INTEGER NOT NULL,
                punto_venta      INTEGER NOT NULL DEFAULT 1,
                fecha_emision    TEXT DEFAULT CURRENT_DATE,
                cuit_receptor    TEXT,
                razon_receptor   TEXT,
                domicilio_receptor TEXT,
                importe_neto     REAL NOT NULL DEFAULT 0,
                importe_iva      REAL DEFAULT 0,
                importe_total    REAL NOT NULL DEFAULT 0,
                alicuota_iva     INTEGER DEFAULT 5,
                concepto         INTEGER DEFAULT 1,
                moneda           TEXT DEFAULT 'PES',
                cae              TEXT,
                cae_vto          TEXT,
                estado           TEXT DEFAULT 'pendiente',
                email_enviado    BOOLEAN DEFAULT 0,
                observaciones    TEXT,
                fecha_creacion   TEXT DEFAULT CURRENT_TIMESTAMP,
                CHECK(estado IN ('pendiente','autorizada','rechazada','error'))
            )
            """,

            # === TABLA RECIBOS ===
            """
            CREATE TABLE IF NOT EXISTS recibos (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id      INTEGER REFERENCES pedidos(id),
                pago_id        INTEGER REFERENCES pagos(id),
                cliente_id     INTEGER NOT NULL REFERENCES clientes(id),
                usuario_id     INTEGER REFERENCES usuarios(id),
                nro_recibo     TEXT UNIQUE NOT NULL,
                fecha          TEXT DEFAULT CURRENT_DATE,
                monto          REAL NOT NULL,
                metodo         TEXT,
                concepto       TEXT,
                email_enviado  BOOLEAN DEFAULT 0,
                pdf_path       TEXT
            )
            """,

            # Índices nuevos
            "CREATE INDEX IF NOT EXISTS idx_facturas_pedido ON facturas(pedido_id)",
            "CREATE INDEX IF NOT EXISTS idx_facturas_cliente ON facturas(cliente_id)",
            "CREATE INDEX IF NOT EXISTS idx_recibos_pedido ON recibos(pedido_id)",
            "CREATE INDEX IF NOT EXISTS idx_pedidos_usuario ON pedidos(id)",

            # Columna usuario_id en pedidos (ALTER TABLE ignora si ya existe)
            # Se hace en migración aparte

            # === DATOS INICIALES tipos_trabajo ===
            "INSERT OR IGNORE INTO tipos_trabajo(nombre, descripcion) VALUES('Tarjetas', 'Tarjetas personales y comerciales')",
            "INSERT OR IGNORE INTO tipos_trabajo(nombre, descripcion) VALUES('Vinilo', 'Impresión en vinilo adhesivo')",
            "INSERT OR IGNORE INTO tipos_trabajo(nombre, descripcion) VALUES('Lona', 'Impresión en lona/banner')",
            "INSERT OR IGNORE INTO tipos_trabajo(nombre, descripcion) VALUES('Plotter', 'Corte plotter')",
            "INSERT OR IGNORE INTO tipos_trabajo(nombre, descripcion) VALUES('DTF', 'Direct to Film')",
            "INSERT OR IGNORE INTO tipos_trabajo(nombre, descripcion) VALUES('Offset', 'Impresión offset')",
            "INSERT OR IGNORE INTO tipos_trabajo(nombre, descripcion) VALUES('Digital', 'Impresión digital general')",
        ]
