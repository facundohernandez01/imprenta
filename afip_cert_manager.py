"""
afip_cert_manager.py - VERSIÓN ACTUALIZADA
Componente para gestión de certificados AFIP
Ahora guarda directamente en ./certificados/ para compatibilidad con wsaa_client y wsfe_client
"""
import os
import errno
from datetime import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------
# CONFIGURACIÓN - CONSOLIDADA CON configwsfe.py
# ---------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STORAGE_DIR = os.path.join(BASE_DIR, "certificados")   # directorio BASE

# Variable de entorno para cifrado opcional
MASTER_KEY_ENV = "AFIP_MASTER_KEY"

# ---------------------------------------------------------------------
# Helpers de filesystem y cifrado
# ---------------------------------------------------------------------
def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

def get_fernet():
    key = os.environ.get(MASTER_KEY_ENV)
    if not key:
        return None
    return Fernet(key)

def write_bytes_secure(path, data: bytes):
    """Escribe bytes en disco. Si hay MASTER_KEY, cifra antes."""
    f = get_fernet()
    if f:
        data = f.encrypt(data)
    with open(path, "wb") as fh:
        fh.write(data)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass

def read_bytes_secure(path) -> bytes:
    """Lee y descifra si aplica."""
    with open(path, "rb") as fh:
        data = fh.read()
    f = get_fernet()
    if f:
        data = f.decrypt(data)
    return data

# ---------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------
class AFIPCertManager:
    """
    Gestor de certificados AFIP
    Ahora guarda directamente en ./certificados/ con nombres estándar
    """
    def __init__(self, db_manager, storage_dir: str = DEFAULT_STORAGE_DIR,
                 cuit: str = None):
        """
        Si se pasa cuit, el directorio de almacenamiento será storage_dir/<cuit>/
        Esto garantiza que cada contribuyente tenga sus propios certificados.
        """
        self.db = db_manager
        if cuit:
            self.storage_dir = os.path.join(storage_dir, cuit.strip().replace("-", ""))
        else:
            self.storage_dir = storage_dir
        ensure_dir(self.storage_dir)

    # -------------------------
    # RUTAS CONSOLIDADAS - Compatible con wsaa_client y wsfe_client
    # -------------------------
    def key_path(self, alias: str = "wsaa"):
        """Ruta de la clave privada - NOMBRE ESTÁNDAR"""
        return os.path.join(self.storage_dir, f"{alias}.key")

    def csr_path(self, alias: str = "wsaa"):
        """Ruta del CSR"""
        return os.path.join(self.storage_dir, f"{alias}.csr")

    def cert_path(self, alias: str = "wsaa"):
        """Ruta del certificado - NOMBRE ESTÁNDAR"""
        return os.path.join(self.storage_dir, f"{alias}.crt")

    def p12_path(self, alias: str = "wsaa"):
        """Ruta del PKCS12"""
        return os.path.join(self.storage_dir, f"{alias}.p12")

    # -------------------------
    # GENERAR CLAVE + CSR
    # -------------------------
    def generate_key_and_csr(self, cuit: str, alias: str = "wsaa", 
                             org_name: str = None, common_name: str = None,
                             country: str = "AR", key_size: int = 2048,
                             key_passphrase: bytes = None,
                             extra_subject: dict = None):
        """
        Genera una clave RSA y un CSR para AFIP
        Guarda en ./certificados/ con nombres estándar
        """
        org_name = org_name or f"Empresa CUIT {cuit}"
        common_name = common_name or org_name

        # Generar clave privada
        key = rsa.generate_private_key(
            public_exponent=65537, 
            key_size=key_size, 
            backend=default_backend()
        )

        # Serializar clave (PEM), opcionalmente cifrada
        if key_passphrase:
            encryption_algo = serialization.BestAvailableEncryption(key_passphrase)
        else:
            encryption_algo = serialization.NoEncryption()

        key_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption_algo
        )

        # Construir subject del CSR
        name_attrs = [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_name),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, f"CUIT {cuit}"),
        ]

        if extra_subject:
            for k, v in extra_subject.items():
                if k.lower() == "email":
                    name_attrs.append(x509.NameAttribute(NameOID.EMAIL_ADDRESS, v))
                elif k.lower() == "orgunit":
                    name_attrs.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, v))

        subject = x509.Name(name_attrs)

        # Crear CSR
        csr_builder = x509.CertificateSigningRequestBuilder().subject_name(subject)
        csr = csr_builder.sign(key, hashes.SHA256(), default_backend())
        csr_pem = csr.public_bytes(serialization.Encoding.PEM)

        # Guardar archivos CON NOMBRES ESTÁNDAR
        kpath = self.key_path(alias)
        cpath = self.csr_path(alias)

        write_bytes_secure(kpath, key_pem)
        write_bytes_secure(cpath, csr_pem)
        
        # Guardar CUIT en config
        self.set_cuit_in_config(cuit)

        return {
            "key_path": kpath, 
            "csr_path": cpath,
            "success": True,
            "message": f"Clave y CSR generados correctamente en {self.storage_dir}"
        }

    # -------------------------
    # IMPORTAR CERTIFICADO
    # -------------------------
    def import_cert_and_store(self, cuit: str, crt_bytes: bytes, alias: str = "wsaa"):
        """
        Importa un certificado descargado de AFIP
        Lo guarda con nombre estándar para que wsaa_client lo encuentre
        """
        try:
            # Intentar cargar como PEM
            cert = x509.load_pem_x509_certificate(crt_bytes, default_backend())
            pem = cert.public_bytes(serialization.Encoding.PEM)
        except Exception:
            # Intentar DER
            cert = x509.load_der_x509_certificate(crt_bytes, default_backend())
            pem = cert.public_bytes(serialization.Encoding.PEM)

        cert_path = self.cert_path(alias)
        write_bytes_secure(cert_path, pem)

        # Guardar CUIT en config
        self.set_cuit_in_config(cuit)

        return {
            "cert_path": cert_path,
            "success": True,
            "message": f"Certificado importado correctamente en {cert_path}"
        }

    # -------------------------
    # CREAR PKCS12
    # -------------------------
    def create_p12(self, alias: str = "wsaa", p12_password: bytes = None):
        """
        Crea un PKCS12 (.p12) bundling key + cert
        """
        kpath = self.key_path(alias)
        certpath = self.cert_path(alias)
        
        if not os.path.exists(kpath) or not os.path.exists(certpath):
            return {
                "success": False,
                "message": "Faltan archivos: key o cert no encontrados"
            }

        key_pem = read_bytes_secure(kpath)
        cert_pem = read_bytes_secure(certpath)

        private_key = serialization.load_pem_private_key(
            key_pem, 
            password=None, 
            backend=default_backend()
        )
        certificate = x509.load_pem_x509_certificate(cert_pem, default_backend())

        # Serializar p12
        friendly_name = f"{alias}".encode("utf-8")
        p12 = pkcs12.serialize_key_and_certificates(
            name=friendly_name,
            key=private_key,
            cert=certificate,
            cas=None,
            encryption_algorithm=(
                serialization.BestAvailableEncryption(p12_password) 
                if p12_password 
                else serialization.NoEncryption()
            )
        )

        p12_path = self.p12_path(alias)
        write_bytes_secure(p12_path, p12)
        
        return {
            "p12_path": p12_path,
            "success": True,
            "message": f"PKCS12 generado en {p12_path}"
        }

    # -------------------------
    # VERIFICAR CONEXIÓN AFIP
    # -------------------------
    def verificar_conexion(self):
        """
        Verifica que los certificados existan y sean válidos
        Retorna información de estado
        """
        key_exists = os.path.exists(self.key_path())
        cert_exists = os.path.exists(self.cert_path())
        
        info = {
            "key_exists": key_exists,
            "cert_exists": cert_exists,
            "storage_dir": self.storage_dir,
            "ready": key_exists and cert_exists
        }
        
        # Si hay certificado, extraer info
        if cert_exists:
            try:
                cert_pem = read_bytes_secure(self.cert_path())
                cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
                
                info["cert_subject"] = cert.subject.rfc4514_string()
                info["cert_issuer"] = cert.issuer.rfc4514_string()
                info["cert_valid_from"] = cert.not_valid_before_utc.strftime("%d/%m/%Y %H:%M")
                info["cert_valid_until"] = cert.not_valid_after_utc.strftime("%d/%m/%Y %H:%M")
                
                # Verificar si está vigente
                now = datetime.now(cert.not_valid_after_utc.tzinfo)
                info["cert_is_valid"] = cert.not_valid_before_utc <= now <= cert.not_valid_after_utc
                
            except Exception as e:
                info["cert_error"] = str(e)
        
        return info

    # -------------------------
    # UTIL: guardar CUIT en config
    # -------------------------
    def set_cuit_in_config(self, cuit: str):
        """Guarda el CUIT en la configuración"""
        if hasattr(self.db, "set_config_value"):
            self.db.set_config_value("CUIT", cuit)
        elif hasattr(self.db, "execute"):
            self.db.execute(
                "INSERT OR REPLACE INTO config (clave, valor) VALUES (?, ?)", 
                ("CUIT", cuit)
            )
            if hasattr(self.db, "commit"):
                self.db.commit()

    # -------------------------
    # ESTADO COMPLETO
    # -------------------------
    def get_status(self, alias: str = "wsaa"):
        """Devuelve estado completo de los archivos"""
        return {
            "key": os.path.exists(self.key_path(alias)),
            "key_path": self.key_path(alias),
            "csr": os.path.exists(self.csr_path(alias)),
            "csr_path": self.csr_path(alias),
            "cert": os.path.exists(self.cert_path(alias)),
            "cert_path": self.cert_path(alias),
            "p12": os.path.exists(self.p12_path(alias)),
            "p12_path": self.p12_path(alias),
            "storage_dir": self.storage_dir
        }