"""
server/flask_server.py
──────────────────────
Servidor Flask embebido. Corre en un hilo daemon dentro de la app.
Expone todos los endpoints necesarios para que los clientes puedan
operar sin acceder directamente a la DB.

Autenticación: header X-API-Key en todas las rutas.
Serialización: JSON con dataclasses convertidos a dict via dataclasses.asdict().
"""
from __future__ import annotations
import threading
import logging
import dataclasses
from datetime import date
from typing import Any
from flask import Flask, request, jsonify, g

# Silenciar logs de Flask en producción
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app = Flask(__name__)
_api_key: str = ""
_server_thread: threading.Thread | None = None


def _dc_to_dict(obj) -> Any:
    """Convierte dataclass a dict recursivamente."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dc_to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_dc_to_dict(i) for i in obj]
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def _ok(data=None, **kwargs) -> Any:
    payload = {"ok": True}
    if data is not None:
        payload["data"] = _dc_to_dict(data)
    payload.update(kwargs)
    return jsonify(payload)


def _err(msg: str, code: int = 400) -> Any:
    return jsonify({"ok": False, "error": msg}), code


# ─── Auth middleware ──────────────────────────────────────────────────────────

@app.before_request
def _check_auth():
    if request.method == "OPTIONS":
        return
    key = request.headers.get("X-API-Key", "")
    if _api_key and key != _api_key:
        return _err("Unauthorized", 401)


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({"ok": True, "version": "1.0", "modo": "server"})

@app.get("/api/v1/pedidos/<int:pid>/log")
def pedido_log_get(pid):
    from models.pedido_log_model import PedidoLogModel
    return _ok(PedidoLogModel().get_by_pedido(pid))

@app.post("/api/v1/pedidos/<int:pid>/log")
def pedido_log_post(pid):
    from models.pedido_log_model import PedidoLogModel
    d = request.json or {}
    ok = PedidoLogModel().registrar(
        pid, d.get("tipo","cambio"), d.get("descripcion",""), d.get("usuario","")
    )
    return _ok() if ok else _err("Error")


# ─── CLIENTES ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/clientes")
def clientes_get_all():
    solo = request.args.get("solo_activos", "1") == "1"
    from models.cliente_model import ClienteModel
    return _ok(ClienteModel().get_all(solo_activos=solo))

@app.get("/api/v1/clientes/<int:cid>")
def clientes_get_by_id(cid):
    from models.cliente_model import ClienteModel
    c = ClienteModel().get_by_id(cid)
    return _ok(c) if c else _err("Not found", 404)

@app.post("/api/v1/clientes")
def clientes_insertar():
    from models.cliente_model import ClienteModel, Cliente
    d = request.json or {}
    c = Cliente(**{k: v for k, v in d.items() if k in Cliente.__dataclass_fields__})
    new_id = ClienteModel().insertar(c)
    return _ok(id=new_id) if new_id else _err("Error al insertar")

@app.put("/api/v1/clientes/<int:cid>")
def clientes_actualizar(cid):
    from models.cliente_model import ClienteModel, Cliente
    d = request.json or {}
    d["id"] = cid
    c = Cliente(**{k: v for k, v in d.items() if k in Cliente.__dataclass_fields__})
    ok = ClienteModel().actualizar(c)
    return _ok() if ok else _err("Error al actualizar")

@app.delete("/api/v1/clientes/<int:cid>")
def clientes_eliminar(cid):
    from models.cliente_model import ClienteModel
    ok = ClienteModel().eliminar_logico(cid)
    return _ok() if ok else _err("Error")

@app.get("/api/v1/clientes/<int:cid>/saldo")
def clientes_saldo(cid):
    from models.cliente_model import ClienteModel
    s = ClienteModel().get_saldo_total(cid)
    return _ok(saldo=s)


# ─── PEDIDOS ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/pedidos/nro_nuevo")
def pedidos_nro_nuevo():
    from models.pedido_model import PedidoModel
    return _ok(nro=PedidoModel().generar_nro_pedido())

@app.get("/api/v1/pedidos")
def pedidos_get_all():
    from models.pedido_model import PedidoModel
    filtros = {k: v for k, v in request.args.items() if v}
    return _ok(PedidoModel().get_all(filtros or None))

@app.get("/api/v1/pedidos/stats")
def pedidos_stats():
    from models.pedido_model import PedidoModel
    return _ok(PedidoModel().get_stats_footer())

@app.get("/api/v1/pedidos/por_estado")
def pedidos_por_estado():
    from models.pedido_model import PedidoModel
    estados = request.args.getlist("estado")
    return _ok(PedidoModel().get_por_estado(estados))

@app.get("/api/v1/pedidos/filtros_guardados")
def pedidos_filtros_guardados():
    """Retorna lista de filtros guardados por usuario."""
    from models.config_model import ConfigModel
    import json
    raw = ConfigModel().get("filtros_guardados_pedidos", "[]")
    try:
        return _ok(json.loads(raw))
    except Exception:
        return _ok([])

@app.put("/api/v1/pedidos/filtros_guardados")
def pedidos_guardar_filtro():
    from models.config_model import ConfigModel
    import json
    d = request.json or {}
    raw = ConfigModel().get("filtros_guardados_pedidos", "[]")
    try:
        filtros = json.loads(raw)
    except Exception:
        filtros = []
    # Evitar duplicados por nombre
    filtros = [f for f in filtros if f.get("nombre") != d.get("nombre")]
    filtros.append(d)
    ConfigModel().set("filtros_guardados_pedidos", json.dumps(filtros))
    return _ok()

@app.delete("/api/v1/pedidos/filtros_guardados/<nombre>")
def pedidos_eliminar_filtro(nombre):
    from models.config_model import ConfigModel
    import json
    raw = ConfigModel().get("filtros_guardados_pedidos", "[]")
    try:
        filtros = json.loads(raw)
    except Exception:
        filtros = []
    filtros = [f for f in filtros if f.get("nombre") != nombre]
    ConfigModel().set("filtros_guardados_pedidos", json.dumps(filtros))
    return _ok()

@app.get("/api/v1/pedidos/<int:pid>")
def pedidos_get_by_id(pid):
    from models.pedido_model import PedidoModel
    p = PedidoModel().get_by_id(pid)
    return _ok(p) if p else _err("Not found", 404)

@app.post("/api/v1/pedidos")
def pedidos_insertar():
    from models.pedido_model import PedidoModel, Pedido
    d = request.json or {}
    p = Pedido(**{k: v for k, v in d.items() if k in Pedido.__dataclass_fields__})
    new_id = PedidoModel().insertar(p)
    return _ok(id=new_id) if new_id else _err("Error al insertar")

@app.put("/api/v1/pedidos/<int:pid>")
def pedidos_actualizar(pid):
    from models.pedido_model import PedidoModel, Pedido
    d = request.json or {}
    d["id"] = pid
    p = Pedido(**{k: v for k, v in d.items() if k in Pedido.__dataclass_fields__})
    ok = PedidoModel().actualizar(p)
    return _ok() if ok else _err("Error al actualizar")

@app.patch("/api/v1/pedidos/<int:pid>/estado")
def pedidos_cambiar_estado(pid):
    from models.pedido_model import PedidoModel
    estado = (request.json or {}).get("estado", "")
    ok = PedidoModel().cambiar_estado(pid, estado)
    return _ok() if ok else _err("Error")


# ─── DETALLE ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/pedidos/<int:pid>/detalle")
def detalle_get(pid):
    from models.models import PedidoDetalleModel
    return _ok(PedidoDetalleModel().get_by_pedido(pid))

@app.post("/api/v1/detalle")
def detalle_insertar():
    from models.models import PedidoDetalleModel, PedidoDetalle
    d = request.json or {}
    obj = PedidoDetalle(**{k: v for k, v in d.items() if k in PedidoDetalle.__dataclass_fields__})
    new_id = PedidoDetalleModel().insertar(obj)
    return _ok(id=new_id) if new_id else _err("Error")

@app.delete("/api/v1/detalle/pedido/<int:pid>")
def detalle_eliminar_por_pedido(pid):
    from models.models import PedidoDetalleModel
    ok = PedidoDetalleModel().eliminar_por_pedido(pid)
    return _ok() if ok else _err("Error")


# ─── PRODUCTOS ────────────────────────────────────────────────────────────────

@app.get("/api/v1/productos")
def productos_get_all():
    from models.models import ProductoModel
    solo = request.args.get("solo_activos", "1") == "1"
    return _ok(ProductoModel().get_all(solo_activos=solo))

@app.get("/api/v1/productos/<int:pid>")
def productos_get_by_id(pid):
    from models.models import ProductoModel
    p = ProductoModel().get_by_id(pid)
    return _ok(p) if p else _err("Not found", 404)

@app.post("/api/v1/productos")
def productos_insertar():
    from models.models import ProductoModel, Producto
    d = request.json or {}
    p = Producto(**{k: v for k, v in d.items() if k in Producto.__dataclass_fields__})
    new_id = ProductoModel().insertar(p)
    return _ok(id=new_id) if new_id else _err("Error")

@app.put("/api/v1/productos/<int:pid>")
def productos_actualizar(pid):
    from models.models import ProductoModel, Producto
    d = request.json or {}
    d["id"] = pid
    p = Producto(**{k: v for k, v in d.items() if k in Producto.__dataclass_fields__})
    ok = ProductoModel().actualizar(p)
    return _ok() if ok else _err("Error")

@app.delete("/api/v1/productos/<int:pid>")
def productos_eliminar(pid):
    from models.models import ProductoModel
    ok = ProductoModel().eliminar_logico(pid)
    return _ok() if ok else _err("Error")


# ─── TIPOS DE TRABAJO ─────────────────────────────────────────────────────────

@app.get("/api/v1/tipos")
def tipos_get_all():
    from models.models import TipoTrabajoModel
    return _ok(TipoTrabajoModel().get_all())

@app.post("/api/v1/tipos")
def tipos_insertar():
    from models.models import TipoTrabajoModel, TipoTrabajo
    d = request.json or {}
    t = TipoTrabajo(**{k: v for k, v in d.items() if k in TipoTrabajo.__dataclass_fields__})
    new_id = TipoTrabajoModel().insertar(t)
    return _ok(id=new_id) if new_id else _err("Error")

@app.put("/api/v1/tipos/<int:tid>")
def tipos_actualizar(tid):
    from models.models import TipoTrabajoModel, TipoTrabajo
    d = request.json or {}
    d["id"] = tid
    t = TipoTrabajo(**{k: v for k, v in d.items() if k in TipoTrabajo.__dataclass_fields__})
    ok = TipoTrabajoModel().actualizar(t)
    return _ok() if ok else _err("Error")

@app.delete("/api/v1/tipos/<int:tid>")
def tipos_eliminar(tid):
    from models.models import TipoTrabajoModel
    ok = TipoTrabajoModel().eliminar(tid)
    return _ok() if ok else _err("Error")


# ─── PAGOS ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/pedidos/<int:pid>/pagos")
def pagos_get(pid):
    from models.models import PagoModel
    return _ok(PagoModel().get_by_pedido(pid))

@app.post("/api/v1/pagos")
def pagos_insertar():
    from models.models import PagoModel, Pago
    d = request.json or {}
    p = Pago(**{k: v for k, v in d.items() if k in Pago.__dataclass_fields__})
    new_id = PagoModel().insertar(p)
    return _ok(id=new_id) if new_id else _err("Error")

@app.delete("/api/v1/pagos/<int:paid>")
def pagos_eliminar(paid):
    from models.models import PagoModel
    ok = PagoModel().eliminar(paid)
    return _ok() if ok else _err("Error")

@app.get("/api/v1/pedidos/<int:pid>/pagos/total")
def pagos_total(pid):
    from models.models import PagoModel
    return _ok(total=PagoModel().get_total_pagado(pid))


# ─── INSUMOS ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/insumos")
def insumos_get_all():
    from models.models import InsumoModel
    return _ok(InsumoModel().get_all())

@app.post("/api/v1/insumos")
def insumos_insertar():
    from models.models import InsumoModel, Insumo
    d = request.json or {}
    i = Insumo(**{k: v for k, v in d.items() if k in Insumo.__dataclass_fields__})
    new_id = InsumoModel().insertar(i)
    return _ok(id=new_id) if new_id else _err("Error")

@app.put("/api/v1/insumos/<int:iid>")
def insumos_actualizar(iid):
    from models.models import InsumoModel, Insumo
    d = request.json or {}
    d["id"] = iid
    i = Insumo(**{k: v for k, v in d.items() if k in Insumo.__dataclass_fields__})
    ok = InsumoModel().actualizar(i)
    return _ok() if ok else _err("Error")

@app.delete("/api/v1/insumos/<int:iid>")
def insumos_eliminar(iid):
    from models.models import InsumoModel
    ok = InsumoModel().eliminar(iid)
    return _ok() if ok else _err("Error")


# ─── CONFIG ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/config/<clave>")
def config_get(clave):
    from models.config_model import ConfigModel
    return _ok(valor=ConfigModel().get(clave))

@app.put("/api/v1/config/<clave>")
def config_set(clave):
    from models.config_model import ConfigModel
    valor = (request.json or {}).get("valor", "")
    ok = ConfigModel().set(clave, valor)
    return _ok() if ok else _err("Error")

@app.get("/api/v1/config")
def config_get_all():
    from models.config_model import ConfigModel
    return _ok(ConfigModel().get_datos_imprenta())

@app.put("/api/v1/config")
def config_set_all():
    from models.config_model import ConfigModel
    datos = request.json or {}
    ok = ConfigModel().set_datos_imprenta(datos)
    return _ok() if ok else _err("Error")


# ─── USUARIOS ─────────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/login")
def auth_login():
    from models.usuario_model import UsuarioModel
    d = request.json or {}
    usuario = UsuarioModel().autenticar(d.get("username",""), d.get("password",""))
    if usuario:
        return _ok(_dc_to_dict(usuario))
    return _err("Credenciales inválidas", 401)

@app.get("/api/v1/usuarios")
def usuarios_get_all():
    from models.usuario_model import UsuarioModel
    return _ok(UsuarioModel().get_all())

@app.post("/api/v1/usuarios")
def usuarios_insertar():
    from models.usuario_model import UsuarioModel, Usuario
    d = request.json or {}
    pwd = d.pop("password", "")
    u = Usuario(**{k: v for k, v in d.items() if k in Usuario.__dataclass_fields__})
    new_id = UsuarioModel().insertar(u, pwd)
    return _ok(id=new_id) if new_id else _err("Error (usuario duplicado?)")

@app.put("/api/v1/usuarios/<int:uid>")
def usuarios_actualizar(uid):
    from models.usuario_model import UsuarioModel, Usuario
    d = request.json or {}
    pwd = d.pop("password", "")
    d["id"] = uid
    u = Usuario(**{k: v for k, v in d.items() if k in Usuario.__dataclass_fields__})
    ok = UsuarioModel().actualizar(u, nueva_password=pwd)
    return _ok() if ok else _err("Error")

@app.get("/api/v1/usuarios/recordado")
def usuarios_recordado():
    from models.usuario_model import UsuarioModel
    u = UsuarioModel().get_usuario_recordado()
    return _ok(username=u)

@app.put("/api/v1/usuarios/recordar")
def usuarios_recordar():
    from models.usuario_model import UsuarioModel
    d = request.json or {}
    UsuarioModel().guardar_recordar(d.get("username",""), d.get("recordar", False))
    return _ok()


# ─── FACTURAS ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/facturas")
def facturas_get_all():
    from models.factura_model import FacturaModel
    limit = int(request.args.get("limit", 200))
    return _ok(FacturaModel().get_all_facturas(limit=limit))

@app.get("/api/v1/recibos")
def recibos_get_all():
    from models.factura_model import ReciboModel
    limit = int(request.args.get("limit", 200))
    return _ok(ReciboModel().get_all_recibos(limit=limit))

@app.get("/api/v1/facturas/cliente/<int:cid>")
def facturas_por_cliente(cid):
    from models.factura_model import FacturaModel
    return _ok(FacturaModel().get_by_cliente(cid))

@app.get("/api/v1/facturas/pedido/<int:pid>")
def facturas_por_pedido(pid):
    from models.factura_model import FacturaModel
    return _ok(FacturaModel().get_by_pedido(pid))

@app.get("/api/v1/facturas/<int:fid>")
def factura_get_by_id(fid):
    from models.factura_model import FacturaModel
    f = FacturaModel().get_by_id(fid)
    return _ok(f) if f else _err("Not found", 404)

@app.post("/api/v1/facturas")
def facturas_insertar():
    from models.factura_model import FacturaModel, Factura
    d = request.json or {}
    f = Factura(**{k: v for k, v in d.items() if k in Factura.__dataclass_fields__})
    new_id = FacturaModel().insertar(f)
    return _ok(id=new_id) if new_id else _err("Error")

@app.patch("/api/v1/facturas/<int:fid>/cae")
def facturas_actualizar_cae(fid):
    from models.factura_model import FacturaModel
    d = request.json or {}
    ok = FacturaModel().actualizar_cae(fid, d.get("nro",""), d.get("cae",""),
                                       d.get("cae_vto",""), d.get("estado",""))
    return _ok() if ok else _err("Error")

@app.patch("/api/v1/facturas/<int:fid>/email")
def facturas_email(fid):
    from models.factura_model import FacturaModel
    ok = FacturaModel().marcar_email_enviado(fid)
    return _ok() if ok else _err("Error")


# ─── RECIBOS ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/recibos/nro_nuevo")
def recibo_nro_nuevo():
    from models.factura_model import ReciboModel
    return _ok(nro=ReciboModel().generar_nro())

@app.get("/api/v1/recibos/cliente/<int:cid>")
def recibos_por_cliente(cid):
    from models.factura_model import ReciboModel
    return _ok(ReciboModel().get_by_cliente(cid))

@app.post("/api/v1/recibos")
def recibos_insertar():
    from models.factura_model import ReciboModel, Recibo
    d = request.json or {}
    r = Recibo(**{k: v for k, v in d.items() if k in Recibo.__dataclass_fields__})
    new_id = ReciboModel().insertar(r)
    return _ok(id=new_id) if new_id else _err("Error")

@app.patch("/api/v1/recibos/<int:rid>/email")
def recibos_email(rid):
    from models.factura_model import ReciboModel
    ok = ReciboModel().marcar_email(rid)
    return _ok() if ok else _err("Error")


# ─── REPORTES ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/reportes/ventas")
def rep_ventas():
    from controllers.reporte_controller import ReporteController
    anio = int(request.args.get("anio", 2025))
    mes  = int(request.args.get("mes", 1))
    return _ok(ReporteController().ventas_por_dia_mes(anio, mes))

@app.get("/api/v1/reportes/balance")
def rep_balance():
    from controllers.reporte_controller import ReporteController
    return _ok(ReporteController().balance_general())

@app.get("/api/v1/reportes/productos")
def rep_productos():
    from controllers.reporte_controller import ReporteController
    anio = int(request.args.get("anio", 2025))
    mes  = int(request.args.get("mes", 1))
    return _ok(ReporteController().productos_mas_vendidos(anio, mes))

@app.get("/api/v1/reportes/cuenta_corriente/<int:cid>")
def rep_cuenta_corriente(cid):
    from controllers.reporte_controller import ReporteController
    return _ok(ReporteController().pedidos_cuenta_corriente(cid))


# ─── Iniciar servidor ────────────────────────────────────────────────────────

def start_server(port: int = 7432, api_key: str = "") -> threading.Thread:
    """
    Arranca Flask en un hilo daemon.
    Retorna el hilo (ya iniciado).
    """
    global _api_key
    _api_key = api_key

    def _run():
        import socket as _socket
        # Bind a 0.0.0.0 para aceptar conexiones de toda la LAN
        app.run(host="0.0.0.0", port=port, debug=False,
                use_reloader=False, threaded=True)

    t = threading.Thread(target=_run, daemon=True, name="FlaskServer")
    t.start()
    return t


def is_running() -> bool:
    """Verifica si el servidor ya está escuchando en el puerto."""
    import socket
    from network.net_config import get_port
    try:
        with socket.create_connection(("127.0.0.1", get_port()), timeout=0.5):
            return True
    except OSError:
        return False
