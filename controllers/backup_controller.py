"""
Backup automático de la base de datos al cerrar la app.
"""
import shutil
from datetime import datetime
from pathlib import Path
from db.database import DatabaseManager


class BackupController:
    """Copia la DB a /backups/ con timestamp."""

    def hacer_backup(self) -> str | None:
        """
        Copia gestion_imprenta.db a backups/db_YYYYMMDD_HHMM.db.
        Mantiene los últimos 30 backups.
        Retorna path del backup creado o None si falló.
        """
        db_manager = DatabaseManager()
        origen = db_manager.db_path
        backup_dir = db_manager.backup_dir

        if not origen.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        destino = backup_dir / f"db_{timestamp}.db"

        try:
            shutil.copy2(str(origen), str(destino))
            self._limpiar_backups_viejos(backup_dir, mantener=30)
            return str(destino)
        except Exception as e:
            print(f"Error backup: {e}")
            return None

    @staticmethod
    def _limpiar_backups_viejos(backup_dir: Path, mantener: int = 30) -> None:
        """Elimina backups más viejos manteniendo solo los N más recientes."""
        archivos = sorted(
            backup_dir.glob("db_*.db"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        for archivo in archivos[mantener:]:
            try:
                archivo.unlink()
            except Exception:
                pass
