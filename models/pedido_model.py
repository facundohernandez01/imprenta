"""
Modelo para tabla pedidos. CRUD + numeración automática.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import date
from PySide6.QtSql import QSqlQuery
from db.database import DatabaseManager


ESTADOS_PEDIDO = [
    'Presupuesto', 'Diseño', 'Aprobación Cliente',
    'En Taller', 'Listo para Entregar', 'Entregado',
    'Pendiente de Cobro', 'Cobrado', 'Cancelado'
]

# Color por estado (para badges)
ESTADO_COLORES: dict[str, tuple[str, str]] = {
    'Presupuesto':          ("#3a3a5c", "#a0a0d0"),
    'Diseño':               ("#1a3a4a", "#60b0e0"),
    'Aprobación Cliente':   ("#3a3a1a", "#e0d060"),
    'En Taller':            ("#1a2a4a", "#4080e0"),
    'Listo para Entregar':  ("#1a4a2a", "#40c060"),
    'Entregado':            ("#2a4a1a", "#80d040"),
    'Pendiente de Cobro':   ("#4a2a1a", "#e08040"),
    'Cobrado':              ("#1a4a1a", "#40e040"),
    'Cancelado':            ("#3a1a1a", "#e04040"),
}


@dataclass
class Pedido:
    id: int = 0
    nro_pedido: str = ""
    cliente_id: int = 0
    cliente_nombre: str = ""  # JOIN
    fecha_creacion: str = ""
    fecha_entrega: str = ""
    estado: str = "Presupuesto"
    subtotal: float = 0.0
    descuento: float = 0.0
    sena: float = 0.0
    total: float = 0.0
    saldo: float = 0.0
    observaciones: str = ""
    archivo_diseno_path: str = ""
    fecha_entregado_real: str = ""
    usuario_id: int = 0
    usuario_nombre: str = ""  # JOIN


class PedidoModel:
    """CRUD para tabla pedidos."""

    def generar_nro_pedido(self) -> str:
        """Genera próximo número de pedido en formato YYYY-XXXX."""
        anio = date.today().year
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT MAX(CAST(SUBSTR(nro_pedido, 6) AS INTEGER))
            FROM pedidos WHERE nro_pedido LIKE :patron
        """)
        query.bindValue(":patron", f"{anio}-%")
        query.exec()
        ultimo = 0
        if query.next() and query.value(0) is not None:
            ultimo = int(query.value(0) or 0)
        return f"{anio}-{(ultimo + 1):04d}"

    def get_all(self, filtros: Optional[dict] = None) -> list[Pedido]:
        """Retorna pedidos con JOIN a clientes. Acepta filtros opcionales."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)

        sql = """
            SELECT p.id, p.nro_pedido, p.cliente_id, c.nombre,
                   p.fecha_creacion, p.fecha_entrega, p.estado,
                   p.subtotal, p.descuento, p.sena, p.total, p.saldo,
                   p.observaciones, p.archivo_diseno_path, p.fecha_entregado_real,
                   COALESCE(p.usuario_id,0), COALESCE(u.nombre,'')
            FROM pedidos p
            LEFT JOIN clientes c ON p.cliente_id = c.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            WHERE 1=1
        """
        params = {}

        if filtros:
            if filtros.get("estados"):
                # Lista de estados (multi-select)
                placeholders = ",".join([f"'{e}'" for e in filtros["estados"]])
                sql += f" AND p.estado IN ({placeholders})"
            elif filtros.get("estado") and filtros["estado"] != "Todos":
                sql += " AND p.estado = :estado"
                params["estado"] = filtros["estado"]
            if filtros.get("cliente_id"):
                sql += " AND p.cliente_id = :cliente_id"
                params["cliente_id"] = filtros["cliente_id"]
            if filtros.get("desde"):
                sql += " AND p.fecha_creacion >= :desde"
                params["desde"] = filtros["desde"]
            if filtros.get("hasta"):
                sql += " AND p.fecha_creacion <= :hasta"
                params["hasta"] = filtros["hasta"]
            if filtros.get("buscar"):
                sql += " AND (p.nro_pedido LIKE :buscar OR c.nombre LIKE :buscar2)"
                params["buscar"] = f"%{filtros['buscar']}%"
                params["buscar2"] = f"%{filtros['buscar']}%"

        sql += " ORDER BY p.id DESC"
        query.prepare(sql)
        for k, v in params.items():
            query.bindValue(f":{k}", v)
        query.exec()

        pedidos = []
        while query.next():
            pedidos.append(self._row_to_pedido(query))
        return pedidos

    def get_by_id(self, pedido_id: int) -> Optional[Pedido]:
        """Retorna pedido por ID."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT p.id, p.nro_pedido, p.cliente_id, c.nombre,
                   p.fecha_creacion, p.fecha_entrega, p.estado,
                   p.subtotal, p.descuento, p.sena, p.total, p.saldo,
                   p.observaciones, p.archivo_diseno_path, p.fecha_entregado_real,
                   COALESCE(p.usuario_id,0), COALESCE(u.nombre,'')
            FROM pedidos p
            LEFT JOIN clientes c ON p.cliente_id = c.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            WHERE p.id = :id
        """)
        query.bindValue(":id", pedido_id)
        query.exec()
        if query.next():
            return self._row_to_pedido(query)
        return None

    def insertar(self, p: Pedido) -> int:
        """Inserta pedido y retorna ID generado."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO pedidos(nro_pedido, cliente_id, fecha_creacion, fecha_entrega,
                estado, descuento, sena, observaciones, archivo_diseno_path, usuario_id)
            VALUES(:nro, :cliente, :fcreacion, :fentrega,
                   :estado, :descuento, :sena, :obs, :archivo, :uid)
        """)
        query.bindValue(":nro", p.nro_pedido)
        query.bindValue(":cliente", p.cliente_id)
        query.bindValue(":fcreacion", p.fecha_creacion)
        query.bindValue(":fentrega", p.fecha_entrega or None)
        query.bindValue(":estado", p.estado)
        query.bindValue(":descuento", p.descuento)
        query.bindValue(":sena", p.sena)
        query.bindValue(":obs", p.observaciones)
        query.bindValue(":archivo", p.archivo_diseno_path or None)
        query.bindValue(":uid", p.usuario_id or None)
        if query.exec():
            return query.lastInsertId()
        print(f"Error insertar pedido: {query.lastError().text()}")
        return 0

    def actualizar(self, p: Pedido) -> bool:
        """Actualiza pedido existente."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)

        # Si pasa a Entregado, setear fecha_entregado_real si está vacía
        fecha_entregado = p.fecha_entregado_real
        if p.estado == "Entregado" and not fecha_entregado:
            fecha_entregado = date.today().isoformat()

        query.prepare("""
            UPDATE pedidos SET
                cliente_id=:cliente, fecha_creacion=:fcreacion,
                fecha_entrega=:fentrega, estado=:estado,
                descuento=:descuento, sena=:sena,
                observaciones=:obs, archivo_diseno_path=:archivo,
                fecha_entregado_real=:fentregado,
                total = subtotal - :descuento2,
                saldo = subtotal - :descuento3 - :sena2
                      - (SELECT COALESCE(SUM(monto),0) FROM pagos WHERE pedido_id=:id2)
            WHERE id=:id
        """)
        query.bindValue(":cliente", p.cliente_id)
        query.bindValue(":fcreacion", p.fecha_creacion)
        query.bindValue(":fentrega", p.fecha_entrega or None)
        query.bindValue(":estado", p.estado)
        query.bindValue(":descuento", p.descuento)
        query.bindValue(":descuento2", p.descuento)
        query.bindValue(":descuento3", p.descuento)
        query.bindValue(":sena", p.sena)
        query.bindValue(":sena2", p.sena)
        query.bindValue(":obs", p.observaciones)
        query.bindValue(":archivo", p.archivo_diseno_path or None)
        query.bindValue(":fentregado", fecha_entregado or None)
        query.bindValue(":id", p.id)
        query.bindValue(":id2", p.id)
        return query.exec()

    def cambiar_estado(self, pedido_id: int, nuevo_estado: str) -> bool:
        """Cambia solo el estado del pedido y registra en el log."""
        db = DatabaseManager.get_db()
        # Obtener estado anterior para el log
        estado_anterior = ""
        check_estado = QSqlQuery(db)
        check_estado.prepare("SELECT estado FROM pedidos WHERE id=:id")
        check_estado.bindValue(":id", pedido_id)
        check_estado.exec()
        if check_estado.next():
            estado_anterior = check_estado.value(0) or ""

        query = QSqlQuery(db)
        fecha_entregado = None
        if nuevo_estado == "Entregado":
            check = QSqlQuery(db)
            check.prepare("SELECT fecha_entregado_real FROM pedidos WHERE id=:id")
            check.bindValue(":id", pedido_id)
            check.exec()
            if check.next() and not check.value(0):
                fecha_entregado = date.today().isoformat()

        if fecha_entregado:
            query.prepare("UPDATE pedidos SET estado=:estado, fecha_entregado_real=:fecha WHERE id=:id")
            query.bindValue(":fecha", fecha_entregado)
        else:
            query.prepare("UPDATE pedidos SET estado=:estado WHERE id=:id")

        query.bindValue(":estado", nuevo_estado)
        query.bindValue(":id", pedido_id)
        ok = query.exec()
        if ok and estado_anterior != nuevo_estado:
            try:
                from models.pedido_log_model import PedidoLogModel
                PedidoLogModel().registrar_cambio_estado(pedido_id, estado_anterior, nuevo_estado)
            except Exception:
                pass
        return ok

    def get_stats_footer(self) -> dict:
        """Retorna stats para el footer de la tab pedidos."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.exec("""
            SELECT
                COUNT(*) as total,
                COALESCE(SUM(total),0) as facturado,
                COALESCE(SUM(CASE WHEN estado NOT IN ('Cobrado','Cancelado') THEN saldo ELSE 0 END),0) as pendiente
            FROM pedidos WHERE estado != 'Cancelado'
        """)
        if query.next():
            return {
                "total": query.value(0),
                "facturado": float(query.value(1) or 0),
                "pendiente": float(query.value(2) or 0),
            }
        return {"total": 0, "facturado": 0, "pendiente": 0}

    def get_por_estado(self, estados: list[str]) -> list[Pedido]:
        """Retorna pedidos filtrados por lista de estados (para Kanban)."""
        db = DatabaseManager.get_db()
        placeholders = ",".join([f"'{e}'" for e in estados])
        query = QSqlQuery(db)
        sql = f"""
            SELECT p.id, p.nro_pedido, p.cliente_id, c.nombre,
                   p.fecha_creacion, p.fecha_entrega, p.estado,
                   p.subtotal, p.descuento, p.sena, p.total, p.saldo,
                   p.observaciones, p.archivo_diseno_path, p.fecha_entregado_real,
                   COALESCE(p.usuario_id,0), COALESCE(u.nombre,'')
            FROM pedidos p
            LEFT JOIN clientes c ON p.cliente_id = c.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            WHERE p.estado IN ({placeholders})
            ORDER BY p.fecha_entrega ASC NULLS LAST
        """
        query.exec(sql)
        pedidos = []
        while query.next():
            pedidos.append(self._row_to_pedido(query))
        return pedidos

    @staticmethod
    def _row_to_pedido(query: QSqlQuery) -> "Pedido":
        """Convierte fila de query en dataclass Pedido."""
        return Pedido(
            id=query.value(0),
            nro_pedido=query.value(1) or "",
            cliente_id=query.value(2),
            cliente_nombre=query.value(3) or "",
            fecha_creacion=query.value(4) or "",
            fecha_entrega=query.value(5) or "",
            estado=query.value(6) or "Presupuesto",
            subtotal=float(query.value(7) or 0),
            descuento=float(query.value(8) or 0),
            sena=float(query.value(9) or 0),
            total=float(query.value(10) or 0),
            saldo=float(query.value(11) or 0),
            observaciones=query.value(12) or "",
            archivo_diseno_path=query.value(13) or "",
            fecha_entregado_real=query.value(14) or "",
            usuario_id=int(query.value(15) or 0),
            usuario_nombre=query.value(16) or "",
        )
