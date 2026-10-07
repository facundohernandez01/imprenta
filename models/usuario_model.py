"""
Modelo de usuarios. Autenticación con hash SHA256 + sal.
"""
import hashlib
import secrets
from dataclasses import dataclass
from typing import Optional
from PySide6.QtSql import QSqlQuery
from db.database import DatabaseManager


@dataclass
class Usuario:
    id: int = 0
    username: str = ""
    nombre: str = ""
    password_hash: str = ""
    rol: str = "operador"
    activo: bool = True
    recordar: bool = False
    ultimo_login: str = ""


def _hash_password(password: str) -> str:
    """Genera hash SHA256 con sal."""
    sal = secrets.token_hex(16)
    h = hashlib.sha256(f"{sal}{password}".encode()).hexdigest()
    return f"sha256:{sal}:{h}"


def _verificar_password(password: str, stored: str) -> bool:
    """Verifica contraseña contra hash almacenado."""
    # Compatibilidad con hash simple inicial
    if stored == "pbkdf2:sha256:admin123" and password == "admin123":
        return True
    try:
        _, sal, h = stored.split(":")
        return hashlib.sha256(f"{sal}{password}".encode()).hexdigest() == h
    except Exception:
        return stored == password


class UsuarioModel:
    """CRUD para tabla usuarios."""

    # Sesión en memoria (usuario logueado actual)
    _sesion_actual: Optional["Usuario"] = None

    def autenticar(self, username: str, password: str) -> Optional[Usuario]:
        """Retorna Usuario si credenciales válidas, None si no."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT id, username, nombre, password_hash, rol, activo, recordar, ultimo_login
            FROM usuarios WHERE username = :u AND activo = 1
        """)
        query.bindValue(":u", username.strip())
        query.exec()
        if not query.next():
            return None
        user = Usuario(
            id=query.value(0), username=query.value(1),
            nombre=query.value(2), password_hash=query.value(3),
            rol=query.value(4), activo=bool(query.value(5)),
            recordar=bool(query.value(6)), ultimo_login=query.value(7) or "",
        )
        if not _verificar_password(password, user.password_hash):
            return None
        # Actualizar último login
        upd = QSqlQuery(db)
        upd.prepare("UPDATE usuarios SET ultimo_login = datetime('now') WHERE id = :id")
        upd.bindValue(":id", user.id)
        upd.exec()
        UsuarioModel._sesion_actual = user
        return user

    def get_all(self) -> list[Usuario]:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.exec("""
            SELECT id, username, nombre, password_hash, rol, activo, recordar, ultimo_login
            FROM usuarios ORDER BY nombre
        """)
        usuarios = []
        while query.next():
            usuarios.append(Usuario(
                id=query.value(0), username=query.value(1),
                nombre=query.value(2), password_hash=query.value(3),
                rol=query.value(4), activo=bool(query.value(5)),
                recordar=bool(query.value(6)), ultimo_login=query.value(7) or "",
            ))
        return usuarios

    def insertar(self, u: Usuario, password: str) -> int:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO usuarios(username, nombre, password_hash, rol, activo)
            VALUES(:u, :n, :ph, :r, :a)
        """)
        query.bindValue(":u", u.username)
        query.bindValue(":n", u.nombre)
        query.bindValue(":ph", _hash_password(password))
        query.bindValue(":r", u.rol)
        query.bindValue(":a", 1)
        if query.exec():
            return query.lastInsertId()
        return 0

    def actualizar(self, u: Usuario, nueva_password: str = "") -> bool:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        if nueva_password:
            query.prepare("""
                UPDATE usuarios SET nombre=:n, rol=:r, activo=:a,
                password_hash=:ph WHERE id=:id
            """)
            query.bindValue(":ph", _hash_password(nueva_password))
        else:
            query.prepare("""
                UPDATE usuarios SET nombre=:n, rol=:r, activo=:a WHERE id=:id
            """)
        query.bindValue(":n", u.nombre)
        query.bindValue(":r", u.rol)
        query.bindValue(":a", 1 if u.activo else 0)
        query.bindValue(":id", u.id)
        return query.exec()

    def guardar_recordar(self, username: str, recordar: bool) -> None:
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("UPDATE usuarios SET recordar=:r WHERE username=:u")
        query.bindValue(":r", 1 if recordar else 0)
        query.bindValue(":u", username)
        query.exec()

    def get_usuario_recordado(self) -> Optional[str]:
        """Retorna el username que tiene recordar=1, si existe."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.exec("SELECT username FROM usuarios WHERE recordar=1 LIMIT 1")
        if query.next():
            return query.value(0)
        return None

    @classmethod
    def usuario_actual(cls) -> Optional[Usuario]:
        return cls._sesion_actual

    @classmethod
    def cerrar_sesion(cls) -> None:
        cls._sesion_actual = None
