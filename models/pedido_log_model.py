"""
models/pedido_log_model.py
──────────────────────────
Log de auditoría de pedidos: cambios de estado, emails, modificaciones.
"""
from dataclasses import dataclass
from PySide6.QtSql import QSqlQuery
from db.database import DatabaseManager
from models.usuario_model import UsuarioModel


@dataclass
class PedidoLogEntry:
    id: int = 0
    pedido_id: int = 0
    fecha: str = ""
    usuario: str = ""
    tipo: str = "cambio"       # cambio_estado | email | modificacion | pago | factura | recibo
    descripcion: str = ""


class PedidoLogModel:
    """CRUD para tabla pedido_log."""

    def registrar(self, pedido_id: int, tipo: str, descripcion: str,
                  usuario: str = "") -> bool:
        """Inserta una entrada de log."""
        db = DatabaseManager.get_db()
        if not db.isOpen():
            return False
        if not usuario:
            u = UsuarioModel.usuario_actual()
            usuario = u.nombre if u else "Sistema"
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO pedido_log(pedido_id, usuario, tipo, descripcion)
            VALUES(:pid, :usr, :tipo, :desc)
        """)
        query.bindValue(":pid",  pedido_id)
        query.bindValue(":usr",  usuario)
        query.bindValue(":tipo", tipo)
        query.bindValue(":desc", descripcion)
        return query.exec()

    def registrar_cambio_estado(self, pedido_id: int,
                                 estado_anterior: str, estado_nuevo: str) -> bool:
        desc = f"Estado: '{estado_anterior}' → '{estado_nuevo}'"
        return self.registrar(pedido_id, "cambio_estado", desc)

    def registrar_modificacion(self, pedido_id: int, detalle: str = "") -> bool:
        desc = f"Pedido modificado{f': {detalle}' if detalle else '.'}"
        return self.registrar(pedido_id, "modificacion", desc)

    def registrar_email(self, pedido_id: int, destinatario: str, asunto: str) -> bool:
        desc = f"Email enviado a {destinatario} — Asunto: {asunto}"
        return self.registrar(pedido_id, "email", desc)

    def registrar_pago(self, pedido_id: int, monto: float, metodo: str) -> bool:
        from utils.helpers import fmt_moneda
        desc = f"Pago registrado: {fmt_moneda(monto)} ({metodo})"
        return self.registrar(pedido_id, "pago", desc)

    def registrar_factura(self, pedido_id: int, nro_factura: str, cae: str = "") -> bool:
        desc = f"Factura electrónica emitida N° {nro_factura}"
        if cae:
            desc += f" — CAE: {cae}"
        return self.registrar(pedido_id, "factura", desc)

    def registrar_recibo(self, pedido_id: int, nro_recibo: str, monto: float) -> bool:
        from utils.helpers import fmt_moneda
        desc = f"Recibo emitido N° {nro_recibo} — {fmt_moneda(monto)}"
        return self.registrar(pedido_id, "recibo", desc)

    def get_by_pedido(self, pedido_id: int) -> list[PedidoLogEntry]:
        """Retorna historial completo de un pedido, más reciente primero."""
        db = DatabaseManager.get_db()
        if not db.isOpen():
            return []
        query = QSqlQuery(db)
        query.prepare("""
            SELECT id, pedido_id, fecha, usuario, tipo, descripcion
            FROM pedido_log
            WHERE pedido_id = :pid
            ORDER BY id DESC
        """)
        query.bindValue(":pid", pedido_id)
        query.exec()
        entries = []
        while query.next():
            entries.append(PedidoLogEntry(
                id=query.value(0),
                pedido_id=query.value(1),
                fecha=query.value(2) or "",
                usuario=query.value(3) or "",
                tipo=query.value(4) or "cambio",
                descripcion=query.value(5) or "",
            ))
        return entries
