"""
Cliente para Web Service de Autenticación y Autorización (WSAA) de AFIP
Maneja la autenticación mediante certificados digitales y obtención de Token/Sign
"""
import os
import base64
from datetime import datetime, timedelta
import ssl
import requests  # <--- AGREGADO: Necesario para que SSLAdapter funcione
from lxml import etree
from zeep import Client
from zeep.transports import Transport
from requests import Session
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import configwsfe as config

# 1. DEFINICIÓN DEL CONTEXTO Y LA CLASE
ctx = ssl.create_default_context()
# Esta configuración permite conectar con servidores AFIP antiguos (DH_KEY_TOO_SMALL)
ctx.set_ciphers('DEFAULT@SECLEVEL=1') 
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

class SSLAdapter(requests.adapters.HTTPAdapter):
    """Adaptador para inyectar el contexto SSL con SECLEVEL=1"""
    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = ctx
        return super(SSLAdapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = ctx
        return super(SSLAdapter, self).proxy_manager_for(*args, **kwargs)

class WSAAClient:
    """Cliente para autenticación con WSAA de AFIP"""
    
    def __init__(self, cert_file: str = None, key_file: str = None,
                 cuit: str = None, service: str = "wsfe"):
        """
        cert_file / key_file: rutas explícitas (prioridad).
        cuit: si se pasa, busca en certificados/<cuit>/wsaa.crt|key.
        service: nombre del servicio AFIP para el TRA.
            - "wsfe"                         → Facturación Electrónica
            - "ws_sr_constancia_inscripcion" → Padrón ARCA
        """
        self.url = config.WSAA_URL
        self.service = service
        self.token = None
        self.sign = None
        self.expiration = None

        if cert_file and key_file:
            self.cert_file = cert_file
            self.key_file  = key_file
        elif cuit:
            self.cert_file, self.key_file = config.get_cert_paths(cuit)
        else:
            raise ValueError("WSAAClient requiere cert_file+key_file o cuit. "
                             "Ejemplo: WSAAClient(cuit='20...')")
        
    def crear_tra(self):
        """Crea el TRA (Ticket de Requerimiento de Acceso) en formato XML"""
        unique_id = int(datetime.now().timestamp())
        generation_time = datetime.now() - timedelta(minutes=10)
        expiration_time = datetime.now() + timedelta(hours=12)
        
        gen_time_str = generation_time.strftime("%Y-%m-%dT%H:%M:%S-03:00")
        exp_time_str = expiration_time.strftime("%Y-%m-%dT%H:%M:%S-03:00")
        
        tra = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{gen_time_str}</generationTime>
    <expirationTime>{exp_time_str}</expirationTime>
  </header>
  <service>{self.service}</service>
</loginTicketRequest>"""
        return tra
    
    def firmar_tra(self, tra):
        """Firma el TRA con el certificado usando cryptography (CMS/PKCS7)"""
        try:
            with open(self.cert_file, 'rb') as f:
                cert_data = f.read()
                cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            
            with open(self.key_file, 'rb') as f:
                key_data = f.read()
                private_key = serialization.load_pem_private_key(
                    key_data,
                    password=None,
                    backend=default_backend()
                )
            
            tra_bytes = tra.encode('utf-8')
            options = [pkcs7.PKCS7Options.Binary]
            
            builder = (
                pkcs7.PKCS7SignatureBuilder()
                .set_data(tra_bytes)
                .add_signer(cert, private_key, hashes.SHA256())
            )
            
            cms_data = builder.sign(
                encoding=serialization.Encoding.DER,
                options=options
            )
            
            return base64.b64encode(cms_data).decode('utf-8')
        except Exception as e:
            raise Exception(f"Error al firmar TRA: {str(e)}")
    
    def login(self):
        """Realiza el login y obtiene las credenciales"""
        try:
            # Validar que existan los archivos configurados
            if not __import__("os").path.exists(self.cert_file):
                raise FileNotFoundError(f"Certificado no encontrado: {self.cert_file}")
            if not __import__("os").path.exists(self.key_file):
                raise FileNotFoundError(f"Clave privada no encontrada: {self.key_file}")
            tra = self.crear_tra()
            cms = self.firmar_tra(tra)
            
            # CONFIGURACIÓN DE SESIÓN CON EL ADAPTADOR SSL
            session = Session()
            session.mount('https://', SSLAdapter())
            session.verify = False 
            
            transport = Transport(session=session, timeout=15)
            client = Client(self.url, transport=transport)
            
            response = client.service.loginCms(cms)
            
            root = etree.fromstring(response.encode('utf-8'))
            self.token = root.find('.//token').text
            self.sign = root.find('.//sign').text
            
            header = root.find('.//header')
            if header is not None:
                exp_elem = header.find('expirationTime')
                if exp_elem is not None:
                    self.expiration = exp_elem.text
            
            return {
                'token': self.token,
                'sign': self.sign,
                'expiration': self.expiration,
                'success': True,
                'message': 'Autenticación exitosa'
            }
            
        except Exception as e:
            error_msg = str(e)
            if 'TA valido' in error_msg or 'ya posee' in error_msg.lower():
                return {
                    'success': True,
                    'token': self.token,
                    'sign': self.sign,
                    'expiration': self.expiration,
                    'message': 'Ya existe una autenticación vigente.',
                    'reused': True
                }
            
            return {
                'success': False,
                'message': f'Error en autenticación: {error_msg}'
            }
    
    def get_credentials(self):
        return {'token': self.token, 'sign': self.sign}
    
    def is_authenticated(self):
        return self.token is not None and self.sign is not None