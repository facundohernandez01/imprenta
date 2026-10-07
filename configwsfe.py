"""
configwsfe.py
─────────────
Configuración centralizada AFIP. Sin dependencia de database_manager.
Los certificados se organizan por CUIT: certificados/<cuit>/wsaa.crt|wsaa.key
"""
import os

# ── Modo de operación ───────────────────────────────────────────────────────
TESTING = False

# ── Directorio base ─────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CERT_BASE_DIR = os.path.join(BASE_DIR, "certificados")

# ── URLs de servicios AFIP ───────────────────────────────────────────────────
if TESTING:
    WSAA_URL = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl"
    WSFE_URL = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
else:
    WSAA_URL = "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl"
    WSFE_URL = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"

# ── Tipos de comprobante ─────────────────────────────────────────────────────
TIPO_CBTE_FACTURA_A = 1
TIPO_CBTE_FACTURA_B = 6
TIPO_CBTE_FACTURA_C = 11

# ── Concepto ────────────────────────────────────────────────────────────────
CONCEPTO_PRODUCTOS = 1
CONCEPTO_SERVICIOS = 2
CONCEPTO_MIXTO     = 3

# ── Tipo de documento receptor ───────────────────────────────────────────────
DOC_TIPO_CUIT             = 80
DOC_TIPO_DNI              = 96
DOC_TIPO_CONSUMIDOR_FINAL = 99

# ── Alícuotas IVA ────────────────────────────────────────────────────────────
IVA_0_PORCIENTO    = 3
IVA_10_5_PORCIENTO = 4
IVA_21_PORCIENTO   = 5
IVA_27_PORCIENTO   = 6

# ── Moneda ───────────────────────────────────────────────────────────────────
MONEDA_PESOS   = "PES"
MONEDA_DOLARES = "DOL"


# ── Helpers ──────────────────────────────────────────────────────────────────
def get_cert_dir(cuit: str) -> str:
    """Devuelve la carpeta de certificados de un CUIT: certificados/<cuit>/"""
    return os.path.join(CERT_BASE_DIR, cuit.strip().replace("-", ""))


def get_cert_paths(cuit: str) -> tuple:
    """Devuelve (cert_file, key_file) para el CUIT dado.
    Estructura: certificados/<cuit>/wsaa.crt  y  certificados/<cuit>/wsaa.key
    """
    d = get_cert_dir(cuit)
    return os.path.join(d, "wsaa.crt"), os.path.join(d, "wsaa.key")


def get_modo_texto() -> str:
    return "HOMOLOGACIÓN (Testing)" if TESTING else "PRODUCCIÓN"


def validar_certificados(cuit: str) -> bool:
    """Verifica que existan crt y key para el CUIT dado."""
    cert_f, key_f = get_cert_paths(cuit)
    for path, nombre in [(cert_f, "certificado (.crt)"), (key_f, "clave privada (.key)")]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"No se encontró {nombre} para CUIT {cuit}: {path}")
    return True


def get_info_config(cuit: str) -> dict:
    cert_f, key_f = get_cert_paths(cuit)
    return {
        "modo":        get_modo_texto(),
        "cuit":        cuit,
        "certificado": cert_f,
        "wsaa_url":    WSAA_URL,
        "wsfe_url":    WSFE_URL,
    }
