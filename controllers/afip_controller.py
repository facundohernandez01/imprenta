"""
Controlador AFIP. Orquesta WSAA + WSFE usando los módulos existentes.
Cachea el token/sign hasta su vencimiento.
"""
import os
from datetime import datetime
from pathlib import Path

from models.config_model import ConfigModel


class AFIPController:
    """Fachada para operaciones AFIP en la app."""

    _token: str = ""
    _sign: str = ""
    _expiration: str = ""

    def __init__(self) -> None:
        self.config = ConfigModel()

    def get_cuit_emisor(self) -> str:
        return self.config.get("cuit", "").replace("-", "").strip()

    def get_punto_venta(self) -> int:
        return int(self.config.get("punto_venta", "1") or 1)

    def _cert_dir(self) -> Path:
        """Devuelve directorio de certificados del proyecto."""
        from db.database import DatabaseManager
        # Guarda en misma carpeta que la DB
        db_mgr = DatabaseManager()
        cert_dir = Path(db_mgr.db_path).parent / "certificados" / self.get_cuit_emisor()
        cert_dir.mkdir(parents=True, exist_ok=True)
        return cert_dir

    def cert_paths(self) -> tuple[str, str]:
        """Retorna (cert.crt, wsaa.key)"""
        d = self._cert_dir()
        return str(d / "wsaa.crt"), str(d / "wsaa.key")

    def certificados_existen(self) -> bool:
        crt, key = self.cert_paths()
        return Path(crt).exists() and Path(key).exists()

    def _credenciales_vigentes(self) -> bool:
        if not (self._token and self._sign and self._expiration):
            return False
        try:
            exp = datetime.fromisoformat(self._expiration.replace("-03:00", "+00:00")
                                         .replace("-03:00", ""))
            return datetime.utcnow() < exp.replace(tzinfo=None)
        except Exception:
            return False

    def autenticar(self) -> dict:
        """Obtiene token/sign del WSAA. Reutiliza si sigue vigente."""
        if self._credenciales_vigentes():
            return {"success": True, "token": self._token,
                    "sign": self._sign, "reused": True}

        cuit = self.get_cuit_emisor()
        if not cuit:
            return {"success": False, "message": "CUIT del emisor no configurado."}
        if not self.certificados_existen():
            crt, _ = self.cert_paths()
            return {"success": False,
                    "message": f"Certificados no encontrados en:\n{Path(crt).parent}"}

        try:
            from wsaa_client import WSAAClient
            crt, key = self.cert_paths()
            cliente = WSAAClient(cert_file=crt, key_file=key)
            resultado = cliente.login()
            if resultado["success"]:
                self._token      = cliente.token or ""
                self._sign       = cliente.sign or ""
                self._expiration = cliente.expiration or ""
            return resultado
        except Exception as e:
            return {"success": False, "message": f"Error WSAA: {e}"}

    def emitir_factura(self, datos: dict) -> dict:
        """Emite factura electrónica via WSFE."""
        auth = self.autenticar()
        if not auth["success"]:
            return auth
        try:
            from wsfe_client import WSFEClient
            cliente = WSFEClient(
                token=self._token,
                sign=self._sign,
                cuit=self.get_cuit_emisor(),
            )
            datos["punto_venta"] = datos.get("punto_venta", self.get_punto_venta())
            return cliente.emitir_factura(datos)
        except Exception as e:
            return {"success": False, "message": f"Error WSFE: {e}"}

    def generar_csr(self, cuit: str, org_name: str, extra: dict = None) -> dict:
        """Genera clave privada + CSR para enviar a AFIP."""
        try:
            from afip_cert_manager import AFIPCertManager

            class _FakeDB:
                def set_config_value(self, k, v):
                    ConfigModel().set(k, v)

            cert_dir = str(Path(self._cert_dir()).parent)
            mgr = AFIPCertManager(_FakeDB(), storage_dir=cert_dir, cuit=cuit)
            return mgr.generate_key_and_csr(
                cuit=cuit, alias="wsaa", org_name=org_name,
                extra_subject=extra or {}
            )
        except Exception as e:
            return {"success": False, "message": str(e)}

    def importar_certificado(self, cuit: str, crt_bytes: bytes) -> dict:
        """Importa el .crt descargado de AFIP."""
        try:
            from afip_cert_manager import AFIPCertManager

            class _FakeDB:
                def set_config_value(self, k, v):
                    ConfigModel().set(k, v)

            cert_dir = str(Path(self._cert_dir()).parent)
            mgr = AFIPCertManager(_FakeDB(), storage_dir=cert_dir, cuit=cuit)
            return mgr.import_cert_and_store(cuit=cuit, crt_bytes=crt_bytes)
        except Exception as e:
            return {"success": False, "message": str(e)}

    def info_certificado(self) -> dict:
        """Retorna info del certificado actual."""
        try:
            from afip_cert_manager import AFIPCertManager

            class _FakeDB:
                def set_config_value(self, k, v):
                    pass

            cert_dir = str(Path(self._cert_dir()).parent)
            mgr = AFIPCertManager(_FakeDB(), storage_dir=cert_dir,
                                   cuit=self.get_cuit_emisor())
            return mgr.verificar_conexion()
        except Exception as e:
            return {"error": str(e)}
