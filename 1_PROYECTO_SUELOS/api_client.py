# -*- coding: utf-8 -*-
"""
GeoLab - Cliente de la API (Laravel + MySQL)

Guarda cada informe en la base de datos `suelos_db` a traves de la API.
- La sesion (token) se guarda en  %APPDATA%\\GeoLab\\config.json  (NUNCA la contrasena).
- Si no hay internet o el servidor esta apagado, el informe queda en una cola local
  (pendientes.json) y se reenvia solo en la siguiente oportunidad.
"""

import datetime
import json
import math
import os
import threading
import uuid

import requests

URL_POR_DEFECTO = "http://127.0.0.1:8000/api"   # php artisan serve  (o http://suelos-api.test/api con Laragon)
TIMEOUT = 15
MAX_PENDIENTES = 200

DIR_CONFIG = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "GeoLab")
ARCHIVO_CONFIG = os.path.join(DIR_CONFIG, "config.json")
ARCHIVO_PENDIENTES = os.path.join(DIR_CONFIG, "pendientes.json")

_lock = threading.Lock()


class ErrorAPI(Exception):
    """Error legible para mostrar al usuario."""


# ------------------------------------------------------------------
# Configuracion local
# ------------------------------------------------------------------
def _leer_json(ruta, defecto):
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def _escribir_json(ruta, datos):
    os.makedirs(DIR_CONFIG, exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def cargar_config():
    cfg = _leer_json(ARCHIVO_CONFIG, {})
    cfg.setdefault("url", URL_POR_DEFECTO)
    cfg.setdefault("token", "")
    cfg.setdefault("email", "")
    cfg.setdefault("nombre", "")
    return cfg


def guardar_config(cfg):
    with _lock:
        _escribir_json(ARCHIVO_CONFIG, cfg)


def normalizar_url(url):
    url = (url or "").strip().rstrip("/")
    if not url:
        return URL_POR_DEFECTO
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    if not url.endswith("/api"):
        url += "/api"
    return url


def hay_sesion():
    return bool(cargar_config().get("token"))


def texto_estado():
    cfg = cargar_config()
    n = len(_leer_json(ARCHIVO_PENDIENTES, []))
    if cfg["token"]:
        base = f"☁ {cfg['email'] or 'sesión activa'}"
    else:
        base = "☁ Sin sesión"
    return f"{base}  •  {n} pendiente(s)" if n else base


# ------------------------------------------------------------------
# Limpieza de datos para JSON
# ------------------------------------------------------------------
def limpiar_json(obj, _nivel=0):
    """Convierte cualquier estructura de la app en algo serializable a JSON."""
    if _nivel > 12:
        return None
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): limpiar_json(v, _nivel + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [limpiar_json(v, _nivel + 1) for v in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if hasattr(obj, "item"):            # numpy escalar
        try:
            return limpiar_json(obj.item(), _nivel + 1)
        except Exception:
            pass
    if hasattr(obj, "tolist"):          # numpy array
        try:
            return limpiar_json(obj.tolist(), _nivel + 1)
        except Exception:
            pass
    return str(obj)


# ------------------------------------------------------------------
# Llamadas HTTP
# ------------------------------------------------------------------
def _mensaje_error(resp):
    try:
        data = resp.json()
    except ValueError:
        return f"Error {resp.status_code} del servidor."
    if isinstance(data, dict):
        if data.get("errors"):
            primero = next(iter(data["errors"].values()))
            return primero[0] if isinstance(primero, list) and primero else str(primero)
        if data.get("message"):
            return str(data["message"])
    return f"Error {resp.status_code} del servidor."


def _post(ruta, cuerpo, token=None, url=None):
    cfg = cargar_config()
    base = normalizar_url(url or cfg["url"])
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.post(f"{base}{ruta}", json=cuerpo, headers=headers, timeout=TIMEOUT)


def _guardar_sesion(resp_json, email, url):
    cfg = cargar_config()
    cfg["url"] = normalizar_url(url or cfg["url"])
    cfg["token"] = resp_json.get("token", "")
    cfg["email"] = email
    cfg["nombre"] = (resp_json.get("user") or {}).get("name", "")
    guardar_config(cfg)


def login(email, password, url=None):
    try:
        r = _post("/login", {"email": email, "password": password, "dispositivo": "escritorio"}, url=url)
    except requests.RequestException as e:
        raise ErrorAPI(f"No se pudo conectar con el servidor.\n¿Está encendido Laragon y 'php artisan serve'?\n\n{e.__class__.__name__}")
    if r.status_code != 200:
        raise ErrorAPI(_mensaje_error(r))
    _guardar_sesion(r.json(), email, url)
    enviar_pendientes()


def registrar(nombre, email, password, codigo="", url=None):
    cuerpo = {"name": nombre, "email": email, "password": password, "dispositivo": "escritorio"}
    if codigo:
        cuerpo["codigo"] = codigo
    try:
        r = _post("/register", cuerpo, url=url)
    except requests.RequestException as e:
        raise ErrorAPI(f"No se pudo conectar con el servidor.\n\n{e.__class__.__name__}")
    if r.status_code not in (200, 201):
        raise ErrorAPI(_mensaje_error(r))
    _guardar_sesion(r.json(), email, url)


def cerrar_sesion():
    cfg = cargar_config()
    if cfg["token"]:
        try:
            _post("/logout", {}, token=cfg["token"])
        except requests.RequestException:
            pass
    cfg["token"] = ""
    guardar_config(cfg)


# ------------------------------------------------------------------
# Informes
# ------------------------------------------------------------------
def nuevo_payload(proyecto, muestra, ensayo, tipo, archivo_pdf, datos, resultados, clasificacion=None):
    return limpiar_json({
        "uid": uuid.uuid4().hex,
        "proyecto": proyecto or "Proyecto sin título",
        "muestra": muestra or "",
        "ensayo": ensayo,                  # humedad, volumetrico, ..., consolidado
        "tipo": tipo,                      # individual | consolidado
        "origen": "escritorio",
        "archivo_pdf": archivo_pdf or "",
        "datos": datos or {},
        "resultados": resultados or {},
        "clasificacion": clasificacion,
    })


def _poner_en_cola(payload):
    with _lock:
        cola = _leer_json(ARCHIVO_PENDIENTES, [])
        if not any(p.get("uid") == payload.get("uid") for p in cola):
            cola.append(payload)
        _escribir_json(ARCHIVO_PENDIENTES, cola[-MAX_PENDIENTES:])


def _enviar(payload, token):
    return _post("/informes", payload, token=token)


def guardar_informe(payload):
    """Devuelve (estado, mensaje). estado: ok | pendiente | sin_sesion | error"""
    cfg = cargar_config()
    if not cfg["token"]:
        _poner_en_cola(payload)
        return "sin_sesion", "Informe guardado localmente. Inicie sesión en ☁ Servidor para subirlo a la base de datos."
    try:
        r = _enviar(payload, cfg["token"])
    except requests.RequestException:
        _poner_en_cola(payload)
        return "pendiente", "Sin conexión con el servidor. El informe quedó en cola y se enviará después."
    if r.status_code in (200, 201):
        enviar_pendientes()
        return "ok", "Informe guardado en la base de datos."
    if r.status_code == 401:
        cfg["token"] = ""
        guardar_config(cfg)
        _poner_en_cola(payload)
        return "sin_sesion", "La sesión expiró. Inicie sesión de nuevo en ☁ Servidor; el informe quedó en cola."
    if r.status_code >= 500:
        _poner_en_cola(payload)
        return "pendiente", "El servidor tuvo un error. El informe quedó en cola."
    return "error", _mensaje_error(r)


def enviar_pendientes():
    """Reenvia la cola local. Devuelve (enviados, quedan)."""
    cfg = cargar_config()
    cola = _leer_json(ARCHIVO_PENDIENTES, [])
    if not cola or not cfg["token"]:
        return 0, len(cola)
    enviados, quedan = 0, []
    for i, p in enumerate(cola):
        try:
            r = _enviar(p, cfg["token"])
        except requests.RequestException:
            quedan = cola[i:]
            break
        if r.status_code in (200, 201):
            enviados += 1
        elif r.status_code == 401:
            quedan = cola[i:]
            break
        elif r.status_code >= 500:
            quedan.append(p)
        # 422 u otros: dato invalido, se descarta para no atascar la cola
    with _lock:
        _escribir_json(ARCHIVO_PENDIENTES, quedan)
    return enviados, len(quedan)


def guardar_en_segundo_plano(payload, cola_resultados):
    """Ejecuta guardar_informe en un hilo y deja (estado, mensaje) en una queue.Queue."""
    def tarea():
        try:
            cola_resultados.put(guardar_informe(payload))
        except Exception as e:                      # nunca romper la app por la red
            cola_resultados.put(("error", f"No se pudo guardar: {e}"))
    threading.Thread(target=tarea, daemon=True).start()
