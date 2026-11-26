# -*- coding: utf-8 -*-
"""
Prueba rápida de la API de GeoLab (Laravel).
Antes de ejecutarla: en Laragon deje corriendo   php artisan serve   dentro de C:\\laragon\\www\\Suelos-api
Uso:   python probar_api.py
"""
import os
import sys
import uuid

import requests

BASE = os.environ.get("GEOLAB_API", "http://127.0.0.1:8000/api")
EMAIL = "jose@test.com"      # <- cambie por su cuenta
PASSWORD = "123456"          # <- cambie por su contraseña
H = {"Accept": "application/json"}


def mostrar(titulo, r):
    try:
        cuerpo = r.json()
    except ValueError:
        cuerpo = r.text[:200]
    print(f"{titulo}: {r.status_code} {cuerpo}")


try:
    # 1. Iniciar sesión (si la cuenta no existe, se intenta crear; la contraseña nueva debe tener 8+ caracteres)
    r = requests.post(f"{BASE}/login", json={"email": EMAIL, "password": PASSWORD, "dispositivo": "prueba"}, headers=H, timeout=10)
    if r.status_code == 401:
        r = requests.post(f"{BASE}/register", json={"name": "Jose", "email": EMAIL, "password": PASSWORD, "dispositivo": "prueba"}, headers=H, timeout=10)
        mostrar("Registro", r)
    else:
        mostrar("Login", r)
    token = r.json().get("token") if r.status_code in (200, 201) else None
    if not token:
        sys.exit("\nNo se obtuvo token: revise el correo/contraseña de este archivo (o el código de registro).")
    H["Authorization"] = f"Bearer {token}"

    # 2. Enviar un informe de prueba (con 'uid', si se repite no se duplica)
    informe = {
        "uid": uuid.uuid4().hex,
        "proyecto": "Prueba",
        "muestra": "M-00",
        "ensayo": "humedad",
        "tipo": "individual",
        "origen": "escritorio",
        "archivo_pdf": "Informe_Humedad_M-00.pdf",
        "datos": {"humedad": 12.5},
        "resultados": {"promedio": 12.5},
    }
    mostrar("Informe", requests.post(f"{BASE}/informes", json=informe, headers=H, timeout=10))

    # 3. Listar mis informes
    r = requests.get(f"{BASE}/informes", headers=H, timeout=10)
    lista = r.json().get("data", []) if r.status_code == 200 else []
    print(f"Lista: {r.status_code}, {len(lista)} informe(s) en esta página")
    for i in lista[:5]:
        print("  -", i.get("id"), i.get("proyecto"), i.get("muestra"), i.get("ensayo"), i.get("created_at"))

except requests.ConnectionError:
    sys.exit("\nNo se pudo conectar. ¿Está corriendo 'php artisan serve' (y MySQL en Laragon)?")
