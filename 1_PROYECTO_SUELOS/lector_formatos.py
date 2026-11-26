# -*- coding: utf-8 -*-
"""
GeoLab - Lector de hojas escaneadas (foto o PDF, incluso manuscritas)

Flujo:  archivo  ->  servidor Laravel (/api/leer-formato, con IA)  ->  JSON  ->  formulario del programa.
La clave de la IA vive solo en el servidor; aquí se necesita haber iniciado sesión en ☁ Servidor.

Además verifica las sumas de la propia hoja (la suma de masas retenidas debe cuadrar con la
masa lavada y seca) para avisar si algún número manuscrito pudo leerse mal.
"""

import base64
import io
import os

import requests

import api_client

LIMITE_PDF = 15 * 1024 * 1024        # bytes (el PDF viaja en base64, ~33 % más grande)
LADO_MAX_IMAGEN = 2000                # px: suficiente para leer números a mano y viaja rápido
TIMEOUT_LECTURA = 180                 # la lectura con IA puede tardar


# ------------------------------------------------------------------
# Preparar el archivo
# ------------------------------------------------------------------
def preparar_archivo(ruta):
    """Devuelve (base64, mediaType). Reduce las fotos grandes y respeta la rotación del celular."""
    if not os.path.isfile(ruta):
        raise api_client.ErrorAPI("No se encontró el archivo seleccionado.")
    ext = os.path.splitext(ruta)[1].lower()

    if ext == ".pdf":
        if os.path.getsize(ruta) > LIMITE_PDF:
            raise api_client.ErrorAPI("El PDF pesa demasiado (máx. ~4.5 MB). Escanee en menor resolución o use una foto.")
        with open(ruta, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii"), "application/pdf"

    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"):
        raise api_client.ErrorAPI("Formato no admitido. Use PDF, JPG o PNG.")

    try:
        from PIL import Image, ImageOps
        img = ImageOps.exif_transpose(Image.open(ruta))
        img = img.convert("RGB")
        img.thumbnail((LADO_MAX_IMAGEN, LADO_MAX_IMAGEN))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"
    except ImportError:
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            raise api_client.ErrorAPI("Instale 'pillow' para leer este tipo de imagen (pip install pillow).")
        if os.path.getsize(ruta) > LIMITE_PDF:
            raise api_client.ErrorAPI("La imagen pesa demasiado. Instale 'pillow' (pip install pillow) para reducirla automáticamente.")
        with open(ruta, "rb") as f:
            tipo = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
            return base64.b64encode(f.read()).decode("ascii"), tipo
    except Exception as e:
        raise api_client.ErrorAPI(f"No se pudo abrir la imagen: {e}")


# ------------------------------------------------------------------
# Llamada al servidor
# ------------------------------------------------------------------
def leer_formato(ruta, ensayo="granulometria"):
    """Envía el archivo al servidor y devuelve el dict con los datos leídos."""
    cfg = api_client.cargar_config()
    if not cfg["token"]:
        raise api_client.ErrorAPI("Para usar el lector inicie sesión en ☁ Servidor.")
    datos_b64, tipo = preparar_archivo(ruta)
    base = api_client.normalizar_url(cfg["url"])
    try:
        r = requests.post(
            f"{base}/leer-formato",
            json={"data": datos_b64, "mediaType": tipo, "ensayo": ensayo},
            headers={"Accept": "application/json", "Authorization": f"Bearer {cfg['token']}"},
            timeout=TIMEOUT_LECTURA,
        )
    except requests.Timeout:
        raise api_client.ErrorAPI("La lectura tardó demasiado. Intente de nuevo o use una imagen más liviana.")
    except requests.RequestException:
        raise api_client.ErrorAPI("No se pudo conectar con el servidor.\n¿Está encendido Laragon y 'php artisan serve'?")

    if r.status_code == 401:
        cfg["token"] = ""
        api_client.guardar_config(cfg)
        raise api_client.ErrorAPI("La sesión expiró. Inicie sesión de nuevo en ☁ Servidor.")
    if r.status_code == 429:
        raise api_client.ErrorAPI("Se alcanzó el límite de lecturas por hora. Espere un momento e intente de nuevo.")
    if r.status_code != 200:
        raise api_client.ErrorAPI(api_client._mensaje_error(r))
    try:
        datos = r.json()
    except ValueError:
        raise api_client.ErrorAPI("El servidor devolvió una respuesta no válida.")
    if not isinstance(datos, dict):
        raise api_client.ErrorAPI("El servidor devolvió una respuesta no válida.")
    return datos


# ------------------------------------------------------------------
# Verificación de las sumas de la hoja
# ------------------------------------------------------------------
def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _suma(tamices, col):
    vals = [_num(t.get(col)) for t in tamices.values() if isinstance(t, dict)]
    vals = [v for v in vals if v is not None]
    return (sum(vals), len(vals)) if vals else (None, 0)


def validar_granulometria(d):
    """
    Revisa que lo leído sea coherente. Devuelve una lista de (nivel, texto), nivel = 'ok' | 'aviso'.
    Un 'aviso' no bloquea nada: solo indica qué conviene revisar contra la hoja original.
    """
    out = []
    metodo = d.get("metodo") or ""
    tam = d.get("tamices") or {}
    sec = d.get("secado") or {}
    enc = d.get("encabezado") or {}
    s1, n1 = _suma(tam, "m1")
    s2, n2 = _suma(tam, "m2")

    if n1 + n2 == 0:
        return [("aviso", "No se leyó ningún valor de masa retenida. Revise que la foto sea nítida y esté completa.")]

    if metodo == "a-compuesto":
        g1, g2, g3 = (_num(sec.get(k)) for k in ("g1", "g2", "g3"))
        f1, f2, f3 = (_num(sec.get(k)) for k in ("f1", "f2", "f3"))

        for nombre, a, b, txt in (("gruesa", g1, g2, "g1 (húmeda) < g2 (seca)"), ("gruesa", g2, g3, "g2 (seca) < g3 (lavada)"),
                                  ("fina", f1, f2, "f1 (húmeda) < f2 (seca)"), ("fina", f2, f3, "f2 (seca) < f3 (lavada)")):
            if a is not None and b is not None and a < b:
                out.append(("aviso", f"Parte {nombre}: {txt}. La masa debería disminuir al secar y lavar; revise esos números."))

        if s1 is not None and g3 is not None:
            tol = max(1.5, 0.0002 * g3)       # la hoja real cuadra exacto; así se detectan dígitos mal leídos
            dif = abs(s1 - g3)
            if dif <= tol:
                out.append(("ok", f"Parte gruesa: la suma de retenidos ({s1:.1f} g) coincide con la masa lavada y seca ({g3:.1f} g)."))
            else:
                out.append(("aviso", f"Parte gruesa: la suma de retenidos ({s1:.1f} g) NO coincide con la masa lavada y seca "
                                     f"({g3:.1f} g); diferencia {dif:.1f} g. Revise la columna M-1 (o g3)."))
        if s2 is not None and f3 is not None:
            tol = max(0.3, 0.0005 * f3)
            dif = abs(s2 - f3)
            if dif <= tol:
                out.append(("ok", f"Parte fina: la suma de retenidos ({s2:.1f} g) coincide con la masa lavada y seca ({f3:.1f} g)."))
            else:
                out.append(("aviso", f"Parte fina: la suma de retenidos ({s2:.1f} g) NO coincide con la masa lavada y seca "
                                     f"({f3:.1f} g); diferencia {dif:.1f} g. Revise la columna M-2 (o f3)."))

        mt, mg, mf = (_num(enc.get(k)) for k in ("masa-total", "masa-gruesa", "masa-fina"))
        if mt is not None and mg is not None and mf is not None:
            if abs(mt - (mg + mf)) <= max(1.5, 0.0005 * mt):
                out.append(("ok", f"Masa total ({mt:.1f} g) = parte gruesa + parte fina."))
            else:
                out.append(("aviso", f"La masa total ({mt:.1f} g) no es igual a parte gruesa + parte fina ({mg + mf:.1f} g). Revise el encabezado."))
        if mg is not None and g1 is not None and abs(mg - g1) > 1.0:
            out.append(("aviso", f"La masa de la parte gruesa del encabezado ({mg:.1f} g) difiere de g1 ({g1:.1f} g)."))
    else:
        w0 = _num(d.get("masa_lavada"))
        w1 = _num(d.get("masa_total"))
        if w1 is not None and w0 is not None and w0 > w1:
            out.append(("aviso", "La masa lavada es mayor que la masa seca total; revise esos dos valores."))
        if s1 is not None and w0 is not None:
            tol = max(2.0, 0.002 * w0)
            dif = abs(s1 - w0)
            if dif <= tol:
                out.append(("ok", f"La suma de retenidos ({s1:.1f} g) coincide con la masa seca lavada ({w0:.1f} g)."))
            else:
                out.append(("aviso", f"La suma de retenidos ({s1:.1f} g) difiere de la masa seca lavada ({w0:.1f} g) en {dif:.1f} g. "
                                     "Puede deberse a finos perdidos por lavado o a un número mal leído; compárelo con la hoja."))
    return out
