"""
Queries para reportes: ventas del mes, balance, productos más vendidos.
"""
from datetime import date
from PySide6.QtSql import QSqlQuery
from db.database import DatabaseManager


class ReporteController:
    """Provee datos para los reportes."""

    def ventas_por_dia_mes(self, anio: int, mes: int) -> list[dict]:
        """
        Retorna lista de {'dia': int, 'total': float} para el mes dado.
        Basado en pedidos con estado != Cancelado.
        """
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT
                CAST(SUBSTR(fecha_creacion, 9, 2) AS INTEGER) as dia,
                COALESCE(SUM(total), 0) as total
            FROM pedidos
            WHERE
                SUBSTR(fecha_creacion, 1, 4) = :anio
                AND SUBSTR(fecha_creacion, 6, 2) = :mes
                AND estado != 'Cancelado'
            GROUP BY dia
            ORDER BY dia
        """)
        query.bindValue(":anio", str(anio))
        query.bindValue(":mes", f"{mes:02d}")
        query.exec()

        resultados = []
        while query.next():
            resultados.append({
                "dia": int(query.value(0) or 0),
                "total": float(query.value(1) or 0),
            })
        return resultados

    def balance_general(self) -> dict:
        """Retorna totales históricos."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.exec("""
            SELECT
                COALESCE(SUM(CASE WHEN estado != 'Cancelado' THEN total ELSE 0 END), 0)   as facturado,
                COALESCE(SUM(CASE WHEN estado = 'Cobrado' THEN total ELSE 0 END), 0)       as cobrado,
                COALESCE(SUM(CASE WHEN estado NOT IN ('Cobrado','Cancelado') THEN saldo ELSE 0 END), 0) as pendiente,
                COALESCE(SUM(CASE WHEN estado != 'Cancelado' THEN sena ELSE 0 END), 0)     as senas
            FROM pedidos
        """)
        if query.next():
            return {
                "facturado":  float(query.value(0) or 0),
                "cobrado":    float(query.value(1) or 0),
                "pendiente":  float(query.value(2) or 0),
                "senas":      float(query.value(3) or 0),
            }
        return {"facturado": 0, "cobrado": 0, "pendiente": 0, "senas": 0}

    def productos_mas_vendidos(self, anio: int, mes: int) -> list[dict]:
        """Retorna top productos del mes por cantidad vendida."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT
                COALESCE(pr.nombre, pd.descripcion) as producto,
                SUM(pd.cantidad) as cantidad,
                SUM(pd.subtotal) as facturado
            FROM pedidos_detalle pd
            LEFT JOIN productos pr ON pd.producto_id = pr.id
            JOIN pedidos p ON pd.pedido_id = p.id
            WHERE
                SUBSTR(p.fecha_creacion, 1, 4) = :anio
                AND SUBSTR(p.fecha_creacion, 6, 2) = :mes
                AND p.estado != 'Cancelado'
            GROUP BY COALESCE(pd.producto_id, pd.descripcion)
            ORDER BY cantidad DESC
            LIMIT 20
        """)
        query.bindValue(":anio", str(anio))
        query.bindValue(":mes", f"{mes:02d}")
        query.exec()

        resultados = []
        while query.next():
            resultados.append({
                "producto":   query.value(0) or "",
                "cantidad":   int(query.value(1) or 0),
                "facturado":  float(query.value(2) or 0),
            })
        return resultados

    def pedidos_cuenta_corriente(self, cliente_id: int) -> list[dict]:
        """Retorna pedidos para cuenta corriente. cliente_id=0 retorna todos."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        if cliente_id:
            query.prepare("""
                SELECT p.id, p.nro_pedido, p.fecha_creacion, p.estado,
                       p.total, p.sena, p.saldo,
                       COALESCE((SELECT SUM(monto) FROM pagos WHERE pedido_id=p.id),0) as pagado,
                       c.nombre, p.cliente_id
                FROM pedidos p
                LEFT JOIN clientes c ON p.cliente_id = c.id
                WHERE p.cliente_id = :cid AND p.estado NOT IN ('Cancelado')
                ORDER BY p.fecha_creacion DESC
            """)
            query.bindValue(":cid", cliente_id)
        else:
            query.prepare("""
                SELECT p.id, p.nro_pedido, p.fecha_creacion, p.estado,
                       p.total, p.sena, p.saldo,
                       COALESCE((SELECT SUM(monto) FROM pagos WHERE pedido_id=p.id),0) as pagado,
                       c.nombre, p.cliente_id
                FROM pedidos p
                LEFT JOIN clientes c ON p.cliente_id = c.id
                WHERE p.estado NOT IN ('Cancelado')
                ORDER BY p.fecha_creacion DESC
                LIMIT 200
            """)
        query.exec()
        filas = []
        while query.next():
            filas.append({
                "id":            query.value(0),
                "nro":           query.value(1) or "",
                "fecha":         query.value(2) or "",
                "estado":        query.value(3) or "",
                "total":         float(query.value(4) or 0),
                "sena":          float(query.value(5) or 0),
                "saldo":         float(query.value(6) or 0),
                "pagado":        float(query.value(7) or 0),
                "cliente_nombre": query.value(8) or "",
                "cliente_id":    int(query.value(9) or 0),
            })
        return filas
