"""
Modelos: PedidoDetalle, Producto, TipoTrabajo, Pago, Insumo.
"""
from dataclasses import dataclass
from typing import Optional
from PySide6.QtSql import QSqlQuery
from db.database import DatabaseManager


# ─── PEDIDO DETALLE ────────────────────────────────────────────────────────────

@dataclass
class PedidoDetalle:
    id: int = 0
    pedido_id: int = 0
    producto_id: Optional[int] = None
    producto_nombre: str = ""
    descripcion: str = ""
    cantidad: int = 1
    ancho: float = 0.0
    alto: float = 0.0
    precio_unitario: float = 0.0
    subtotal: float = 0.0


class PedidoDetalleModel:
    """CRUD para pedidos_detalle."""

    def get_by_pedido(self, pedido_id: int) -> list[PedidoDetalle]:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT pd.id, pd.pedido_id, pd.producto_id, COALESCE(p.nombre,''),
                   pd.descripcion, pd.cantidad, pd.ancho, pd.alto,
                   pd.precio_unitario, pd.subtotal
            FROM pedidos_detalle pd
            LEFT JOIN productos p ON pd.producto_id = p.id
            WHERE pd.pedido_id = :pid
            ORDER BY pd.id
        """)
        query.bindValue(":pid", pedido_id)
        query.exec()
        items = []
        while query.next():
            items.append(PedidoDetalle(
                id=query.value(0),
                pedido_id=query.value(1),
                producto_id=query.value(2),
                producto_nombre=query.value(3),
                descripcion=query.value(4) or "",
                cantidad=int(query.value(5) or 1),
                ancho=float(query.value(6) or 0),
                alto=float(query.value(7) or 0),
                precio_unitario=float(query.value(8) or 0),
                subtotal=float(query.value(9) or 0),
            ))
        return items

    def insertar(self, d: PedidoDetalle) -> int:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO pedidos_detalle
                (pedido_id, producto_id, descripcion, cantidad, ancho, alto, precio_unitario, subtotal)
            VALUES(:pid, :prod, :desc, :cant, :ancho, :alto, :precio, :sub)
        """)
        query.bindValue(":pid", d.pedido_id)
        query.bindValue(":prod", d.producto_id)
        query.bindValue(":desc", d.descripcion)
        query.bindValue(":cant", d.cantidad)
        query.bindValue(":ancho", d.ancho)
        query.bindValue(":alto", d.alto)
        query.bindValue(":precio", d.precio_unitario)
        query.bindValue(":sub", d.subtotal)
        if query.exec():
            return query.lastInsertId()
        return 0

    def actualizar(self, d: PedidoDetalle) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            UPDATE pedidos_detalle SET
                producto_id=:prod, descripcion=:desc, cantidad=:cant,
                ancho=:ancho, alto=:alto, precio_unitario=:precio, subtotal=:sub
            WHERE id=:id
        """)
        query.bindValue(":prod", d.producto_id)
        query.bindValue(":desc", d.descripcion)
        query.bindValue(":cant", d.cantidad)
        query.bindValue(":ancho", d.ancho)
        query.bindValue(":alto", d.alto)
        query.bindValue(":precio", d.precio_unitario)
        query.bindValue(":sub", d.subtotal)
        query.bindValue(":id", d.id)
        return query.exec()

    def eliminar(self, detalle_id: int) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("DELETE FROM pedidos_detalle WHERE id=:id")
        query.bindValue(":id", detalle_id)
        return query.exec()

    def eliminar_por_pedido(self, pedido_id: int) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("DELETE FROM pedidos_detalle WHERE pedido_id=:pid")
        query.bindValue(":pid", pedido_id)
        return query.exec()


# ─── TIPO TRABAJO ──────────────────────────────────────────────────────────────

@dataclass
class TipoTrabajo:
    id: int = 0
    nombre: str = ""
    descripcion: str = ""


class TipoTrabajoModel:
    def get_all(self) -> list[TipoTrabajo]:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.exec("SELECT id, nombre, descripcion FROM tipos_trabajo ORDER BY nombre")
        items = []
        while query.next():
            items.append(TipoTrabajo(
                id=query.value(0),
                nombre=query.value(1) or "",
                descripcion=query.value(2) or "",
            ))
        return items

    def insertar(self, t: TipoTrabajo) -> int:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("INSERT INTO tipos_trabajo(nombre, descripcion) VALUES(:n, :d)")
        query.bindValue(":n", t.nombre)
        query.bindValue(":d", t.descripcion)
        if query.exec():
            return query.lastInsertId()
        return 0

    def actualizar(self, t: TipoTrabajo) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("UPDATE tipos_trabajo SET nombre=:n, descripcion=:d WHERE id=:id")
        query.bindValue(":n", t.nombre)
        query.bindValue(":d", t.descripcion)
        query.bindValue(":id", t.id)
        return query.exec()

    def eliminar(self, tipo_id: int) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("DELETE FROM tipos_trabajo WHERE id=:id")
        query.bindValue(":id", tipo_id)
        return query.exec()


# ─── PRODUCTO ──────────────────────────────────────────────────────────────────

@dataclass
class Producto:
    id: int = 0
    nombre: str = ""
    tipo_trabajo_id: Optional[int] = None
    tipo_nombre: str = ""
    unidad: str = "unidad"
    precio_base: float = 0.0
    activo: bool = True


class ProductoModel:
    def get_all(self, solo_activos: bool = True) -> list[Producto]:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        sql = """
            SELECT p.id, p.nombre, p.tipo_trabajo_id, COALESCE(t.nombre,''),
                   p.unidad, p.precio_base, p.activo
            FROM productos p
            LEFT JOIN tipos_trabajo t ON p.tipo_trabajo_id = t.id
        """
        if solo_activos:
            sql += " WHERE p.activo = 1"
        sql += " ORDER BY p.nombre COLLATE NOCASE"
        query.exec(sql)
        items = []
        while query.next():
            items.append(Producto(
                id=query.value(0),
                nombre=query.value(1) or "",
                tipo_trabajo_id=query.value(2),
                tipo_nombre=query.value(3),
                unidad=query.value(4) or "unidad",
                precio_base=float(query.value(5) or 0),
                activo=bool(query.value(6)),
            ))
        return items

    def get_by_id(self, prod_id: int) -> Optional[Producto]:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT p.id, p.nombre, p.tipo_trabajo_id, COALESCE(t.nombre,''),
                   p.unidad, p.precio_base, p.activo
            FROM productos p
            LEFT JOIN tipos_trabajo t ON p.tipo_trabajo_id = t.id
            WHERE p.id=:id
        """)
        query.bindValue(":id", prod_id)
        query.exec()
        if query.next():
            return Producto(
                id=query.value(0), nombre=query.value(1) or "",
                tipo_trabajo_id=query.value(2), tipo_nombre=query.value(3),
                unidad=query.value(4) or "unidad",
                precio_base=float(query.value(5) or 0),
                activo=bool(query.value(6)),
            )
        return None

    def insertar(self, p: Producto) -> int:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO productos(nombre, tipo_trabajo_id, unidad, precio_base, activo)
            VALUES(:n, :t, :u, :p, :a)
        """)
        query.bindValue(":n", p.nombre)
        query.bindValue(":t", p.tipo_trabajo_id)
        query.bindValue(":u", p.unidad)
        query.bindValue(":p", p.precio_base)
        query.bindValue(":a", 1 if p.activo else 0)
        if query.exec():
            return query.lastInsertId()
        return 0

    def actualizar(self, p: Producto) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            UPDATE productos SET nombre=:n, tipo_trabajo_id=:t,
            unidad=:u, precio_base=:p, activo=:a WHERE id=:id
        """)
        query.bindValue(":n", p.nombre)
        query.bindValue(":t", p.tipo_trabajo_id)
        query.bindValue(":u", p.unidad)
        query.bindValue(":p", p.precio_base)
        query.bindValue(":a", 1 if p.activo else 0)
        query.bindValue(":id", p.id)
        return query.exec()

    def eliminar_logico(self, prod_id: int) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("UPDATE productos SET activo=0 WHERE id=:id")
        query.bindValue(":id", prod_id)
        return query.exec()


# ─── PAGO ──────────────────────────────────────────────────────────────────────

@dataclass
class Pago:
    id: int = 0
    pedido_id: int = 0
    fecha: str = ""
    monto: float = 0.0
    metodo: str = "Efectivo"
    comprobante: str = ""
    nro_factura: str = ""


class PagoModel:
    def get_by_pedido(self, pedido_id: int) -> list[Pago]:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT id, pedido_id, fecha, monto, metodo, comprobante, nro_factura
            FROM pagos WHERE pedido_id=:pid ORDER BY fecha DESC
        """)
        query.bindValue(":pid", pedido_id)
        query.exec()
        pagos = []
        while query.next():
            pagos.append(Pago(
                id=query.value(0), pedido_id=query.value(1),
                fecha=query.value(2) or "", monto=float(query.value(3) or 0),
                metodo=query.value(4) or "Efectivo",
                comprobante=query.value(5) or "",
                nro_factura=query.value(6) or "",
            ))
        return pagos

    def insertar(self, p: Pago) -> int:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO pagos(pedido_id, fecha, monto, metodo, comprobante, nro_factura)
            VALUES(:pid, :f, :m, :met, :comp, :nro)
        """)
        query.bindValue(":pid", p.pedido_id)
        query.bindValue(":f", p.fecha)
        query.bindValue(":m", p.monto)
        query.bindValue(":met", p.metodo)
        query.bindValue(":comp", p.comprobante)
        query.bindValue(":nro", p.nro_factura)
        if query.exec():
            return query.lastInsertId()
        return 0

    def eliminar(self, pago_id: int) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("DELETE FROM pagos WHERE id=:id")
        query.bindValue(":id", pago_id)
        return query.exec()

    def get_total_pagado(self, pedido_id: int) -> float:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE pedido_id=:pid")
        query.bindValue(":pid", pedido_id)
        query.exec()
        if query.next():
            return float(query.value(0) or 0)
        return 0.0


# ─── INSUMO ────────────────────────────────────────────────────────────────────

@dataclass
class Insumo:
    id: int = 0
    nombre: str = ""
    costo_unitario: float = 0.0
    stock_actual: float = 0.0


class InsumoModel:
    def get_all(self) -> list[Insumo]:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.exec("SELECT id, nombre, costo_unitario, stock_actual FROM insumos ORDER BY nombre")
        items = []
        while query.next():
            items.append(Insumo(
                id=query.value(0), nombre=query.value(1) or "",
                costo_unitario=float(query.value(2) or 0),
                stock_actual=float(query.value(3) or 0),
            ))
        return items

    def insertar(self, i: Insumo) -> int:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("INSERT INTO insumos(nombre, costo_unitario, stock_actual) VALUES(:n,:c,:s)")
        query.bindValue(":n", i.nombre)
        query.bindValue(":c", i.costo_unitario)
        query.bindValue(":s", i.stock_actual)
        if query.exec():
            return query.lastInsertId()
        return 0

    def actualizar(self, i: Insumo) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("UPDATE insumos SET nombre=:n, costo_unitario=:c, stock_actual=:s WHERE id=:id")
        query.bindValue(":n", i.nombre)
        query.bindValue(":c", i.costo_unitario)
        query.bindValue(":s", i.stock_actual)
        query.bindValue(":id", i.id)
        return query.exec()

    def eliminar(self, insumo_id: int) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("DELETE FROM insumos WHERE id=:id")
        query.bindValue(":id", insumo_id)
        return query.exec()
