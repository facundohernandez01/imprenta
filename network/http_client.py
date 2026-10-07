"""
network/http_client.py
──────────────────────
HttpProvider: implementa la misma interfaz que LocalProvider
pero haciendo requests HTTP al servidor Flask.

Convierte dicts JSON → dataclasses para que el código de las
vistas no cambie en absoluto.
"""
from __future__ import annotations
import dataclasses
from typing import Optional, Any
import requests as _requests

from network.data_provider import BaseProvider
from network.net_config import get_server_url, get_api_key


# ─── HTTP helper ─────────────────────────────────────────────────────────────

class APIError(Exception):
    pass


def _session() -> _requests.Session:
    s = _requests.Session()
    key = get_api_key()
    if key:
        s.headers.update({"X-API-Key": key})
    s.headers.update({"Content-Type": "application/json"})
    return s


def _get(path: str, params: dict = None) -> Any:
    url = get_server_url() + path
    try:
        r = _session().get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise APIError(data.get("error", "Error desconocido"))
        return data.get("data")
    except _requests.exceptions.ConnectionError:
        raise APIError("Sin conexión al servidor. Verificá que esté encendido.")
    except _requests.exceptions.Timeout:
        raise APIError("El servidor tardó demasiado en responder.")


def _post(path: str, body: dict) -> Any:
    url = get_server_url() + path
    try:
        r = _session().post(url, json=body, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise APIError(data.get("error", "Error desconocido"))
        return data
    except _requests.exceptions.ConnectionError:
        raise APIError("Sin conexión al servidor.")
    except _requests.exceptions.Timeout:
        raise APIError("Timeout")


def _put(path: str, body: dict) -> bool:
    url = get_server_url() + path
    try:
        r = _session().put(url, json=body, timeout=10)
        return r.ok and r.json().get("ok", False)
    except Exception:
        return False


def _patch(path: str, body: dict) -> bool:
    url = get_server_url() + path
    try:
        r = _session().patch(url, json=body, timeout=10)
        return r.ok and r.json().get("ok", False)
    except Exception:
        return False


def _delete(path: str) -> bool:
    url = get_server_url() + path
    try:
        r = _session().delete(url, timeout=10)
        return r.ok and r.json().get("ok", False)
    except Exception:
        return False


# ─── Conversores JSON → dataclass ────────────────────────────────────────────

def _from_dict(cls, d: dict):
    """Crea un dataclass desde dict, ignorando campos extra."""
    if d is None:
        return None
    fields = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in fields})


def _list_from(cls, data) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return [_from_dict(cls, i) for i in data]
    # Si viene envuelto en {"data": [...]}
    if isinstance(data, dict) and "data" in data:
        return [_from_dict(cls, i) for i in data["data"]]
    return []


# ─── Repos HTTP ───────────────────────────────────────────────────────────────

class _ClienteRepo:
    def get_all(self, solo_activos=True):
        from models.cliente_model import Cliente
        return _list_from(Cliente, _get("/clientes", {"solo_activos": "1" if solo_activos else "0"}))

    def get_by_id(self, id):
        from models.cliente_model import Cliente
        return _from_dict(Cliente, _get(f"/clientes/{id}"))

    def insertar(self, c) -> int:
        return (_post("/clientes", dataclasses.asdict(c)) or {}).get("id", 0)

    def actualizar(self, c) -> bool:
        return _put(f"/clientes/{c.id}", dataclasses.asdict(c))

    def eliminar_logico(self, id) -> bool:
        return _delete(f"/clientes/{id}")

    def get_saldo_total(self, id) -> float:
        data = _get(f"/clientes/{id}/saldo")
        return float((data or {}).get("saldo", 0))


class _PedidoRepo:
    def generar_nro_pedido(self) -> str:
        data = _get("/pedidos/nro_nuevo")
        return (data or {}).get("nro", "")

    def get_all(self, filtros=None):
        from models.pedido_model import Pedido
        return _list_from(Pedido, _get("/pedidos", filtros or {}))

    def get_by_id(self, id):
        from models.pedido_model import Pedido
        return _from_dict(Pedido, _get(f"/pedidos/{id}"))

    def insertar(self, p) -> int:
        return (_post("/pedidos", dataclasses.asdict(p)) or {}).get("id", 0)

    def actualizar(self, p) -> bool:
        return _put(f"/pedidos/{p.id}", dataclasses.asdict(p))

    def cambiar_estado(self, id, estado) -> bool:
        return _patch(f"/pedidos/{id}/estado", {"estado": estado})

    def get_stats_footer(self) -> dict:
        data = _get("/pedidos/stats")
        return data if isinstance(data, dict) else {}

    def get_por_estado(self, estados) -> list:
        from models.pedido_model import Pedido
        return _list_from(Pedido, _get("/pedidos/por_estado",
                                        {k: v for k, v in [("estado", e) for e in estados]}))


class _DetalleRepo:
    def get_by_pedido(self, pedido_id):
        from models.models import PedidoDetalle
        return _list_from(PedidoDetalle, _get(f"/pedidos/{pedido_id}/detalle"))

    def insertar(self, d) -> int:
        return (_post("/detalle", dataclasses.asdict(d)) or {}).get("id", 0)

    def actualizar(self, d) -> bool:
        return _put(f"/detalle/{d.id}", dataclasses.asdict(d))

    def eliminar(self, id) -> bool:
        return _delete(f"/detalle/{id}")

    def eliminar_por_pedido(self, pedido_id) -> bool:
        return _delete(f"/detalle/pedido/{pedido_id}")


class _ProductoRepo:
    def get_all(self, solo_activos=True):
        from models.models import Producto
        return _list_from(Producto, _get("/productos", {"solo_activos": "1" if solo_activos else "0"}))

    def get_by_id(self, id):
        from models.models import Producto
        return _from_dict(Producto, _get(f"/productos/{id}"))

    def insertar(self, p) -> int:
        return (_post("/productos", dataclasses.asdict(p)) or {}).get("id", 0)

    def actualizar(self, p) -> bool:
        return _put(f"/productos/{p.id}", dataclasses.asdict(p))

    def eliminar_logico(self, id) -> bool:
        return _delete(f"/productos/{id}")


class _TipoRepo:
    def get_all(self):
        from models.models import TipoTrabajo
        return _list_from(TipoTrabajo, _get("/tipos"))

    def insertar(self, t) -> int:
        return (_post("/tipos", dataclasses.asdict(t)) or {}).get("id", 0)

    def actualizar(self, t) -> bool:
        return _put(f"/tipos/{t.id}", dataclasses.asdict(t))

    def eliminar(self, id) -> bool:
        return _delete(f"/tipos/{id}")


class _PagoRepo:
    def get_by_pedido(self, pedido_id):
        from models.models import Pago
        return _list_from(Pago, _get(f"/pedidos/{pedido_id}/pagos"))

    def insertar(self, p) -> int:
        return (_post("/pagos", dataclasses.asdict(p)) or {}).get("id", 0)

    def eliminar(self, id) -> bool:
        return _delete(f"/pagos/{id}")

    def get_total_pagado(self, pedido_id) -> float:
        data = _get(f"/pedidos/{pedido_id}/pagos/total")
        return float((data or {}).get("total", 0))


class _InsumoRepo:
    def get_all(self):
        from models.models import Insumo
        return _list_from(Insumo, _get("/insumos"))

    def insertar(self, i) -> int:
        return (_post("/insumos", dataclasses.asdict(i)) or {}).get("id", 0)

    def actualizar(self, i) -> bool:
        return _put(f"/insumos/{i.id}", dataclasses.asdict(i))

    def eliminar(self, id) -> bool:
        return _delete(f"/insumos/{id}")


class _ConfigRepo:
    def get_filtros_guardados(self) -> list:
        try:
            data = _get("/pedidos/filtros_guardados")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def guardar_filtro(self, filtro: dict) -> bool:
        return bool(_put("/pedidos/filtros_guardados", filtro))

    def eliminar_filtro(self, nombre: str) -> bool:
        return _delete(f"/pedidos/filtros_guardados/{nombre}")

    def get(self, clave, default="") -> str:
        try:
            data = _get(f"/config/{clave}")
            return (data or {}).get("valor", default)
        except Exception:
            return default

    def set(self, clave, valor) -> bool:
        return _put(f"/config/{clave}", {"valor": valor})

    def esta_configurado(self) -> bool:
        return bool(self.get("razon_social"))

    def get_datos_imprenta(self) -> dict:
        try:
            data = _get("/config")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def set_datos_imprenta(self, datos) -> bool:
        return _put("/config", datos)


class _UsuarioRepo:
    # Sesión en memoria igual que LocalProvider
    _sesion = None

    def autenticar(self, username, password):
        from models.usuario_model import Usuario
        try:
            data = _post("/auth/login", {"username": username, "password": password})
            if data and data.get("ok") and data.get("data"):
                u = _from_dict(Usuario, data["data"])
                _UsuarioRepo._sesion = u
                # También actualizar el singleton de UsuarioModel para compatibilidad
                from models.usuario_model import UsuarioModel
                UsuarioModel._sesion_actual = u
                return u
        except APIError:
            pass
        return None

    def get_all(self):
        from models.usuario_model import Usuario
        return _list_from(Usuario, _get("/usuarios"))

    def insertar(self, u, password) -> int:
        d = dataclasses.asdict(u)
        d["password"] = password
        return (_post("/usuarios", d) or {}).get("id", 0)

    def actualizar(self, u, nueva_password="") -> bool:
        d = dataclasses.asdict(u)
        if nueva_password:
            d["password"] = nueva_password
        return _put(f"/usuarios/{u.id}", d)

    def guardar_recordar(self, username, recordar):
        _put("/usuarios/recordar", {"username": username, "recordar": recordar})

    def get_usuario_recordado(self):
        try:
            data = _get("/usuarios/recordado")
            return (data or {}).get("username")
        except Exception:
            return None


class _FacturaRepo:
    def insertar(self, f) -> int:
        return (_post("/facturas", dataclasses.asdict(f)) or {}).get("id", 0)

    def actualizar_cae(self, id, nro, cae, vto, estado) -> bool:
        return _patch(f"/facturas/{id}/cae",
                       {"nro": nro, "cae": cae, "cae_vto": vto, "estado": estado})

    def marcar_email_enviado(self, id) -> bool:
        return _patch(f"/facturas/{id}/email", {})

    def get_all_facturas(self, limit=200):
        from models.factura_model import Factura
        return _list_from(Factura, _get("/facturas", {"limit": limit}))

    def get_by_pedido(self, pedido_id):
        from models.factura_model import Factura
        return _list_from(Factura, _get(f"/facturas/pedido/{pedido_id}"))

    def get_by_cliente(self, cliente_id):
        from models.factura_model import Factura
        return _list_from(Factura, _get(f"/facturas/cliente/{cliente_id}"))

    def get_by_id(self, id):
        from models.factura_model import Factura
        return _from_dict(Factura, _get(f"/facturas/{id}"))


class _ReciboRepo:
    def get_all_recibos(self, limit=200):
        from models.factura_model import Recibo
        return _list_from(Recibo, _get("/recibos", {"limit": limit}))

    def generar_nro(self) -> str:
        data = _get("/recibos/nro_nuevo")
        return (data or {}).get("nro", "")

    def insertar(self, r) -> int:
        return (_post("/recibos", dataclasses.asdict(r)) or {}).get("id", 0)

    def marcar_email(self, id) -> bool:
        return _patch(f"/recibos/{id}/email", {})

    def get_by_pedido(self, pedido_id):
        from models.factura_model import Recibo
        return _list_from(Recibo, _get(f"/pedidos/{pedido_id}/recibos"))

    def get_by_cliente(self, cliente_id):
        from models.factura_model import Recibo
        return _list_from(Recibo, _get(f"/recibos/cliente/{cliente_id}"))


class _ReporteRepo:
    def ventas_por_dia_mes(self, anio, mes):
        data = _get("/reportes/ventas", {"anio": anio, "mes": mes})
        return data if isinstance(data, list) else []

    def balance_general(self) -> dict:
        data = _get("/reportes/balance")
        return data if isinstance(data, dict) else {}

    def productos_mas_vendidos(self, anio, mes):
        data = _get("/reportes/productos", {"anio": anio, "mes": mes})
        return data if isinstance(data, list) else []

    def pedidos_cuenta_corriente(self, cliente_id):
        data = _get(f"/reportes/cuenta_corriente/{cliente_id}")
        return data if isinstance(data, list) else []


# ─── Provider completo ───────────────────────────────────────────────────────

class HttpProvider(BaseProvider):
    def __init__(self):
        self.clientes  = _ClienteRepo()
        self.pedidos   = _PedidoRepo()
        self.detalle   = _DetalleRepo()
        self.productos = _ProductoRepo()
        self.tipos     = _TipoRepo()
        self.pagos     = _PagoRepo()
        self.insumos   = _InsumoRepo()
        self.config    = _ConfigRepo()
        self.usuarios  = _UsuarioRepo()
        self.facturas  = _FacturaRepo()
        self.recibos   = _ReciboRepo()
        self.reportes  = _ReporteRepo()


def test_conexion(ip: str, port: int, api_key: str = "") -> dict:
    """Verifica conectividad con el servidor antes de guardar config."""
    import requests as req
    url = f"http://{ip}:{port}/health"
    headers = {"X-API-Key": api_key} if api_key else {}
    try:
        r = req.get(url, headers=headers, timeout=5)
        if r.ok:
            data = r.json()
            return {"ok": True, "mensaje": f"Servidor encontrado: v{data.get('version','?')}"}
        return {"ok": False, "mensaje": f"Servidor respondió con error {r.status_code}"}
    except req.exceptions.ConnectionError:
        return {"ok": False, "mensaje": f"No se puede conectar a {ip}:{port}.\nVerificá que el servidor esté encendido."}
    except req.exceptions.Timeout:
        return {"ok": False, "mensaje": "El servidor tardó demasiado. Verificá la IP."}
    except Exception as e:
        return {"ok": False, "mensaje": str(e)}
