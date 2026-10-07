"""
Modelo para tabla clientes. CRUD completo.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from PySide6.QtSql import QSqlQuery
from db.database import DatabaseManager


@dataclass
class Cliente:
    id: int = 0
    nombre: str = ""
    telefono: str = ""
    whatsapp: str = ""
    email: str = ""
    cuit: str = ""
    direccion: str = ""
    notas: str = ""
    fecha_alta: str = ""
    activo: bool = True


class ClienteModel:
    """CRUD para tabla clientes."""

    def get_all(self, solo_activos: bool = True) -> list[Cliente]:
        """Retorna lista de clientes."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        sql = "SELECT id,nombre,telefono,whatsapp,email,cuit,direccion,notas,fecha_alta,activo FROM clientes"
        if solo_activos:
            sql += " WHERE activo = 1"
        sql += " ORDER BY nombre COLLATE NOCASE"
        query.exec(sql)
        clientes = []
        while query.next():
            clientes.append(Cliente(
                id=query.value(0),
                nombre=query.value(1) or "",
                telefono=query.value(2) or "",
                whatsapp=query.value(3) or "",
                email=query.value(4) or "",
                cuit=query.value(5) or "",
                direccion=query.value(6) or "",
                notas=query.value(7) or "",
                fecha_alta=query.value(8) or "",
                activo=bool(query.value(9)),
            ))
        return clientes

    def get_by_id(self, cliente_id: int) -> Optional[Cliente]:
        """Retorna cliente por ID."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT id,nombre,telefono,whatsapp,email,cuit,direccion,notas,fecha_alta,activo
            FROM clientes WHERE id = :id
        """)
        query.bindValue(":id", cliente_id)
        query.exec()
        if query.next():
            return Cliente(
                id=query.value(0),
                nombre=query.value(1) or "",
                telefono=query.value(2) or "",
                whatsapp=query.value(3) or "",
                email=query.value(4) or "",
                cuit=query.value(5) or "",
                direccion=query.value(6) or "",
                notas=query.value(7) or "",
                fecha_alta=query.value(8) or "",
                activo=bool(query.value(9)),
            )
        return None

    def insertar(self, c: Cliente) -> int:
        """Inserta cliente y retorna ID generado."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO clientes(nombre,telefono,whatsapp,email,cuit,direccion,notas,activo)
            VALUES(:nombre,:telefono,:whatsapp,:email,:cuit,:direccion,:notas,:activo)
        """)
        query.bindValue(":nombre", c.nombre)
        query.bindValue(":telefono", c.telefono)
        query.bindValue(":whatsapp", c.whatsapp)
        query.bindValue(":email", c.email)
        query.bindValue(":cuit", c.cuit)
        query.bindValue(":direccion", c.direccion)
        query.bindValue(":notas", c.notas)
        query.bindValue(":activo", 1 if c.activo else 0)
        if query.exec():
            return query.lastInsertId()
        return 0

    def actualizar(self, c: Cliente) -> bool:
        """Actualiza cliente existente."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            UPDATE clientes SET
                nombre=:nombre, telefono=:telefono, whatsapp=:whatsapp,
                email=:email, cuit=:cuit, direccion=:direccion,
                notas=:notas, activo=:activo
            WHERE id=:id
        """)
        query.bindValue(":nombre", c.nombre)
        query.bindValue(":telefono", c.telefono)
        query.bindValue(":whatsapp", c.whatsapp)
        query.bindValue(":email", c.email)
        query.bindValue(":cuit", c.cuit)
        query.bindValue(":direccion", c.direccion)
        query.bindValue(":notas", c.notas)
        query.bindValue(":activo", 1 if c.activo else 0)
        query.bindValue(":id", c.id)
        return query.exec()

    def eliminar_logico(self, cliente_id: int) -> bool:
        """Baja lógica (activo=0)."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("UPDATE clientes SET activo=0 WHERE id=:id")
        query.bindValue(":id", cliente_id)
        return query.exec()

    def get_nombres_para_completer(self) -> list[str]:
        """Retorna lista de nombres para QCompleter."""
        return [c.nombre for c in self.get_all()]

    def get_saldo_total(self, cliente_id: int) -> float:
        """Retorna suma de saldos pendientes del cliente."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT COALESCE(SUM(saldo),0) FROM pedidos
            WHERE cliente_id=:id AND estado NOT IN ('Cancelado','Cobrado')
        """)
        query.bindValue(":id", cliente_id)
        query.exec()
        if query.next():
            return float(query.value(0) or 0)
        return 0.0
