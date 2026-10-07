"""
Modelos para facturas electrónicas ARCA y recibos de pago.
"""
from dataclasses import dataclass
from typing import Optional
from PySide6.QtSql import QSqlQuery
from db.database import DatabaseManager


@dataclass
class Factura:
    id: int = 0
    pedido_id: Optional[int] = None
    pago_id: Optional[int] = None
    cliente_id: int = 0
    usuario_id: Optional[int] = None
    nro_factura: str = ""
    tipo_cbte: int = 6          # 6=B por defecto
    punto_venta: int = 1
    fecha_emision: str = ""
    cuit_receptor: str = ""
    razon_receptor: str = ""
    domicilio_receptor: str = ""
    importe_neto: float = 0.0
    importe_iva: float = 0.0
    importe_total: float = 0.0
    alicuota_iva: int = 5       # 5=21%
    concepto: int = 1
    moneda: str = "PES"
    cae: str = ""
    cae_vto: str = ""
    estado: str = "pendiente"
    email_enviado: bool = False
    observaciones: str = ""
    # JOIN
    cliente_nombre: str = ""
    nro_pedido: str = ""


@dataclass
class Recibo:
    id: int = 0
    pedido_id: Optional[int] = None
    pago_id: Optional[int] = None
    cliente_id: int = 0
    usuario_id: Optional[int] = None
    nro_recibo: str = ""
    fecha: str = ""
    monto: float = 0.0
    metodo: str = ""
    concepto: str = ""
    email_enviado: bool = False
    pdf_path: str = ""
    # JOIN
    cliente_nombre: str = ""
    nro_pedido: str = ""


class FacturaModel:
    """CRUD facturas electrónicas."""

    def generar_nro_recibo(self) -> str:
        """Genera próximo número de recibo: REC-YYYY-XXXX."""
        from datetime import date
        anio = date.today().year
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT MAX(CAST(SUBSTR(nro_recibo, 10) AS INTEGER))
            FROM recibos WHERE nro_recibo LIKE :p
        """)
        query.bindValue(":p", f"REC-{anio}-%")
        query.exec()
        ultimo = 0
        if query.next() and query.value(0) is not None:
            ultimo = int(query.value(0) or 0)
        return f"REC-{anio}-{(ultimo+1):04d}"

    def insertar(self, f: Factura) -> int:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO facturas(
                pedido_id, pago_id, cliente_id, usuario_id,
                nro_factura, tipo_cbte, punto_venta, fecha_emision,
                cuit_receptor, razon_receptor, domicilio_receptor,
                importe_neto, importe_iva, importe_total,
                alicuota_iva, concepto, moneda,
                cae, cae_vto, estado, observaciones
            ) VALUES(
                :pid,:pagoid,:cid,:uid,
                :nro,:tipo,:pv,:fecha,
                :cuit_r,:razon_r,:dom_r,
                :neto,:iva,:total,
                :alic,:conc,:mon,
                :cae,:caevto,:estado,:obs
            )
        """)
        for k, v in {
            ":pid": f.pedido_id, ":pagoid": f.pago_id, ":cid": f.cliente_id,
            ":uid": f.usuario_id, ":nro": f.nro_factura, ":tipo": f.tipo_cbte,
            ":pv": f.punto_venta, ":fecha": f.fecha_emision,
            ":cuit_r": f.cuit_receptor, ":razon_r": f.razon_receptor,
            ":dom_r": f.domicilio_receptor, ":neto": f.importe_neto,
            ":iva": f.importe_iva, ":total": f.importe_total,
            ":alic": f.alicuota_iva, ":conc": f.concepto,
            ":mon": f.moneda, ":cae": f.cae, ":caevto": f.cae_vto,
            ":estado": f.estado, ":obs": f.observaciones,
        }.items():
            query.bindValue(k, v)
        if query.exec():
            return query.lastInsertId()
        print(f"Error insertar factura: {query.lastError().text()}")
        return 0

    def actualizar_cae(self, factura_id: int, nro: str, cae: str,
                       cae_vto: str, estado: str) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            UPDATE facturas SET nro_factura=:nro, cae=:cae,
            cae_vto=:vto, estado=:estado WHERE id=:id
        """)
        query.bindValue(":nro", nro)
        query.bindValue(":cae", cae)
        query.bindValue(":vto", cae_vto)
        query.bindValue(":estado", estado)
        query.bindValue(":id", factura_id)
        return query.exec()

    def marcar_email_enviado(self, factura_id: int) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("UPDATE facturas SET email_enviado=1 WHERE id=:id")
        query.bindValue(":id", factura_id)
        return query.exec()

    def get_by_pedido(self, pedido_id: int) -> list[Factura]:
        return self._query_facturas("WHERE f.pedido_id = :v", pedido_id)

    def get_all_facturas(self, limit: int = 200) -> list["Factura"]:
        """Retorna todas las facturas (sin filtro de cliente), máximo limit."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        sql = f"""
            SELECT f.id, f.pedido_id, f.pago_id, f.cliente_id, f.usuario_id,
                   f.nro_factura, f.tipo_cbte, f.punto_venta, f.fecha_emision,
                   f.cuit_receptor, f.razon_receptor, f.domicilio_receptor,
                   f.importe_neto, f.importe_iva, f.importe_total,
                   f.alicuota_iva, f.concepto, f.moneda,
                   f.cae, f.cae_vto, f.estado, f.email_enviado, f.observaciones,
                   c.nombre, COALESCE(p.nro_pedido,'')
            FROM facturas f
            LEFT JOIN clientes c ON f.cliente_id = c.id
            LEFT JOIN pedidos p ON f.pedido_id = p.id
            ORDER BY f.id DESC LIMIT {limit}
        """
        query.exec(sql)
        result = []
        while query.next():
            result.append(Factura(
                id=query.value(0), pedido_id=query.value(1),
                pago_id=query.value(2), cliente_id=query.value(3),
                usuario_id=query.value(4), nro_factura=query.value(5) or "",
                tipo_cbte=int(query.value(6) or 6),
                punto_venta=int(query.value(7) or 1),
                fecha_emision=query.value(8) or "",
                cuit_receptor=query.value(9) or "",
                razon_receptor=query.value(10) or "",
                domicilio_receptor=query.value(11) or "",
                importe_neto=float(query.value(12) or 0),
                importe_iva=float(query.value(13) or 0),
                importe_total=float(query.value(14) or 0),
                alicuota_iva=int(query.value(15) or 5),
                concepto=int(query.value(16) or 1),
                moneda=query.value(17) or "PES",
                cae=query.value(18) or "",
                cae_vto=query.value(19) or "",
                estado=query.value(20) or "pendiente",
                email_enviado=bool(query.value(21)),
                observaciones=query.value(22) or "",
                cliente_nombre=query.value(23) or "",
                nro_pedido=query.value(24) or "",
            ))
        return result

    def get_by_cliente(self, cliente_id: int) -> list[Factura]:
        return self._query_facturas("WHERE f.cliente_id = :v", cliente_id)

    def get_by_id(self, factura_id: int) -> Optional[Factura]:
        rows = self._query_facturas("WHERE f.id = :v", factura_id)
        return rows[0] if rows else None

    def _query_facturas(self, where: str, param) -> list[Factura]:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        sql = f"""
            SELECT f.id, f.pedido_id, f.pago_id, f.cliente_id, f.usuario_id,
                   f.nro_factura, f.tipo_cbte, f.punto_venta, f.fecha_emision,
                   f.cuit_receptor, f.razon_receptor, f.domicilio_receptor,
                   f.importe_neto, f.importe_iva, f.importe_total,
                   f.alicuota_iva, f.concepto, f.moneda,
                   f.cae, f.cae_vto, f.estado, f.email_enviado, f.observaciones,
                   c.nombre, COALESCE(p.nro_pedido,'')
            FROM facturas f
            LEFT JOIN clientes c ON f.cliente_id = c.id
            LEFT JOIN pedidos p ON f.pedido_id = p.id
            {where}
            ORDER BY f.id DESC
        """
        query.prepare(sql)
        query.bindValue(":v", param)
        query.exec()
        result = []
        while query.next():
            result.append(Factura(
                id=query.value(0), pedido_id=query.value(1),
                pago_id=query.value(2), cliente_id=query.value(3),
                usuario_id=query.value(4), nro_factura=query.value(5) or "",
                tipo_cbte=int(query.value(6) or 6),
                punto_venta=int(query.value(7) or 1),
                fecha_emision=query.value(8) or "",
                cuit_receptor=query.value(9) or "",
                razon_receptor=query.value(10) or "",
                domicilio_receptor=query.value(11) or "",
                importe_neto=float(query.value(12) or 0),
                importe_iva=float(query.value(13) or 0),
                importe_total=float(query.value(14) or 0),
                alicuota_iva=int(query.value(15) or 5),
                concepto=int(query.value(16) or 1),
                moneda=query.value(17) or "PES",
                cae=query.value(18) or "",
                cae_vto=query.value(19) or "",
                estado=query.value(20) or "pendiente",
                email_enviado=bool(query.value(21)),
                observaciones=query.value(22) or "",
                cliente_nombre=query.value(23) or "",
                nro_pedido=query.value(24) or "",
            ))
        return result


class ReciboModel:
    """CRUD recibos de pago."""

    def generar_nro(self) -> str:
        from datetime import date
        anio = date.today().year
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT MAX(CAST(SUBSTR(nro_recibo, 10) AS INTEGER))
            FROM recibos WHERE nro_recibo LIKE :p
        """)
        query.bindValue(":p", f"REC-{anio}-%")
        query.exec()
        ultimo = 0
        if query.next() and query.value(0) is not None:
            ultimo = int(query.value(0) or 0)
        return f"REC-{anio}-{(ultimo+1):04d}"

    def insertar(self, r: Recibo) -> int:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO recibos(
                pedido_id, pago_id, cliente_id, usuario_id,
                nro_recibo, fecha, monto, metodo, concepto, pdf_path
            ) VALUES(:pid,:pagoid,:cid,:uid,:nro,:f,:m,:met,:conc,:pdf)
        """)
        for k, v in {
            ":pid": r.pedido_id, ":pagoid": r.pago_id, ":cid": r.cliente_id,
            ":uid": r.usuario_id, ":nro": r.nro_recibo, ":f": r.fecha,
            ":m": r.monto, ":met": r.metodo, ":conc": r.concepto,
            ":pdf": r.pdf_path,
        }.items():
            query.bindValue(k, v)
        if query.exec():
            return query.lastInsertId()
        return 0

    def marcar_email(self, recibo_id: int) -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("UPDATE recibos SET email_enviado=1 WHERE id=:id")
        query.bindValue(":id", recibo_id)
        return query.exec()

    def get_by_pedido(self, pedido_id: int) -> list[Recibo]:
        return self._query("WHERE r.pedido_id=:v", pedido_id)

    def get_all_recibos(self, limit: int = 200) -> list["Recibo"]:
        """Retorna todos los recibos sin filtro."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.exec(f"""
            SELECT r.id, r.pedido_id, r.pago_id, r.cliente_id, r.usuario_id,
                   r.nro_recibo, r.fecha, r.monto, r.metodo, r.concepto,
                   r.email_enviado, r.pdf_path,
                   c.nombre, COALESCE(p.nro_pedido,'')
            FROM recibos r
            LEFT JOIN clientes c ON r.cliente_id = c.id
            LEFT JOIN pedidos p ON r.pedido_id = p.id
            ORDER BY r.id DESC LIMIT {limit}
        """)
        result = []
        while query.next():
            result.append(Recibo(
                id=query.value(0), pedido_id=query.value(1),
                pago_id=query.value(2), cliente_id=query.value(3),
                usuario_id=query.value(4), nro_recibo=query.value(5) or "",
                fecha=query.value(6) or "", monto=float(query.value(7) or 0),
                metodo=query.value(8) or "", concepto=query.value(9) or "",
                email_enviado=bool(query.value(10)),
                pdf_path=query.value(11) or "",
                cliente_nombre=query.value(12) or "",
                nro_pedido=query.value(13) or "",
            ))
        return result

    def get_by_cliente(self, cliente_id: int) -> list[Recibo]:
        return self._query("WHERE r.cliente_id=:v", cliente_id)

    def _query(self, where: str, param) -> list[Recibo]:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        sql = f"""
            SELECT r.id, r.pedido_id, r.pago_id, r.cliente_id, r.usuario_id,
                   r.nro_recibo, r.fecha, r.monto, r.metodo, r.concepto,
                   r.email_enviado, r.pdf_path,
                   c.nombre, COALESCE(p.nro_pedido,'')
            FROM recibos r
            LEFT JOIN clientes c ON r.cliente_id = c.id
            LEFT JOIN pedidos p ON r.pedido_id = p.id
            {where} ORDER BY r.id DESC
        """
        query.prepare(sql)
        query.bindValue(":v", param)
        query.exec()
        result = []
        while query.next():
            result.append(Recibo(
                id=query.value(0), pedido_id=query.value(1),
                pago_id=query.value(2), cliente_id=query.value(3),
                usuario_id=query.value(4), nro_recibo=query.value(5) or "",
                fecha=query.value(6) or "", monto=float(query.value(7) or 0),
                metodo=query.value(8) or "", concepto=query.value(9) or "",
                email_enviado=bool(query.value(10)),
                pdf_path=query.value(11) or "",
                cliente_nombre=query.value(12) or "",
                nro_pedido=query.value(13) or "",
            ))
        return result
