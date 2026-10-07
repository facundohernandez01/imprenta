"""
network/net_config.py
─────────────────────
Configuración de red guardada en JSON local (por PC).
"""
import json
import os
import secrets
from pathlib import Path
from typing import Optional

_CONFIG_DIR  = Path(os.environ.get("APPDATA", Path.home())) / "ImprentaPro"
NET_CFG_FILE = _CONFIG_DIR / "net_config.json"

MODO_LOCAL  = "local"   # DB local, sin API
MODO_SERVER = "server"  # DB local + API Flask activa
MODO_CLIENT = "client"  # Sin DB, consume API remota

DEFAULT_PORT = 7432      # Puerto arbitrario alto, poco probable que esté usado
API_PREFIX   = "/api/v1"


def _defaults() -> dict:
    return {
        "modo":       MODO_LOCAL,
        "server_ip":  "",
        "server_port": DEFAULT_PORT,
        "api_key":    "",           # secreto compartido para autenticar clientes
    }


def cargar() -> dict:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not NET_CFG_FILE.exists():
        return _defaults()
    try:
        with open(NET_CFG_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        cfg = _defaults()
        cfg.update(d)
        return cfg
    except Exception:
        return _defaults()


def guardar(cfg: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(NET_CFG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_modo() -> str:
    return cargar().get("modo", MODO_LOCAL)


def get_server_url() -> str:
    cfg = cargar()
    ip   = cfg.get("server_ip", "127.0.0.1")
    port = cfg.get("server_port", DEFAULT_PORT)
    return f"http://{ip}:{port}{API_PREFIX}"


def get_api_key() -> str:
    return cargar().get("api_key", "")


def generar_api_key() -> str:
    """Genera una clave API aleatoria de 32 chars."""
    return secrets.token_hex(16)


def es_server_o_local() -> bool:
    return get_modo() in (MODO_LOCAL, MODO_SERVER)


def get_port() -> int:
    return int(cargar().get("server_port", DEFAULT_PORT))
