"""
Cliente para Web Service de Facturación Electrónica (WSFE) de AFIP
Maneja la emisión de comprobantes electrónicos con soporte para Python 3.13+
"""
import ssl
import requests
from datetime import datetime
from zeep import Client
from zeep.transports import Transport
from requests import Session
import configwsfe as config

# --- SOLUCIÓN ERROR DH_KEY_TOO_SMALL ---
ctx = ssl.create_default_context()
ctx.set_ciphers('DEFAULT@SECLEVEL=1')
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

class SSLAdapter(requests.adapters.HTTPAdapter):
    """Adaptador que inyecta el contexto SSL personalizado"""
    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = ctx
        return super(SSLAdapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = ctx
        return super(SSLAdapter, self).proxy_manager_for(*args, **kwargs)
# ---------------------------------------

class WSFEClient:
    """Cliente para operaciones de facturación electrónica con WSFE"""
    
    def __init__(self, token, sign, cuit: str = None):
        """Inicializa el cliente WSFE con las credenciales de WSAA.
        cuit: CUIT del contribuyente emisor (obligatorio para operar).
        Si no se pasa se lanza un error claro.
        """
        if not cuit:
            raise ValueError("WSFEClient requiere el CUIT del contribuyente. "
                             "Pasarlo como: WSFEClient(token, sign, cuit='20...')")
        self.url   = config.WSFE_URL
        self.token = token
        self.sign  = sign
        self.cuit  = cuit.strip().replace("-", "")
        
        # Configurar la sesión con el adaptador SSL
        session = Session()
        session.mount('https://', SSLAdapter())
        session.verify = False
        
        # Silenciar los warnings de InsecureRequest
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        transport = Transport(session=session, timeout=30)
        self.client = Client(self.url, transport=transport)
    
    def _create_auth(self):
        """Crea el objeto de autenticación para las solicitudes"""
        return {
            'Token': self.token,
            'Sign': self.sign,
            'Cuit': self.cuit
        }
    
    def get_ultimo_comprobante(self, punto_venta, tipo_cbte):
        """Retorna el último número de comprobante autorizado por AFIP"""
        try:
            auth = self._create_auth()
            response = self.client.service.FECompUltimoAutorizado(
                Auth=auth,
                PtoVta=punto_venta,
                CbteTipo=tipo_cbte
            )
            
            if hasattr(response, 'Errors') and response.Errors:
                return {'success': False, 'message': response.Errors.Err[0].Msg}
                
            return {'success': True, 'ultimo_nro': response.CbteNro}
        except Exception as e:
            return {'success': False, 'message': str(e)}
        
    def emitir_factura(self, datos_factura):
        """
        Emite una factura electronica.

        Campos esperados en datos_factura:
          punto_venta, tipo_cbte, concepto, tipo_doc, nro_doc,
          importe_neto, iva_porcentaje, importe_tributos (opcional),
          cbte_desde (opcional — si no viene, se consulta FECompUltimoAutorizado)
        """
        try:
            print("=" * 60)
            print(f"[WSFE] Iniciando emision: {datos_factura}")

            auth = self._create_auth()

            # ── Numeracion ────────────────────────────────────────────────
            if datos_factura.get('cbte_desde'):
                siguiente_nro = int(datos_factura['cbte_desde'])
                print(f"[WSFE] Usando cbte_desde={siguiente_nro} (pasado por caller)")
            else:
                ultimo = self.get_ultimo_comprobante(
                    datos_factura['punto_venta'],
                    datos_factura['tipo_cbte']
                )
                if not ultimo['success']:
                    print(f"[WSFE] Error FECompUltimoAutorizado: {ultimo['message']}")
                    return ultimo
                siguiente_nro = ultimo['ultimo_nro'] + 1
                print(f"[WSFE] Ultimo AFIP={ultimo['ultimo_nro']} → siguiente={siguiente_nro}")

            # ── Importes ──────────────────────────────────────────────────
            importe_neto = round(float(datos_factura['importe_neto']), 2)
            importe_trib = round(float(datos_factura.get('importe_tributos', 0) or 0), 2)

            # Tipos sin IVA: Factura C (11), NC-C (13), ND-C (12)
            tipo_cbte = datos_factura['tipo_cbte']
            if tipo_cbte in (11, 12, 13):
                importe_iva = 0.0
                print(f"[WSFE] Tipo {tipo_cbte} → ImpIVA=0 (no discrimina IVA)")
            elif datos_factura['iva_porcentaje'] == config.IVA_21_PORCIENTO:
                importe_iva = round(importe_neto * 0.21, 2)
            elif datos_factura['iva_porcentaje'] == config.IVA_10_5_PORCIENTO:
                importe_iva = round(importe_neto * 0.105, 2)
            else:
                importe_iva = 0.0

            importe_total = round(importe_neto + importe_iva + importe_trib, 2)
            # Fecha del comprobante: desde datos o hoy
            _fecha_raw = datos_factura.get('fecha_cbte', '')
            if _fecha_raw:
                # Acepta YYYYMMDD o DD/MM/YYYY
                if '/' in str(_fecha_raw):
                    try:
                        _d = datetime.strptime(str(_fecha_raw).strip(), "%d/%m/%Y")
                        fecha_cbte = _d.strftime("%Y%m%d")
                    except ValueError:
                        fecha_cbte = datetime.now().strftime("%Y%m%d")
                else:
                    fecha_cbte = str(_fecha_raw).strip()[:8]
            else:
                fecha_cbte = datetime.now().strftime("%Y%m%d")

            print(f"[WSFE] N={siguiente_nro} neto={importe_neto} iva={importe_iva} trib={importe_trib} total={importe_total}")

            # ── Construccion del request ──────────────────────────────────
            factory = self.client.type_factory('ns0')

            cabecera = factory.FECAECabRequest(
                CantReg=1,
                PtoVta=datos_factura['punto_venta'],
                CbteTipo=tipo_cbte,
            )

            detalle = factory.FECAEDetRequest(
                Concepto=datos_factura.get('concepto', config.CONCEPTO_PRODUCTOS),
                DocTipo=datos_factura.get('tipo_doc', config.DOC_TIPO_CONSUMIDOR_FINAL),
                DocNro=datos_factura.get('nro_doc', 0),
                CbteDesde=siguiente_nro,
                CbteHasta=siguiente_nro,
                CbteFch=fecha_cbte,
                ImpTotal=importe_total,
                ImpTotConc=0.00,
                ImpNeto=importe_neto,
                ImpOpEx=0.00,
                ImpIVA=importe_iva,
                ImpTrib=importe_trib,
                MonId=datos_factura.get('moneda', config.MONEDA_PESOS),
                MonCotiz=datos_factura.get('cotizacion', 1.0),
            )

            # Período de servicio (obligatorio para concepto 2=Servicios, 3=Mixto)
            concepto_val = datos_factura.get('concepto', config.CONCEPTO_PRODUCTOS)
            if concepto_val in (2, 3):
                fch_serv_desde = datos_factura.get('fch_serv_desde', '')
                fch_serv_hasta = datos_factura.get('fch_serv_hasta', '')
                # Si no vienen explícitos, usar mes completo de fecha_cbte
                if not fch_serv_desde or not fch_serv_hasta:
                    _dt = datetime.strptime(fecha_cbte, "%Y%m%d")
                    import calendar
                    _ultimo_dia = calendar.monthrange(_dt.year, _dt.month)[1]
                    fch_serv_desde = _dt.replace(day=1).strftime("%Y%m%d")
                    fch_serv_hasta = _dt.replace(day=_ultimo_dia).strftime("%Y%m%d")
                # Normalizar formato
                for _raw, _attr in [(fch_serv_desde, 'desde'), (fch_serv_hasta, 'hasta')]:
                    if '/' in str(_raw):
                        try:
                            _dv = datetime.strptime(str(_raw).strip(), "%d/%m/%Y")
                            if _attr == 'desde': fch_serv_desde = _dv.strftime("%Y%m%d")
                            else:                fch_serv_hasta  = _dv.strftime("%Y%m%d")
                        except ValueError:
                            pass
                detalle.FchServDesde = fch_serv_desde
                detalle.FchServHasta = fch_serv_hasta
                detalle.FchVtoPago   = datos_factura.get('fch_vto_pago', fch_serv_hasta)
                print(f"[WSFE] Servicio: desde={fch_serv_desde} hasta={fch_serv_hasta}")

            # Alicuota de IVA solo si hay IVA
            if importe_iva > 0:
                alic_iva = factory.AlicIva(
                    Id=datos_factura['iva_porcentaje'],
                    BaseImp=importe_neto,
                    Importe=importe_iva,
                )
                detalle.Iva = factory.ArrayOfAlicIva([alic_iva])

            # Comprobante asociado (obligatorio para NC/ND)
            cbte_asoc = datos_factura.get('cbte_asoc')
            if cbte_asoc:
                asoc = factory.CbteAsoc(
                    Tipo=cbte_asoc['tipo'],
                    PtoVta=cbte_asoc['punto_venta'],
                    Nro=cbte_asoc['numero'],
                )
                detalle.CbtesAsoc = factory.ArrayOfCbteAsoc([asoc])
                print(f"[WSFE] CbteAsoc: tipo={cbte_asoc['tipo']} pv={cbte_asoc['punto_venta']} nro={cbte_asoc['numero']}")

            solicitud = factory.FECAERequest(
                FeCabReq=cabecera,
                FeDetReq=factory.ArrayOfFECAEDetRequest([detalle]),
            )

            # ── Llamada al servicio ───────────────────────────────────────
            print(f"[WSFE] Enviando FECAESolicitar...")
            response = self.client.service.FECAESolicitar(
                Auth=auth,
                FeCAEReq=solicitud,
            )
            print(f"[WSFE] Respuesta recibida. FeDetResp={hasattr(response, 'FeDetResp')}")

            # ── Errores generales de la respuesta ─────────────────────────
            errores_grales = []
            if hasattr(response, 'Errors') and response.Errors:
                for er in response.Errors.Err:
                    msg = f"Cod {er.Code}: {er.Msg}"
                    print(f"[WSFE] Error general: {msg}")
                    errores_grales.append(msg)
            if errores_grales:
                return {'success': False, 'message': "Error AFIP: " + " | ".join(errores_grales)}

            # ── Procesar detalle de respuesta ─────────────────────────────
            if not (hasattr(response, 'FeDetResp') and response.FeDetResp):
                print("[WSFE] Respuesta vacia o sin FeDetResp")
                return {'success': False, 'message': 'Respuesta vacia de AFIP'}

            det = response.FeDetResp.FECAEDetResponse[0]
            resultado = det.Resultado
            print(f"[WSFE] Resultado={resultado} CbteDesde={getattr(det,'CbteDesde','N/A')}")

            if resultado == 'A':
                print(f"[WSFE] Autorizada CAE={det.CAE} vto={det.CAEFchVto}")
                return {
                    'success': True,
                    'numero': siguiente_nro,
                    'cae': det.CAE,
                    'vencimiento_cae': det.CAEFchVto,
                    'message': f'Factura {siguiente_nro} autorizada',
                    'debug': {
                        'neto': importe_neto, 'iva': importe_iva,
                        'trib': importe_trib, 'total': importe_total,
                    },
                }
            else:
                errores = []
                if hasattr(det, 'Observaciones') and det.Observaciones:
                    for obs in det.Observaciones.Obs:
                        errores.append(f"Obs {obs.Code}: {obs.Msg}")
                if hasattr(det, 'Errors') and det.Errors:
                    for er in det.Errors.Err:
                        errores.append(f"Err {er.Code}: {er.Msg}")
                if not errores:
                    errores.append(f"Rechazada resultado='{resultado}' sin detalle")
                msg = " | ".join(errores)
                print(f"[WSFE] Rechazada: {msg}")
                return {
                    'success': False,
                    'message': f"ARCA rechazo: {msg}",
                    'debug': {
                        'neto': importe_neto, 'iva': importe_iva,
                        'trib': importe_trib, 'total': importe_total,
                        'tipo_doc': datos_factura.get('tipo_doc'),
                        'nro_doc':  datos_factura.get('nro_doc'),
                        'cbte_desde': siguiente_nro,
                    },
                }

        except Exception as e:
            import traceback
            print(f"[WSFE] EXCEPCION: {e}")
            traceback.print_exc()
            return {'success': False, 'message': f'Error critico: {str(e)}'}