"""
Modelo para tabla config. Lee y escribe configuración de la imprenta.
"""
from PySide6.QtSql import QSqlQuery
from db.database import DatabaseManager


class ConfigModel:
    """CRUD para tabla config."""

    def get(self, clave: str, default: str = "") -> str:
        """Obtiene valor de configuración por clave."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("SELECT valor FROM config WHERE clave = :clave")
        query.bindValue(":clave", clave)
        query.exec()
        if query.next():
            return query.value(0) or default
        return default

    def set(self, clave: str, valor: str) -> bool:
        """Inserta o actualiza una clave de configuración."""
        db = DatabaseManager.get_db()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO config(clave, valor) VALUES(:clave, :valor)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
        """)
        query.bindValue(":clave", clave)
        query.bindValue(":valor", valor)
        return query.exec()

    def esta_configurado(self) -> bool:
        """Retorna True si ya se cargaron los datos básicos de la imprenta."""
        razon = self.get("razon_social")
        return bool(razon and razon.strip())

    def get_datos_imprenta(self) -> dict:
        """Retorna todos los datos de la imprenta como dict."""
        claves = ["razon_social", "cuit", "direccion", "telefono",
                  "email", "logo_path", "impresora_default"]
        return {c: self.get(c) for c in claves}

    def set_datos_imprenta(self, datos: dict) -> bool:
        """Guarda múltiples claves de config."""
        for clave, valor in datos.items():
            if not self.set(clave, valor):
                return False
        return True
