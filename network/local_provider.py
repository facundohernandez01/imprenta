"""
network/local_provider.py
─────────────────────────
Provider LOCAL/SERVER: delega en los modelos con QSqlQuery existentes.
Cero cambio de lógica de negocio.
"""
from network.data_provider import BaseProvider


def _filtros_guardados_get() -> list:
    """Obtiene filtros guardados de la DB local."""
    import json
    from models.config_model import ConfigModel
    raw = ConfigModel().get("filtros_guardados_pedidos", "[]")
    try:
        return json.loads(raw)
    except Exception:
        return []

def _filtros_guardados_set(filtros: list) -> None:
    import json
    from models.config_model import ConfigModel
    ConfigModel().set("filtros_guardados_pedidos", json.dumps(filtros))


class LocalProvider(BaseProvider):
    """
    Instancia todos los modelos existentes y los expone
    con la misma interfaz que HttpProvider.
    """
    def __init__(self):
        from models.cliente_model import ClienteModel
        from models.pedido_model import PedidoModel
        from models.models import (
            PedidoDetalleModel, ProductoModel, TipoTrabajoModel,
            PagoModel, InsumoModel
        )
        from models.config_model import ConfigModel
        from models.usuario_model import UsuarioModel
        from models.factura_model import FacturaModel, ReciboModel
        from controllers.reporte_controller import ReporteController

        self.clientes  = ClienteModel()
        self.pedidos   = PedidoModel()
        self.detalle   = PedidoDetalleModel()
        self.productos = ProductoModel()
        self.tipos     = TipoTrabajoModel()
        self.pagos     = PagoModel()
        self.insumos   = InsumoModel()
        self.config    = ConfigModel()
        self.usuarios  = _LocalUsuarioRepo()
        self.facturas  = FacturaModel()
        self.recibos   = ReciboModel()
        self.reportes  = ReporteController()


class _LocalUsuarioRepo:
    """
    Wrapper de UsuarioModel que mantiene la sesión en memoria
    pero delega todo a la clase original.
    """
    def __init__(self):
        from models.usuario_model import UsuarioModel
        self._m = UsuarioModel()

    def autenticar(self, username: str, password: str):
        return self._m.autenticar(username, password)

    def get_all(self):
        return self._m.get_all()

    def insertar(self, u, password: str) -> int:
        return self._m.insertar(u, password)

    def actualizar(self, u, nueva_password: str = "") -> bool:
        return self._m.actualizar(u, nueva_password)

    def guardar_recordar(self, username: str, recordar: bool) -> None:
        self._m.guardar_recordar(username, recordar)

    def get_usuario_recordado(self):
        return self._m.get_usuario_recordado()
