# -*- coding: utf-8 -*-
"""
GeoLab - Sistema de Mecánica de Suelos (FIGMM / UNI)
Aplicación de Escritorio Profesional (CustomTkinter + Matplotlib + ReportLab)
Sincronizada con la versión Web de GeoLab (Todos los 7 Ensayos de Laboratorio)
"""

import os
import sys
import math
import datetime
import io
import queue
import threading
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import customtkinter as ctk

# Conexión con la base de datos (API Laravel + MySQL). Si falta la librería 'requests',
# la aplicación sigue funcionando normalmente, solo sin guardar en la base de datos.
try:
    import api_client
except Exception:
    api_client = None

# Lector de hojas escaneadas (foto/PDF -> formulario). Requiere 'requests' y, para fotos, 'pillow'.
try:
    import lector_formatos
except Exception:
    lector_formatos = None

# Matplotlib para gráficos interactivos y exportables
import matplotlib
matplotlib.use('Agg') # backend base seguro
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as patches

# ReportLab para informes oficiales en PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Recuerda cuál fue el último PDF generado con éxito (para guardarlo en la base de datos)
ESTADO_PDF = {"ultimo": None}
_SimpleDocTemplateBase = SimpleDocTemplate

class SimpleDocTemplate(_SimpleDocTemplateBase):
    def build(self, *args, **kwargs):
        resultado = super().build(*args, **kwargs)
        ESTADO_PDF["ultimo"] = getattr(self, "filename", None)
        return resultado

# Configuración de CustomTkinter
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ===================================================================
# PALETA OFICIAL FORMAL DE LABORATORIO (IDÉNTICA A LA VERSIÓN WEB)
# ===================================================================
PRIMARY = "#1F3A5F"          # Azul marino formal de laboratorio
PRIMARY_HOVER = "#162C49"
PRIMARY_LIGHT = "#EEF1F6"
PRIMARY_BORDER = "#C5CEDB"

ACCENT_RED = "#7F1D1D"        # Advertencias y alertas normativas
ACCENT_RED_HOVER = "#651616"
ACCENT_RED_LIGHT = "#F8EEEE"
ACCENT_RED_BORDER = "#E2C6C6"

ACCENT_GREEN = "#2F5D46"      # Estado calculado / conforme
ACCENT_GREEN_HOVER = "#244A37"
ACCENT_GREEN_LIGHT = "#EDF3EF"
ACCENT_GREEN_BORDER = "#C3D6CB"

NEUTRAL_DARK = "#111827"
NEUTRAL_HEADING = "#1B2230"
NEUTRAL_BODY = "#374151"
NEUTRAL_MUTED = "#6B7280"

FONDO = "#F3F4F6"
CARD_BG = "#FFFFFF"
CARD_BG_ALT = "#F7F8FA"
BORDER_COLOR = "#CFD4DC"
BORDER_SUBTLE = "#E3E6EB"

# Datos de proyecto predeterminados de la versión Web
DEFAULT_PROYECTO = {
    "proyecto": "Carretera Central Km 45",
    "muestra": "M-01",
    "procedencia": "Calicata C-01 (1.50 m)",
    "material": "Arcilla limosa marrón de media plasticidad",
    "ensayado": "Ing. Laboratorista",
    "fecha": datetime.datetime.now().strftime("%d/%m/%Y"),
    "solicitante": "Dirección Regional de Transportes",
    "ubicacion": "Lima - Perú",
    "cip": "CIP N° 285490",
    "firmante": "Ing. Responsable de Laboratorio",
}

# ===================================================================
# TABLA OFICIAL DE DENSIDAD DEL AGUA Y FACTOR K (ASTM D854)
# ===================================================================
TABLA_DENSIDAD_AGUA = [
    (15.0, 0.99911, 1.00090), (15.5, 0.99903, 1.00082), (16.0, 0.99894, 1.00073),
    (16.5, 0.99886, 1.00065), (17.0, 0.99877, 1.00056), (17.5, 0.99868, 1.00047),
    (18.0, 0.99859, 1.00038), (18.5, 0.99850, 1.00029), (19.0, 0.99840, 1.00019),
    (19.5, 0.99830, 1.00009), (20.0, 0.99820, 0.99999), (20.5, 0.99810, 0.99989),
    (21.0, 0.99799, 0.99978), (21.5, 0.99788, 0.99967), (22.0, 0.99777, 0.99956),
    (22.5, 0.99765, 0.99944), (23.0, 0.99754, 0.99933), (23.5, 0.99742, 0.99921),
    (24.0, 0.99730, 0.99909), (24.5, 0.99717, 0.99896), (25.0, 0.99705, 0.99884),
    (25.5, 0.99692, 0.99871), (26.0, 0.99679, 0.99858), (26.5, 0.99665, 0.99844),
    (27.0, 0.99652, 0.99831), (27.5, 0.99638, 0.99817), (28.0, 0.99624, 0.99803),
    (28.5, 0.99610, 0.99789), (29.0, 0.99595, 0.99773), (29.5, 0.99580, 0.99758),
    (30.0, 0.99565, 0.99743)
]

def obtener_propiedades_agua(temp):
    try:
        t = max(15.0, min(30.0, float(temp)))
    except (ValueError, TypeError):
        t = 20.0
    for i in range(len(TABLA_DENSIDAD_AGUA) - 1):
        t1, r1, k1 = TABLA_DENSIDAD_AGUA[i]
        t2, r2, k2 = TABLA_DENSIDAD_AGUA[i+1]
        if t1 <= t <= t2:
            f = (t - t1) / (t2 - t1) if t2 != t1 else 0.0
            return r1 + f * (r2 - r1), k1 + f * (k2 - k1)
    return 0.99820, 1.00000

# ===================================================================
# JUEGO ESTÁNDAR DE TAMICES ASTM (ASTM D6913 / D422)
# ===================================================================
ASTM_SIEVES = [
    {"id": "3in", "nombre": '3"', "abertura": 75.000, "desc": "75.0 mm"},
    {"id": "2in", "nombre": '2"', "abertura": 50.000, "desc": "50.0 mm"},
    {"id": "1_5in", "nombre": '1 1/2"', "abertura": 37.500, "desc": "37.5 mm"},
    {"id": "1in", "nombre": '1"', "abertura": 25.000, "desc": "25.0 mm"},
    {"id": "3_4in", "nombre": '3/4"', "abertura": 19.000, "desc": "19.0 mm"},
    {"id": "1_2in", "nombre": '1/2"', "abertura": 12.500, "desc": "12.5 mm"},
    {"id": "3_8in", "nombre": '3/8"', "abertura": 9.500, "desc": "9.5 mm"},
    {"id": "1_4in", "nombre": '1/4"', "abertura": 6.300, "desc": "6.30 mm"},
    {"id": "n4", "nombre": "N° 4", "abertura": 4.750, "desc": "4.75 mm"},
    {"id": "n10", "nombre": "N° 10", "abertura": 2.000, "desc": "2.00 mm"},
    {"id": "n20", "nombre": "N° 20", "abertura": 0.850, "desc": "850 µm"},
    {"id": "n30", "nombre": "N° 30", "abertura": 0.600, "desc": "600 µm"},
    {"id": "n40", "nombre": "N° 40", "abertura": 0.425, "desc": "425 µm"},
    {"id": "n60", "nombre": "N° 60", "abertura": 0.250, "desc": "250 µm"},
    {"id": "n100", "nombre": "N° 100", "abertura": 0.150, "desc": "150 µm"},
    {"id": "n140", "nombre": "N° 140", "abertura": 0.106, "desc": "106 µm"},
    {"id": "n200", "nombre": "N° 200", "abertura": 0.075, "desc": "75 µm"},
    {"id": "pan", "nombre": "Platillo / Fondo", "abertura": 0.000, "desc": "Fondo"},
    {"id": "mmo", "nombre": "M - Mo (Lavado)", "abertura": 0.000, "desc": "Finos perdidos por lavado"},
]

# ===================================================================
# FUNCIONES MATEMÁTICAS Y ALGORITMOS GEOTÉCNICOS
# ===================================================================

def regresion_lineal(xs, ys):
    """Regresión por mínimos cuadrados y coeficiente R²."""
    n = len(xs)
    if n < 2:
        return 0.0, 0.0, 0.0
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xx = sum(x * x for x in xs)
    sum_yy = sum(y * y for y in ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    denom = (n * sum_xx - sum_x * sum_x)
    if abs(denom) < 1e-12:
        return 0.0, sum_y / n, 0.0
    m = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - m * sum_x) / n
    denom_r = (n * sum_xx - sum_x * sum_x) * (n * sum_yy - sum_y * sum_y)
    r2 = 0.0
    if denom_r > 1e-12:
        r2 = ((n * sum_xy - sum_x * sum_y) ** 2) / denom_r
    return m, b, r2

def regresion_parabolica(xs, ys):
    """Ajuste polinómico de 2do grado: y = a*x^2 + b*x + c"""
    n = len(xs)
    if n < 3:
        return None
    s_x = sum(xs)
    s_x2 = sum(x ** 2 for x in xs)
    s_x3 = sum(x ** 3 for x in xs)
    s_x4 = sum(x ** 4 for x in xs)
    s_y = sum(ys)
    s_xy = sum(x * y for x, y in zip(xs, ys))
    s_x2y = sum((x ** 2) * y for x, y in zip(xs, ys))

    # Matriz 3x3
    A = [
        [s_x4, s_x3, s_x2],
        [s_x3, s_x2, s_x],
        [s_x2, s_x, float(n)]
    ]
    B = [s_x2y, s_xy, s_y]

    def det3(m):
        return (
            m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
        )

    detA = det3(A)
    if abs(detA) < 1e-12:
        return None

    def repl(m, col, vals):
        m2 = [row[:] for row in m]
        for i in range(3):
            m2[i][col] = vals[i]
        return m2

    a = det3(repl(A, 0, B)) / detA
    b = det3(repl(A, 1, B)) / detA
    c = det3(repl(A, 2, B)) / detA

    y_mean = s_y / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((y - (a * x ** 2 + b * x + c)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0

    return a, b, c, r2

def interpolar_log(x0, x1, y0, y1, y_target):
    """Interpolación logarítmica para diámetros efectivos D (tamiz)."""
    if x0 <= 0 or x1 <= 0 or y0 == y1:
        return None
    log_x0 = math.log10(x0)
    log_x1 = math.log10(x1)
    f = (y_target - y0) / (y1 - y0)
    log_xt = log_x0 + f * (log_x1 - log_x0)
    return 10.0 ** log_xt

def fracciones_enteras(grava, arena, finos):
    """
    Ajusta fracciones a enteros cuya suma es exactamente 100% (criterio ASTM D2487).
    Algoritmo de mayor resto idéntico a la versión Web de GeoLab.
    """
    v = [float(grava or 0.0), float(arena or 0.0), float(finos or 0.0)]
    base = [math.floor(x) for x in v]
    faltan = int(round(sum(v))) - sum(base)
    orden = sorted(range(3), key=lambda i: v[i] - base[i], reverse=True)
    for k in range(min(max(0, faltan), 3)):
        base[orden[k]] += 1
    return {"grava": int(base[0]), "arena": int(base[1]), "finos": int(base[2])}

def ip_entero(ll, lp, ip=None):
    """
    Índice de Plasticidad como entero: IP = LL - LP con valores redondeados (ASTM D4318).
    """
    if ll is not None and lp is not None:
        return int(round(ll)) - int(round(lp))
    if ip is not None:
        return int(round(ip))
    return None

def clasificar_plasticidad(ll, ip):
    """
    Clasificación de plasticidad según carta de Casagrande (ASTM D2487 / D4318).
    Línea A: IP = 0.73 * (LL - 20)
    """
    if ll is None or ip is None:
        return None
    linea_a = 0.73 * (ll - 20.0)
    if 4.0 <= ip <= 7.0 and ip >= linea_a:
        grupo = "CL-ML"
    elif ip > linea_a and ip >= 4.0:
        grupo = "CL" if ll < 50.0 else "CH"
    else:
        grupo = "ML" if ll < 50.0 else "MH"

    nombres = {
        "CL": "Arcilla de baja plasticidad",
        "CH": "Arcilla de alta plasticidad",
        "ML": "Limo de baja plasticidad",
        "MH": "Limo de alta plasticidad",
        "CL-ML": "Limo arcilloso"
    }
    nombre = nombres.get(grupo, grupo)
    if ip < 7.0:
        nivel = "Baja plasticidad"
    elif ip <= 17.0:
        nivel = "Plasticidad media"
    else:
        nivel = "Alta plasticidad"
    return {"grupo": grupo, "nombre": nombre, "nivel": nivel, "linea_a": linea_a}

def clasificar_aashto(p10, p40, p200, ll, ip):
    """Clasificación AASHTO M 145 con Índice de Grupo (IG) y descripción de subrasante."""
    grupo = ""
    parcial = False
    if p200 <= 35.0:
        if p10 <= 50.0 and p40 <= 30.0 and p200 <= 15.0 and ip <= 6.0:
            grupo = "A-1-a"
        elif p40 <= 50.0 and p200 <= 25.0 and ip <= 6.0:
            grupo = "A-1-b"
        elif p40 >= 51.0 and p200 <= 10.0 and ip <= 0.0:
            grupo = "A-3"
        elif ll <= 40.0 and ip <= 10.0:
            grupo = "A-2-4"
        elif ll > 40.0 and ip <= 10.0:
            grupo = "A-2-5"
        elif ll <= 40.0 and ip > 10.0:
            grupo = "A-2-6"
            parcial = True
        else:
            grupo = "A-2-7"
            parcial = True
    else:
        if ll <= 40.0 and ip <= 10.0:
            grupo = "A-4"
        elif ll > 40.0 and ip <= 10.0:
            grupo = "A-5"
        elif ll <= 40.0 and ip > 10.0:
            grupo = "A-6"
        else:
            grupo = "A-7-5" if (ip <= ll - 30.0) else "A-7-6"

    ig = 0
    if grupo.startswith("A-4") or grupo.startswith("A-5") or grupo.startswith("A-6") or grupo.startswith("A-7") or parcial:
        termino2 = 0.01 * (p200 - 15.0) * (ip - 10.0)
        if parcial:
            calc_ig = termino2
        else:
            calc_ig = (p200 - 35.0) * (0.2 + 0.005 * (ll - 40.0)) + termino2
        ig = max(0, int(round(calc_ig)))

    desc_calidad = {
        "A-1-a": "Fragmentos de piedra, grava y arena • Subrasante excelente a buena",
        "A-1-b": "Arena gruesa y fina con grava • Subrasante excelente a buena",
        "A-3": "Arena fina de playa o de duna (no plástica) • Subrasante excelente a buena",
        "A-2-4": "Grava y arena con finos limosos (LL ≤ 40) • Subrasante excelente a buena",
        "A-2-5": "Grava y arena con finos limosos (LL > 40) • Subrasante excelente a buena",
        "A-2-6": "Grava y arena con finos arcillosos (IP > 10) • Subrasante buena a regular",
        "A-2-7": "Grava y arena con finos arcillosos elásticos • Subrasante buena a regular",
        "A-4": "Suelo limoso con baja plasticidad • Subrasante regular a pobre",
        "A-5": "Suelo limoso elástico con alto LL • Subrasante regular a pobre",
        "A-6": "Suelo arcilloso con plasticidad media • Subrasante regular a mala",
        "A-7-5": "Suelo arcilloso elástico • Subrasante pobre a mala",
        "A-7-6": "Suelo arcilloso con alta plasticidad e IP elevado • Subrasante pobre a mala"
    }.get(grupo, f"Grupo {grupo} (AASHTO M 145)")

    return {
        "grupo": grupo,
        "ig": ig,
        "texto": f"{grupo}({ig})",
        "desc": desc_calidad,
        "sub_desc": f"Grupo {grupo} • índice de grupo {ig}"
    }

def clasificar_sucs(p4, p10, p40, p200, ll, ip, cu, cc):
    """Clasificación SUCS ASTM D2487 y AASHTO M 145 con carta de plasticidad idéntica a js/app.js."""
    lineaA = 0.73 * (ll - 20.0)
    pasos = []
    
    # Tipo de finos según Casagrande
    if 4.0 <= ip <= 7.0 and ip >= lineaA:
        tipo_finos = "CL-ML"
    elif ip > lineaA and ip >= 4.0:
        tipo_finos = "CL/CH"
    else:
        tipo_finos = "ML/MH"

    texto_plast = f"Con LL = {ll:.1f} % e IP = {ip:.1f} %, la línea A da IP = 0.73·(LL − 20) = {lineaA:.1f} %."

    incompleto = False
    if p200 >= 50.0:
        # Suelo de grano fino
        pasos.append(f"Pasa la malla N°200 = {p200:.1f} % (≥ 50 %): es un suelo de grano fino.")
        pasos.append(texto_plast)
        if tipo_finos == "CL-ML":
            sucs = {"simbolo": "CL-ML", "desc": "Arcilla limosa de baja plasticidad"}
        elif tipo_finos == "CL/CH":
            sucs = {"simbolo": "CH", "desc": "Arcilla de alta plasticidad"} if ll >= 50.0 else {"simbolo": "CL", "desc": "Arcilla de baja plasticidad"}
        else:
            sucs = {"simbolo": "MH", "desc": "Limo de alta plasticidad"} if ll >= 50.0 else {"simbolo": "ML", "desc": "Limo de baja plasticidad"}
        pasos.append(f"El punto (LL, IP) cae en la zona {sucs['simbolo']} de la carta de plasticidad (LL {'>=' if ll >= 50 else '<'} 50 %).")
    else:
        # Suelo de grano grueso
        grava = 100.0 - p4
        arena = p4 - p200
        pasos.append(f"Pasa la malla N°200 = {p200:.1f} % (< 50 %): es un suelo de grano grueso.")
        es_grava = grava > arena
        prefijo = "G" if es_grava else "S"
        nombre = "Grava" if es_grava else "Arena"
        pasos.append(f"Grava = 100 − {p4:.1f} = {grava:.1f} % y arena = {p4:.1f} − {p200:.1f} = {arena:.1f} %: predomina la {nombre.lower()} ({prefijo}).")

        if p200 < 12.0 and (cu is None or cc is None):
            incompleto = True
            sucs = {"simbolo": "Incompleto", "desc": "Requiere Cu y Cc (ingrese D60, D30 y D10)"}
            pasos.append("Con menos de 12 % de finos hay que conocer la graduación: faltan Cu y Cc.")
        else:
            lim_cu = 4.0 if es_grava else 6.0
            bien = (cu is not None and cc is not None and cu >= lim_cu and 1.0 <= cc <= 3.0)
            if p200 < 12.0:
                pasos.append(f"Graduación: Cu = {cu:.2f} ({'>=' if bien or cu >= lim_cu else '<'} {lim_cu}) y Cc = {cc:.2f} ({'dentro de' if (1.0 <= cc <= 3.0) else 'fuera de'} 1–3) → {'bien graduada (W)' if bien else 'mal graduada (P)'}.")

            if p200 < 5.0:
                simbolo = f"{prefijo}W" if bien else f"{prefijo}P"
                desc = f"{nombre} {'bien' if bien else 'pobremente'} graduada"
                sucs = {"simbolo": simbolo, "desc": desc}
                pasos.append(f"Finos {p200:.1f} % < 5 %: se usa solo la graduación → {simbolo}.")
            elif p200 <= 12.0:
                letra_f = "M" if tipo_finos == "ML/MH" else "C"
                simbolo = f"{prefijo}{'W' if bien else 'P'}-{prefijo}{letra_f}"
                desc = f"{nombre} {'bien' if bien else 'pobremente'} graduada con {'limo' if letra_f == 'M' else 'arcilla'}"
                sucs = {"simbolo": simbolo, "desc": desc}
                pasos.append(f"Finos entre 5 y 12 %: doble símbolo (graduación + tipo de finos). {texto_plast} Finos {tipo_finos} → {simbolo}.")
            else:
                if tipo_finos == "ML/MH":
                    simbolo = f"{prefijo}M"
                    desc = f"{nombre} limosa"
                elif tipo_finos == "CL/CH":
                    simbolo = f"{prefijo}C"
                    desc = f"{nombre} arcillosa"
                else:
                    simbolo = f"{prefijo}C-{prefijo}M"
                    desc = f"{nombre} arcillo-limosa"
                sucs = {"simbolo": simbolo, "desc": desc}
                pasos.append(f"Finos {p200:.1f} % > 12 %: se clasifica por el tipo de finos. {texto_plast} Finos {tipo_finos} → {simbolo}.")

    aashto = clasificar_aashto(p10, p40, p200, ll, ip)
    if p200 <= 35.0:
        pasos.append(f"AASHTO: pasa N°200 = {p200:.1f} % (≤ 35 %): material granular. Con N°10 = {p10:.1f} %, N°40 = {p40:.1f} % e IP = {ip:.1f} % → grupo {aashto['grupo']}.")
    else:
        pasos.append(f"AASHTO: pasa N°200 = {p200:.1f} % (> 35 %): suelo limo-arcilloso. Con LL = {ll:.1f} % e IP = {ip:.1f} % → grupo {aashto['grupo']}.")
    
    es_cero_fijo = aashto["grupo"] in ["A-1-a", "A-1-b", "A-3", "A-2-4", "A-2-5"]
    pasos.append(f"Índice de grupo IG = {aashto['ig']}{' (para este grupo siempre es 0)' if es_cero_fijo else ''} → {aashto['texto']}.")

    graficar = p200 >= 50.0 or (p200 > 12.0 and bool(re.search(r'[MC]', sucs.get('simbolo', ''))))
    return {
        "sucs": sucs,
        "aashto": aashto,
        "pasos": pasos,
        "lineaA": lineaA,
        "tipo_finos": tipo_finos,
        "incompleto": incompleto,
        "graficar": graficar
    }

def obtener_estilos_pdf():
    """Estilos tipográficos formales idénticos a los informes web de laboratorio."""
    hoja = getSampleStyleSheet()
    estilos = {}
    estilos["titulo_institucion"] = ParagraphStyle(
        "TituloInstitucion",
        parent=hoja["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=colors.HexColor(PRIMARY),
        alignment=1, # Centro
        spaceAfter=2
    )
    estilos["subtitulo_sistema"] = ParagraphStyle(
        "SubtituloSistema",
        parent=hoja["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor(NEUTRAL_MUTED),
        alignment=1,
        spaceAfter=4
    )
    estilos["titulo_informe"] = ParagraphStyle(
        "TituloInforme",
        parent=hoja["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
        textColor=colors.HexColor(NEUTRAL_HEADING),
        alignment=1,
        spaceAfter=2
    )
    estilos["norma_ref"] = ParagraphStyle(
        "NormaRef",
        parent=hoja["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor(ACCENT_RED),
        alignment=1,
        spaceAfter=6
    )
    estilos["seccion"] = ParagraphStyle(
        "Seccion",
        parent=hoja["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor(PRIMARY),
        spaceBefore=8,
        spaceAfter=4
    )
    estilos["celda_normal"] = ParagraphStyle(
        "CeldaNormal",
        parent=hoja["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor(NEUTRAL_BODY),
        alignment=0
    )
    estilos["celda_bold"] = ParagraphStyle(
        "CeldaBold",
        parent=hoja["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor(NEUTRAL_HEADING),
        alignment=0
    )
    estilos["celda_centro"] = ParagraphStyle(
        "CeldaCentro",
        parent=hoja["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor(NEUTRAL_BODY),
        alignment=1
    )
    estilos["celda_derecha"] = ParagraphStyle(
        "CeldaDerecha",
        parent=hoja["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor(NEUTRAL_BODY),
        alignment=2
    )
    estilos["firma"] = ParagraphStyle(
        "Firma",
        parent=hoja["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor(NEUTRAL_BODY),
        alignment=1
    )
    return estilos

def crear_cabecera_pdf(estilos, titulo_ensayo, norma):
    """Encabezado oficial institucional con barra superior."""
    elementos = []
    elementos.append(Paragraph("LABORATORIO DE MECÁNICA DE SUELOS • ING. GEOLÓGICA FIGMM", estilos["titulo_institucion"]))
    elementos.append(Paragraph("SISTEMA PROFESIONAL DE CONTROL GEOTÉCNICO (GEOLAB)", estilos["subtitulo_sistema"]))
    elementos.append(Paragraph(f"INFORME TÉCNICO: {titulo_ensayo.upper()}", estilos["titulo_informe"]))
    elementos.append(Paragraph(f"Norma de Referencia: {norma}", estilos["norma_ref"]))
    elementos.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(PRIMARY), spaceAfter=6))
    return elementos

def crear_tabla_metadatos(datos_proyecto):
    """Crea la tabla de identificación del proyecto idéntica a la versión Web."""
    p = datos_proyecto
    data = [
        [
            Paragraph("<b>Proyecto / Obra:</b>", ParagraphStyle("M1", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.HexColor(PRIMARY))),
            Paragraph(str(p.get("proyecto", "---")), ParagraphStyle("M2", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.HexColor(NEUTRAL_HEADING))),
            Paragraph("<b>N.° de Muestra:</b>", ParagraphStyle("M1", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.HexColor(PRIMARY))),
            Paragraph(str(p.get("muestra", "---")), ParagraphStyle("M2", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.HexColor(NEUTRAL_HEADING)))
        ],
        [
            Paragraph("<b>Procedencia / Ubicación:</b>", ParagraphStyle("M1", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.HexColor(PRIMARY))),
            Paragraph(str(p.get("procedencia", "---")), ParagraphStyle("M2", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.HexColor(NEUTRAL_BODY))),
            Paragraph("<b>Fecha de Ensayo:</b>", ParagraphStyle("M1", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.HexColor(PRIMARY))),
            Paragraph(str(p.get("fecha", "---")), ParagraphStyle("M2", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.HexColor(NEUTRAL_BODY)))
        ],
        [
            Paragraph("<b>Descripción del Material:</b>", ParagraphStyle("M1", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.HexColor(PRIMARY))),
            Paragraph(str(p.get("material", "---")), ParagraphStyle("M2", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.HexColor(NEUTRAL_BODY))),
            Paragraph("<b>Ensayado por:</b>", ParagraphStyle("M1", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.HexColor(PRIMARY))),
            Paragraph(str(p.get("ensayado", "---")), ParagraphStyle("M2", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.HexColor(NEUTRAL_BODY)))
        ]
    ]
    t = Table(data, colWidths=[120, 210, 95, 115])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(CARD_BG_ALT)),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(BORDER_COLOR)),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_SUBTLE)),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t

def crear_bloque_firmas(estilos):
    """Bloque de firmas formal de laboratorio."""
    linea = "_" * 32
    data = [
        ["", ""],
        [Paragraph(f"{linea}<br/><b>TÉCNICO DE LABORATORIO</b><br/>Responsable de Ensayo", estilos["firma"]),
         Paragraph(f"{linea}<br/><b>INGENIERO GEOTÉCNICO / JEFE</b><br/>Revisado y Autorizado", estilos["firma"])]
    ]
    t = Table(data, colWidths=[270, 270])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 20),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t

def figura_a_imagen_reportlab(fig, width=420, height=220):
    """Convierte una figura Matplotlib a un elemento RLImage en memoria."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return RLImage(buf, width=width, height=height)

def crear_boton(parent, texto, comando, color=PRIMARY, hover=PRIMARY_HOVER, width=140, height=36, icon=""):
    """Crea un botón estilizado con la paleta formal."""
    return ctk.CTkButton(
        parent,
        text=f"{icon} {texto}".strip(),
        command=comando,
        fg_color=color,
        hover_color=hover,
        text_color="#FFFFFF",
        corner_radius=6,
        font=ctk.CTkFont(size=12, weight="bold"),
        width=width,
        height=height
    )

# ===================================================================
# BASE DE DATOS: armado del informe que se envía al servidor
# ===================================================================
def _resumen_resultados(clave, e):
    """Valores principales de cada ensayo (para consultar rápido en la base de datos)."""
    e = e or {}

    def pick(*claves):
        return {k: e.get(k) for k in claves if e.get(k) is not None}

    if clave == "humedad":
        return pick("promedio")
    if clave == "volumetrico":
        return pick("rho_humeda", "gamma_kn_m3", "rho_seca", "gamma_seca")
    if clave == "gravedad":
        return pick("gs", "gt", "temp")
    if clave == "granulometria":
        return pick("grava", "arena", "finos", "p4", "p10", "p40", "p200", "d10", "d30", "d60", "cu", "cc")
    if clave == "atterberg":
        r = {"np": bool(e.get("np"))}
        r.update(pick("ll", "lp", "ip"))
        return r
    if clave == "clasificacion":
        r = {}
        if e.get("sucs"):
            r["sucs"] = e["sucs"].get("simbolo")
        if e.get("aashto"):
            r["aashto"] = e["aashto"].get("texto")
        return r
    if clave == "proctor":
        return pick("mds", "och", "mds95", "gamma_kn_m3")
    return {}


def construir_informe(controller, clave, archivo_pdf, tipo="individual"):
    """Arma el paquete (JSON) que se guarda en la tabla `informes`."""
    ens = controller.geo_state["ensayos"]
    p = controller.datos_proyecto
    if tipo == "consolidado":
        datos_ens = {k: v for k, v in ens.items() if v}
        resultados = {k: _resumen_resultados(k, v) for k, v in datos_ens.items()}
        cls = ens.get("clasificacion") or {}
    else:
        datos_ens = {clave: ens.get(clave, {})}
        resultados = _resumen_resultados(clave, ens.get(clave, {}))
        cls = ens.get(clave, {}) if clave == "clasificacion" else {}

    partes = []
    if cls.get("sucs"):
        partes.append(f"SUCS {cls['sucs'].get('simbolo', '')}")
    if cls.get("aashto"):
        partes.append(f"AASHTO {cls['aashto'].get('texto', '')}")

    return api_client.nuevo_payload(
        proyecto=p.get("proyecto"),
        muestra=p.get("muestra"),
        ensayo="consolidado" if tipo == "consolidado" else clave,
        tipo=tipo,
        archivo_pdf=os.path.basename(archivo_pdf or ""),
        datos={"proyecto": dict(p), "ensayos": datos_ens},
        resultados=resultados,
        clasificacion=" | ".join(partes) if partes else None,
    )


class Cabecera(ctk.CTkFrame):
    """Cabecera superior institucional formal FIGMM."""
    def __init__(self, parent, titulo, subtitulo=""):
        super().__init__(parent, fg_color="transparent")
        
        contenedor = ctk.CTkFrame(self, fg_color=PRIMARY, corner_radius=8, height=64)
        contenedor.pack(fill="x")
        contenedor.pack_propagate(False)

        icono_frame = ctk.CTkFrame(contenedor, fg_color=PRIMARY_HOVER, corner_radius=6, width=44, height=44)
        icono_frame.pack(side="left", padx=10, pady=10)
        icono_frame.pack_propagate(False)
        ctk.CTkLabel(
            icono_frame,
            text="⚖",
            font=ctk.CTkFont(size=22),
            text_color="#FFFFFF"
        ).pack(expand=True)

        info = ctk.CTkFrame(contenedor, fg_color="transparent")
        info.pack(side="left", padx=5, fill="y", expand=True)

        ctk.CTkLabel(
            info,
            text=titulo,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#FFFFFF",
            anchor="w"
        ).pack(anchor="w", pady=(10, 1))

        if subtitulo:
            ctk.CTkLabel(
                info,
                text=subtitulo,
                font=ctk.CTkFont(size=11),
                text_color=PRIMARY_LIGHT,
                anchor="w"
            ).pack(anchor="w")

class BarraProyecto(ctk.CTkFrame):
    """Cinta superior de sincronización del proyecto (idéntica a la barra de la web)."""
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=CARD_BG, height=38, border_width=1, border_color=BORDER_COLOR, corner_radius=0)
        self.controller = controller
        self.pack_propagate(False)

        self.lbl_info = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=NEUTRAL_BODY,
            anchor="w"
        )
        self.lbl_info.pack(side="left", padx=16, pady=4, fill="x", expand=True)

        ctk.CTkButton(
            self,
            text="⚙ Datos del Proyecto",
            command=self.abrir_dialogo_proyecto,
            fg_color=PRIMARY_LIGHT,
            hover_color=PRIMARY_BORDER,
            text_color=PRIMARY,
            corner_radius=4,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(side="right", padx=12, pady=5)

        self.btn_servidor = ctk.CTkButton(
            self,
            text="☁ Servidor",
            command=self.abrir_dialogo_servidor,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=4,
            height=26,
            width=90,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_servidor.pack(side="right", padx=(0, 4), pady=5)

        self.lbl_servidor = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=10), text_color=NEUTRAL_MUTED)
        self.lbl_servidor.pack(side="right", padx=(0, 8))
        self._temporizador_estado = None

        self.actualizar()
        self.actualizar_servidor()

    def actualizar_servidor(self, texto=None, estado=None):
        """Muestra el estado de la conexión. Los avisos se borran solos a los 8 segundos."""
        if api_client is None:
            self.lbl_servidor.configure(text="☁ Instale 'requests' para usar la base de datos", text_color=NEUTRAL_MUTED)
            return
        colores = {"ok": ACCENT_GREEN, "pendiente": "#B45309", "sin_sesion": "#B45309", "error": ACCENT_RED}
        if texto is None:
            self.lbl_servidor.configure(text=api_client.texto_estado(), text_color=NEUTRAL_MUTED)
            return
        texto_corto = texto if len(texto) <= 70 else texto[:67] + "..."
        self.lbl_servidor.configure(text=texto_corto, text_color=colores.get(estado, NEUTRAL_MUTED))
        if self._temporizador_estado:
            self.after_cancel(self._temporizador_estado)
        self._temporizador_estado = self.after(8000, self.actualizar_servidor)

    def abrir_dialogo_servidor(self):
        if api_client is None:
            messagebox.showwarning("Falta una librería", "Para usar la base de datos instale 'requests':\n\npip install requests")
            return
        DialogoServidor(self, self.controller)

    def actualizar(self):
        p = self.controller.datos_proyecto
        texto = f"📌 Proyecto: {p.get('proyecto', '---')}   |   Muestra: {p.get('muestra', '---')}   |   Procedencia: {p.get('procedencia', '---')}   |   Material: {p.get('material', '---')}   |   Fecha: {p.get('fecha', '---')}"
        self.lbl_info.configure(text=texto)

    def abrir_dialogo_proyecto(self):
        DialogoDatosProyecto(self, self.controller)

class DialogoDatosProyecto(ctk.CTkToplevel):
    """Ventana modal para editar la identificación del proyecto."""
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.title("Identificación del Proyecto y Muestra")
        self.geometry("540x480")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        p = self.controller.datos_proyecto
        self.configure(fg_color=FONDO)

        Cabecera(self, "DATOS DEL PROYECTO", "Se sincronizan en todos los ensayos e informes").pack(fill="x", padx=16, pady=(16, 10))

        cuerpo = ctk.CTkFrame(self, fg_color=CARD_BG, border_width=1, border_color=BORDER_COLOR, corner_radius=8)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        self.entries = {}
        campos = [
            ("proyecto", "Nombre del Proyecto / Obra:"),
            ("muestra", "N.° de Muestra / Identificador:"),
            ("procedencia", "Procedencia / Calicata / Prof.:"),
            ("material", "Descripción del Material / Suelo:"),
            ("ensayado", "Ensayado por / Laboratorista:"),
            ("fecha", "Fecha de Ensayo (DD/MM/AAAA):"),
        ]

        for i, (k, etiqueta) in enumerate(campos):
            f = ctk.CTkFrame(cuerpo, fg_color="transparent")
            f.pack(fill="x", padx=14, pady=5)
            ctk.CTkLabel(f, text=etiqueta, font=ctk.CTkFont(size=11, weight="bold"), text_color=NEUTRAL_HEADING, width=190, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, height=30, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e.insert(0, str(p.get(k, "")))
            e.pack(side="right", fill="x", expand=True)
            self.entries[k] = e

        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=16, pady=(0, 16))

        crear_boton(btn_bar, "Guardar y Sincronizar", self.guardar, color=PRIMARY, hover=PRIMARY_HOVER, width=180).pack(side="right", padx=4)
        crear_boton(btn_bar, "Cancelar", self.destroy, color=NEUTRAL_MUTED, hover=NEUTRAL_BODY, width=110).pack(side="right", padx=4)

    def guardar(self):
        for k, e in self.entries.items():
            self.controller.datos_proyecto[k] = e.get().strip()
        self.controller.barra_proyecto.actualizar()
        messagebox.showinfo("Datos Guardados", "Los datos del proyecto se han actualizado y sincronizado en todos los ensayos e informes.")
        self.destroy()

class DialogoServidor(ctk.CTkToplevel):
    """Inicio de sesión / registro en el servidor de GeoLab (base de datos)."""
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.title("Servidor y Base de Datos")
        self.geometry("540x600")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.configure(fg_color=FONDO)
        self._cola = queue.Queue()

        Cabecera(self, "SERVIDOR Y BASE DE DATOS", "Cada informe PDF se guarda automáticamente en la base de datos").pack(fill="x", padx=16, pady=(16, 10))

        cuerpo = ctk.CTkFrame(self, fg_color=CARD_BG, border_width=1, border_color=BORDER_COLOR, corner_radius=8)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        cfg = api_client.cargar_config()
        campos = [
            ("url", "Dirección del servidor:", cfg["url"], False),
            ("email", "Correo:", cfg["email"], False),
            ("password", "Contraseña:", "", True),
            ("nombre", "Nombre (solo al registrarse):", cfg["nombre"], False),
            ("codigo", "Código de registro (si lo piden):", "", False),
        ]
        self.entries = {}
        for clave, etiqueta, valor, oculto in campos:
            f = ctk.CTkFrame(cuerpo, fg_color="transparent")
            f.pack(fill="x", padx=14, pady=6)
            ctk.CTkLabel(f, text=etiqueta, font=ctk.CTkFont(size=11, weight="bold"), text_color=NEUTRAL_HEADING, width=200, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, height=30, fg_color="#FFFFFF", border_color=BORDER_COLOR, show="•" if oculto else "")
            if valor:
                e.insert(0, valor)
            e.pack(side="right", fill="x", expand=True)
            self.entries[clave] = e

        self.lbl_estado = ctk.CTkLabel(cuerpo, text=api_client.texto_estado(), font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY, wraplength=460, justify="left")
        self.lbl_estado.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            cuerpo,
            text="Con la sesión iniciada, cada vez que exporte un informe a PDF se guardará también en la base de datos.\n"
                 "Si no hay conexión, el informe queda en cola y se envía solo más tarde.",
            font=ctk.CTkFont(size=10), text_color=NEUTRAL_MUTED, wraplength=470, justify="left"
        ).pack(fill="x", padx=16, pady=(0, 10))

        fila1 = ctk.CTkFrame(self, fg_color="transparent")
        fila1.pack(fill="x", padx=16, pady=(0, 6))
        crear_boton(fila1, "Iniciar sesión", self.iniciar_sesion, color=PRIMARY, hover=PRIMARY_HOVER, width=150).pack(side="left", padx=(0, 6))
        crear_boton(fila1, "Registrarme", self.registrarse, color=ACCENT_GREEN, hover=ACCENT_GREEN_HOVER, width=130).pack(side="left", padx=6)
        crear_boton(fila1, "Cerrar sesión", self.cerrar_sesion, color=ACCENT_RED, hover=ACCENT_RED_HOVER, width=130).pack(side="left", padx=6)

        fila2 = ctk.CTkFrame(self, fg_color="transparent")
        fila2.pack(fill="x", padx=16, pady=(0, 16))
        crear_boton(fila2, "Enviar pendientes", self.enviar_pendientes, color=NEUTRAL_BODY, hover=NEUTRAL_DARK, width=150).pack(side="left", padx=(0, 6))
        crear_boton(fila2, "Cerrar", self.destroy, color=NEUTRAL_MUTED, hover=NEUTRAL_BODY, width=110).pack(side="right")

    def _valores(self):
        return {k: e.get().strip() for k, e in self.entries.items()}

    def _correr(self, funcion, mensaje_ok):
        """Ejecuta la llamada de red en un hilo para no congelar la ventana."""
        self.lbl_estado.configure(text="Conectando con el servidor...", text_color=NEUTRAL_MUTED)

        def tarea():
            try:
                resultado = funcion()
                self._cola.put((True, mensaje_ok(resultado) if callable(mensaje_ok) else mensaje_ok))
            except api_client.ErrorAPI as e:
                self._cola.put((False, str(e)))
            except Exception as e:
                self._cola.put((False, f"Error inesperado: {e}"))

        threading.Thread(target=tarea, daemon=True).start()
        self.after(150, self._esperar)

    def _esperar(self):
        if not self.winfo_exists():
            return
        try:
            ok, mensaje = self._cola.get_nowait()
        except queue.Empty:
            self.after(150, self._esperar)
            return
        self.lbl_estado.configure(text=api_client.texto_estado(), text_color=PRIMARY)
        self.controller.barra_proyecto.actualizar_servidor()
        if ok:
            messagebox.showinfo("Servidor", mensaje, parent=self)
        else:
            messagebox.showerror("Servidor", mensaje, parent=self)

    def iniciar_sesion(self):
        v = self._valores()
        if not v["email"] or not v["password"]:
            messagebox.showwarning("Faltan datos", "Escriba su correo y contraseña.", parent=self)
            return
        self._correr(lambda: api_client.login(v["email"], v["password"], url=v["url"]), "Sesión iniciada correctamente.")

    def registrarse(self):
        v = self._valores()
        if not v["nombre"] or not v["email"] or len(v["password"]) < 8:
            messagebox.showwarning("Faltan datos", "Para registrarse escriba su nombre, correo y una contraseña de al menos 8 caracteres.", parent=self)
            return
        self._correr(lambda: api_client.registrar(v["nombre"], v["email"], v["password"], v["codigo"], url=v["url"]), "Cuenta creada y sesión iniciada.")

    def cerrar_sesion(self):
        self._correr(api_client.cerrar_sesion, "Sesión cerrada.")

    def enviar_pendientes(self):
        self._correr(api_client.enviar_pendientes, lambda r: f"Enviados: {r[0]}.  Pendientes: {r[1]}.")


class TablaFormulario(ctk.CTkFrame):
    """Contenedor de formulario con encabezado elegante."""
    def __init__(self, parent, titulo="", icono="📋"):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.entradas = {}
        
        if titulo:
            hdr = ctk.CTkFrame(self, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
            hdr.pack(fill="x", padx=4, pady=4)
            hdr.pack_propagate(False)
            ctk.CTkLabel(
                hdr,
                text=f"{icono}  {titulo}",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=PRIMARY
            ).pack(side="left", padx=10, pady=4)

        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self.cuerpo.pack(fill="both", expand=True, padx=8, pady=(2, 6))

    def agregar_fila(self, clave, etiqueta, unidad="", valor_defecto=""):
        f = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
        f.pack(fill="x", pady=2)
        ctk.CTkLabel(f, text=etiqueta, font=ctk.CTkFont(size=11), text_color=NEUTRAL_BODY, width=210, anchor="w").pack(side="left")
        e = ctk.CTkEntry(f, height=28, width=110, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        if valor_defecto:
            e.insert(0, str(valor_defecto))
        e.pack(side="left", fill="x", expand=True, padx=(0, 6))
        if unidad:
            ctk.CTkLabel(f, text=unidad, font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_MUTED, width=45, anchor="w").pack(side="right")
        self.entradas[clave] = e
        return e

    def get(self, clave):
        if clave in self.entradas:
            return self.entradas[clave].get().strip()
        return ""

    def set(self, clave, val):
        if clave in self.entradas:
            self.entradas[clave].delete(0, "end")
            self.entradas[clave].insert(0, str(val))

    def limpiar(self):
        for e in self.entradas.values():
            e.delete(0, "end")

class BaseEnsayo(ctk.CTkFrame):
    """Estructura modular para las vistas de los 7 ensayos."""
    titulo = "ENSAYO DE LABORATORIO"
    subtitulo = "Descripción técnica"
    codigo_norma = "NORMA ASTM / NTP"
    clave_ensayo = ""

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=FONDO)
        self.controller = controller
        self.calculado = False
        self.datos_calculados = {}

        # Cabecera principal
        Cabecera(self, self.titulo, self.subtitulo).pack(fill="x", padx=20, pady=(14, 4))

        # Barra de navegación
        self.nav = ctk.CTkFrame(self, fg_color="transparent")
        self.nav.pack(fill="x", padx=20, pady=(0, 6))

        self.btn_volver_menu = crear_boton(
            self.nav,
            "← Volver al Panel Principal",
            lambda: controller.mostrar("MenuPrincipal"),
            color=NEUTRAL_MUTED,
            hover=NEUTRAL_BODY,
            width=180,
            height=30
        )
        self.btn_volver_menu.pack(side="left")

        self.btn_volver_clasificacion = crear_boton(
            self.nav,
            "⬅ Guardar y Regresar a Clasificación de Suelos",
            self.volver_a_clasificacion,
            color=PRIMARY,
            hover=PRIMARY_HOVER,
            width=260,
            height=30,
            icon="⬅"
        )
        # Se empaqueta en al_mostrar si origen_clasificacion es True

        ctk.CTkLabel(
            self.nav,
            text=f"Norma: {self.codigo_norma}",
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color=ACCENT_RED
        ).pack(side="right", padx=6)

        # Contenedor dividido en 2 columnas
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.cuerpo_principal = ctk.CTkFrame(self, fg_color="transparent")
        self.cuerpo_principal.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self.cuerpo_principal.grid_columnconfigure(0, weight=5) # Izquierda: Entradas
        self.cuerpo_principal.grid_columnconfigure(1, weight=5) # Derecha: Resultados y gráficos
        self.cuerpo_principal.grid_rowconfigure(0, weight=1)

        self.panel_izquierdo = ctk.CTkFrame(self.cuerpo_principal, fg_color="transparent")
        self.panel_izquierdo.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.panel_derecho = ctk.CTkFrame(self.cuerpo_principal, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.panel_derecho.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # Panel derecho: encabezado de resultados
        hdr_der = ctk.CTkFrame(self.panel_derecho, fg_color=PRIMARY_LIGHT, corner_radius=6, height=36)
        hdr_der.pack(fill="x", padx=6, pady=6)
        hdr_der.pack_propagate(False)
        ctk.CTkLabel(
            hdr_der,
            text="📊  Resultados del Ensayo y Gráficos",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PRIMARY
        ).pack(side="left", padx=10, pady=4)

        self.contenedor_resultados = ctk.CTkScrollableFrame(self.panel_derecho, fg_color="transparent")
        self.contenedor_resultados.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Barra inferior de exportación individual en panel derecho
        barra_export = ctk.CTkFrame(self.panel_derecho, fg_color="transparent", height=44)
        barra_export.pack(fill="x", padx=8, pady=6, side="bottom")
        crear_boton(
            barra_export,
            "📄 Exportar este Ensayo a PDF",
            self.exportar_pdf_seguro,
            color=ACCENT_GREEN,
            hover=ACCENT_GREEN_HOVER,
            width=220,
            height=34
        ).pack(fill="x")

        self.mostrar_placeholder_resultados()

    def mostrar_placeholder_resultados(self):
        for w in self.contenedor_resultados.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.contenedor_resultados,
            text="Los resultados calculados y gráficos técnicos se mostrarán aquí.\n\nComplete los datos en el panel izquierdo y presione '⚡ Calcular'.",
            font=ctk.CTkFont(size=12),
            text_color=NEUTRAL_MUTED,
            justify="center"
        ).pack(expand=True, pady=60)

    def exportar_pdf_seguro(self):
        if not self.calculado:
            messagebox.showwarning(
                "Ensayo sin Calcular",
                f"Para exportar el informe de '{self.titulo}', primero ingrese los datos y presione '⚡ Calcular'."
            )
            return
        ESTADO_PDF["ultimo"] = None
        self.exportar_pdf()
        if ESTADO_PDF["ultimo"]:
            self.controller.registrar_informe(self.clave_ensayo, ESTADO_PDF["ultimo"], "individual")

    def exportar_pdf(self):
        pass

    def calcular(self):
        pass

    def limpiar(self):
        self.calculado = False
        self.datos_calculados = {}
        self.mostrar_placeholder_resultados()

    def cargar_demo(self):
        pass

    def volver_a_clasificacion(self):
        if not self.calculado:
            try:
                self.calcular()
            except Exception:
                pass
        self.controller.origen_clasificacion = False
        self.controller.mostrar("ClasificacionSuelos")

    def al_mostrar(self):
        if hasattr(self, "btn_volver_clasificacion"):
            if getattr(self.controller, "origen_clasificacion", False):
                self.btn_volver_clasificacion.pack(side="left", padx=10)
            else:
                self.btn_volver_clasificacion.pack_forget()

# -------------------------------------------------------------------
# ENSAYO 01: CONTENIDO DE HUMEDAD (ASTM D2216 / NTP 339.127)
# -------------------------------------------------------------------
class ContenidoHumedad(BaseEnsayo):
    titulo = "01. CONTENIDO DE HUMEDAD"
    subtitulo = "Determinación del contenido de humedad en horno según ASTM D2216 / NTP 339.127"
    codigo_norma = "ASTM D2216 • NTP 339.127 • MTC E 108"
    clave_ensayo = "humedad"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        scroll_in = ctk.CTkScrollableFrame(self.panel_izquierdo, fg_color="transparent")
        scroll_in.pack(fill="both", expand=True)

        # Condiciones de secado
        self.form_cond = TablaFormulario(scroll_in, "Condiciones de Secado en Horno", "🌡")
        self.form_cond.pack(fill="x", pady=(0, 8))
        self.form_cond.agregar_fila("temp", "Temperatura de secado", "°C", "110.0")
        self.form_cond.agregar_fila("tiempo", "Tiempo en el horno", "h", "24.0")

        # Tabla de pesadas
        self.card_pesadas = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_pesadas.pack(fill="x", pady=4)

        hdr_p = ctk.CTkFrame(self.card_pesadas, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
        hdr_p.pack(fill="x", padx=4, pady=4)
        hdr_p.pack_propagate(False)
        ctk.CTkLabel(hdr_p, text="⚖  Determinaciones de Masa (Cápsulas)", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=10, pady=4)

        self.filas_pesadas = []
        self.f_tabla = ctk.CTkFrame(self.card_pesadas, fg_color="transparent")
        self.f_tabla.pack(fill="x", padx=6, pady=4)

        headers = ["N°", "N° de\nrecipiente", "Masa del\nrecipiente (M1) [g]", "Masa del recipiente +\nmasa del suelo húmedo (M2) [g]", "Masa del recipiente +\nmasa del suelo seco (M3) [g]"]
        cols_w = [30, 85, 120, 170, 170]
        h_frame = ctk.CTkFrame(self.f_tabla, fg_color=CARD_BG_ALT, height=40)
        h_frame.pack(fill="x", pady=2)
        for t, w in zip(headers, cols_w):
            ctk.CTkLabel(h_frame, text=t, font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=w).pack(side="left", padx=2)

        for i in range(1, 4):
            self.agregar_fila_pesada(i)

        # Botonera de acciones
        b_bar = ctk.CTkFrame(self.panel_izquierdo, fg_color="transparent")
        b_bar.pack(fill="x", pady=8)
        crear_boton(b_bar, "Calcular", self.calcular, color=PRIMARY, hover=PRIMARY_HOVER, icon="⚡").pack(side="left", padx=3, fill="x", expand=True)
        crear_boton(b_bar, "Ejemplo (Demo)", self.cargar_demo, color=PRIMARY_LIGHT, hover=PRIMARY_BORDER, icon="🧪").pack(side="left", padx=3, fill="x", expand=True)
        b_bar.winfo_children()[-1].configure(text_color=PRIMARY)
        crear_boton(b_bar, "Limpiar", self.limpiar, color=NEUTRAL_MUTED, hover=NEUTRAL_BODY, icon="🗑").pack(side="left", padx=3, fill="x", expand=True)

    def agregar_fila_pesada(self, num):
        rf = ctk.CTkFrame(self.f_tabla, fg_color="transparent")
        rf.pack(fill="x", pady=2)
        ctk.CTkLabel(rf, text=str(num), font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY, width=30).pack(side="left", padx=2)
        e_id = ctk.CTkEntry(rf, height=26, width=90, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        e_id.insert(0, f"C-{num}")
        e_id.pack(side="left", padx=2)
        e_mr = ctk.CTkEntry(rf, height=26, width=110, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        e_mr.pack(side="left", padx=2)
        e_mh = ctk.CTkEntry(rf, height=26, width=120, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        e_mh.pack(side="left", padx=2)
        e_ms = ctk.CTkEntry(rf, height=26, width=120, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        e_ms.pack(side="left", padx=2)
        self.filas_pesadas.append({"num": num, "id": e_id, "mr": e_mr, "mh": e_mh, "ms": e_ms})

    def calcular(self):
        try:
            det = []
            for r in self.filas_pesadas:
                id_val = r["id"].get().strip()
                mr_val = r["mr"].get().strip()
                mh_val = r["mh"].get().strip()
                ms_val = r["ms"].get().strip()
                if not mr_val and not mh_val and not ms_val:
                    continue
                if not mr_val or not mh_val or not ms_val:
                    raise ValueError(f"En la fila {r['num']}, complete todas las masas requeridas.")
                mr, mh, ms = float(mr_val), float(mh_val), float(ms_val)
                if mh <= mr or ms <= mr:
                    raise ValueError(f"En la fila {r['num']}, las masas (M2) y (M3) deben ser mayores que la masa del recipiente (M1).")
                if mh < ms:
                    raise ValueError(f"En la fila {r['num']}, la masa del recipiente + suelo húmedo (M2) no puede ser menor a la del recipiente + suelo seco (M3).")
                mw = mh - ms
                mss = ms - mr
                w = (mw / mss) * 100.0
                det.append({"num": r["num"], "id": id_val, "mr": mr, "mh": mh, "ms": ms, "mw": mw, "mss": mss, "w": w})

            if not det:
                raise ValueError("Ingrese los datos de al menos una determinación.")

            temp = float(self.form_cond.get("temp") or 110.0)
            tiempo = float(self.form_cond.get("tiempo") or 24.0)
            prom = sum(d["w"] for d in det) / len(det)

            self.datos_calculados = {
                "determinaciones": det,
                "temp": temp,
                "tiempo": tiempo,
                "promedio": prom
            }
            self.calculado = True

            # Sincronizar en el controlador
            self.controller.geo_state["ensayos"]["humedad"] = self.datos_calculados
            self.mostrar_resultados()
            messagebox.showinfo("Cálculo Exitoso", f"Contenido de Humedad Promedio calculado:\n\nw = {prom:.1f} %")

        except Exception as e:
            messagebox.showerror("Error en Humedad", str(e))

    def mostrar_resultados(self):
        for w in self.contenedor_resultados.winfo_children():
            w.destroy()

        d = self.datos_calculados
        # Tarjeta de resultado principal
        res_card = ctk.CTkFrame(self.contenedor_resultados, fg_color=PRIMARY_LIGHT, corner_radius=8, border_width=1, border_color=PRIMARY_BORDER)
        res_card.pack(fill="x", pady=(4, 10))
        ctk.CTkLabel(res_card, text="CONTENIDO DE HUMEDAD PROMEDIO (w):", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(pady=(8, 2))
        ctk.CTkLabel(res_card, text=f"{d['promedio']:.1f} %", font=ctk.CTkFont(size=26, weight="bold"), text_color=PRIMARY).pack(pady=(0, 8))

        # Tabla de resumen
        t_frame = ctk.CTkFrame(self.contenedor_resultados, fg_color="transparent")
        t_frame.pack(fill="x", pady=4)
        headers = ["N°", "N° recipiente", "M. Agua (g)", "M. Seca (g)", "Humedad (w)"]
        cols_w = [30, 80, 100, 100, 110]
        hf = ctk.CTkFrame(t_frame, fg_color=CARD_BG_ALT, height=26)
        hf.pack(fill="x", pady=2)
        for h, w in zip(headers, cols_w):
            ctk.CTkLabel(hf, text=h, font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=w).pack(side="left", padx=2)

        for det in d["determinaciones"]:
            rf = ctk.CTkFrame(t_frame, fg_color="#FFFFFF", border_width=1, border_color=BORDER_SUBTLE)
            rf.pack(fill="x", pady=1)
            ctk.CTkLabel(rf, text=str(det["num"]), font=ctk.CTkFont(size=10), width=30).pack(side="left", padx=2)
            ctk.CTkLabel(rf, text=det["id"], font=ctk.CTkFont(size=10, weight="bold"), width=80).pack(side="left", padx=2)
            ctk.CTkLabel(rf, text=f"{det['mw']:.1f}", font=ctk.CTkFont(size=10), width=100).pack(side="left", padx=2)
            ctk.CTkLabel(rf, text=f"{det['mss']:.1f}", font=ctk.CTkFont(size=10), width=100).pack(side="left", padx=2)
            ctk.CTkLabel(rf, text=f"{det['w']:.1f} %", font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_GREEN, width=110).pack(side="left", padx=2)

    def cargar_demo(self):
        self.filas_pesadas[0]["id"].delete(0, "end"); self.filas_pesadas[0]["id"].insert(0, "T2-91")
        self.filas_pesadas[0]["mr"].delete(0, "end"); self.filas_pesadas[0]["mr"].insert(0, "79.10")
        self.filas_pesadas[0]["mh"].delete(0, "end"); self.filas_pesadas[0]["mh"].insert(0, "637.00")
        self.filas_pesadas[0]["ms"].delete(0, "end"); self.filas_pesadas[0]["ms"].insert(0, "582.60")

        self.filas_pesadas[1]["id"].delete(0, "end"); self.filas_pesadas[1]["id"].insert(0, "T2-92")
        self.filas_pesadas[1]["mr"].delete(0, "end"); self.filas_pesadas[1]["mr"].insert(0, "113.30")
        self.filas_pesadas[1]["mh"].delete(0, "end"); self.filas_pesadas[1]["mh"].insert(0, "742.00")
        self.filas_pesadas[1]["ms"].delete(0, "end"); self.filas_pesadas[1]["ms"].insert(0, "682.00")

        self.filas_pesadas[2]["id"].delete(0, "end"); self.filas_pesadas[2]["id"].insert(0, "C-3")
        self.filas_pesadas[2]["mr"].delete(0, "end")
        self.filas_pesadas[2]["mh"].delete(0, "end")
        self.filas_pesadas[2]["ms"].delete(0, "end")
        self.calcular()

    def limpiar(self):
        super().limpiar()
        for r in self.filas_pesadas:
            r["mr"].delete(0, "end")
            r["mh"].delete(0, "end")
            r["ms"].delete(0, "end")

    def exportar_pdf(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar Informe Técnico de Contenido de Humedad",
            defaultextension=".pdf",
            initialfile=f"Informe_Humedad_{self.controller.datos_proyecto.get('muestra', 'M-01')}.pdf",
            filetypes=[("Archivo PDF", "*.pdf")]
        )
        if not ruta:
            return
        try:
            doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            est = obtener_estilos_pdf()
            elems = crear_cabecera_pdf(est, self.titulo, self.codigo_norma)
            elems.append(crear_tabla_metadatos(self.controller.datos_proyecto))
            elems.append(Spacer(1, 10))

            elems.append(Paragraph("CONDICIONES DE ENSAYO", est["seccion"]))
            elems.append(Paragraph(f"Horno de secado a {self.datos_calculados['temp']:.1f} °C durante {self.datos_calculados['tiempo']:.1f} horas.", est["celda_normal"]))
            elems.append(Spacer(1, 8))

            elems.append(Paragraph("REGISTRO DE PESADAS Y RESULTADOS", est["seccion"]))
            t_data = [["N°", "N° de\nrecipiente", "Masa del\nrecipiente M1 (g)", "Masa recip. + suelo\nhúmedo M2 (g)", "Masa recip. + suelo\nseco M3 (g)", "Masa de\nagua Mw (g)", "Masa de suelo\nseco Ms (g)", "Humedad\nw (%)"]]
            for d in self.datos_calculados["determinaciones"]:
                t_data.append([
                    str(d["num"]), d["id"], f"{d['mr']:.2f}", f"{d['mh']:.2f}", f"{d['ms']:.2f}",
                    f"{d['mw']:.1f}", f"{d['mss']:.1f}", f"{d['w']:.1f} %"
                ])
            t_data.append(["", "", "", "", "", "", "PROMEDIO (w):", f"{self.datos_calculados['promedio']:.1f} %"])

            tabla = Table(t_data, colWidths=[25, 55, 75, 100, 100, 60, 65, 60])
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(PRIMARY_LIGHT)),
                ("FONTNAME", (-2, -1), (-1, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elems.append(tabla)
            elems.append(Spacer(1, 14))
            elems.append(crear_bloque_firmas(est))

            doc.build(elems)
            if messagebox.askyesno("PDF Generado", f"Informe guardado con éxito:\n{ruta}\n\n¿Desea abrirlo ahora?"):
                os.startfile(ruta)
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))

# -------------------------------------------------------------------
# ENSAYO 02: PESO VOLUMÉTRICO Y DENSIDAD (NTP 339.139 / ASTM D7263)
# -------------------------------------------------------------------
class PesoVolumetrico(BaseEnsayo):
    titulo = "02. PESO VOLUMÉTRICO Y DENSIDAD"
    subtitulo = "Densidad natural húmeda, seca y peso unitario según NTP 339.139 / ASTM D7263"
    codigo_norma = "NTP 339.139 • ASTM D7263 • MTC E 112"
    clave_ensayo = "volumetrico"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        scroll_in = ctk.CTkScrollableFrame(self.panel_izquierdo, fg_color="transparent")
        scroll_in.pack(fill="both", expand=True)

        # Selector de método
        f_metodo = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        f_metodo.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(f_metodo, text="Método de Determinación:", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=12, pady=8)
        self.metodo_var = tk.StringVar(value="parafina")
        self.seg_metodo = ctk.CTkSegmentedButton(
            f_metodo,
            values=["Parafina (NTP 339.139)", "Cilindro / Molde (ASTM D7263)"],
            command=self.cambiar_metodo
        )
        self.seg_metodo.set("Parafina (NTP 339.139)")
        self.seg_metodo.pack(side="right", padx=12, pady=6)

        # Humedad del suelo y sincronización
        f_hum = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        f_hum.pack(fill="x", pady=4)
        ctk.CTkLabel(f_hum, text="Contenido de Humedad (w) [%]:", font=ctk.CTkFont(size=11, weight="bold"), text_color=NEUTRAL_HEADING).pack(side="left", padx=12, pady=8)
        self.e_hum = ctk.CTkEntry(f_hum, width=80, height=28, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.e_hum.pack(side="left", padx=6)
        crear_boton(f_hum, "Sincronizar desde Ensayo 01", self.sincronizar_humedad, color=PRIMARY_LIGHT, hover=PRIMARY_BORDER, width=170, height=26, icon="🔗").pack(side="right", padx=12)
        f_hum.winfo_children()[-1].configure(text_color=PRIMARY)

        # Formulario Parafina
        self.card_parafina = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_parafina.pack(fill="x", pady=4)
        hdr_par = ctk.CTkFrame(self.card_parafina, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
        hdr_par.pack(fill="x", padx=4, pady=4)
        hdr_par.pack_propagate(False)
        ctk.CTkLabel(hdr_par, text="🕯  Método Muestra Parafinada (NTP 339.139)", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=10, pady=4)

        f_dens_p = ctk.CTkFrame(self.card_parafina, fg_color="transparent")
        f_dens_p.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(f_dens_p, text="Densidad de la Parafina (ρp):", font=ctk.CTkFont(size=11), text_color=NEUTRAL_BODY).pack(side="left")
        self.e_rho_parafina = ctk.CTkEntry(f_dens_p, width=70, height=26, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.e_rho_parafina.insert(0, "0.87")
        self.e_rho_parafina.pack(side="left", padx=6)
        ctk.CTkLabel(f_dens_p, text="g/cm³", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_MUTED).pack(side="left")

        self.filas_parafina = []
        f_tp = ctk.CTkFrame(self.card_parafina, fg_color="transparent")
        f_tp.pack(fill="x", padx=6, pady=4)
        headers_p = ["Prueba", "M. Suelo (Mm) [g]", "M. Parafinada (Mm+p) [g]", "M. Sumergida [g]"]
        cols_wp = [50, 130, 150, 130]
        hf_p = ctk.CTkFrame(f_tp, fg_color=CARD_BG_ALT, height=26)
        hf_p.pack(fill="x", pady=2)
        for h, w in zip(headers_p, cols_wp):
            ctk.CTkLabel(hf_p, text=h, font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=w).pack(side="left", padx=2)

        for i in range(1, 3):
            rf = ctk.CTkFrame(f_tp, fg_color="transparent")
            rf.pack(fill="x", pady=2)
            ctk.CTkLabel(rf, text=f"Prueba {i}", font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY, width=50).pack(side="left", padx=2)
            e_mm = ctk.CTkEntry(rf, height=26, width=130, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_mm.pack(side="left", padx=2)
            e_mmp = ctk.CTkEntry(rf, height=26, width=150, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_mmp.pack(side="left", padx=2)
            e_msum = ctk.CTkEntry(rf, height=26, width=130, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_msum.pack(side="left", padx=2)
            self.filas_parafina.append({"num": i, "mm": e_mm, "mmp": e_mmp, "msum": e_msum})

        # Formulario Cilindro (oculto por defecto)
        self.card_cilindro = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        hdr_cil = ctk.CTkFrame(self.card_cilindro, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
        hdr_cil.pack(fill="x", padx=4, pady=4)
        hdr_cil.pack_propagate(False)
        ctk.CTkLabel(hdr_cil, text="🥫  Método del Cilindro / Molde (ASTM D7263)", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=10, pady=4)

        self.form_cilindro = TablaFormulario(self.card_cilindro)
        self.form_cilindro.pack(fill="x", padx=6, pady=4)
        self.form_cilindro.agregar_fila("mm", "Masa del molde vacío (Mm)", "g", "4178.0")
        self.form_cilindro.agregar_fila("mts", "Masa molde + suelo húmedo (Mts)", "g", "6186.8")
        self.form_cilindro.agregar_fila("vol", "Volumen interior del molde (V)", "cm³", "944.0")

        # Botonera
        b_bar = ctk.CTkFrame(self.panel_izquierdo, fg_color="transparent")
        b_bar.pack(fill="x", pady=8)
        crear_boton(b_bar, "Calcular", self.calcular, color=PRIMARY, hover=PRIMARY_HOVER, icon="⚡").pack(side="left", padx=3, fill="x", expand=True)
        crear_boton(b_bar, "Ejemplo (Demo)", self.cargar_demo, color=PRIMARY_LIGHT, hover=PRIMARY_BORDER, icon="🧪").pack(side="left", padx=3, fill="x", expand=True)
        b_bar.winfo_children()[-1].configure(text_color=PRIMARY)
        crear_boton(b_bar, "Limpiar", self.limpiar, color=NEUTRAL_MUTED, hover=NEUTRAL_BODY, icon="🗑").pack(side="left", padx=3, fill="x", expand=True)

    def cambiar_metodo(self, opcion):
        if "Parafina" in opcion:
            self.card_parafina.pack(fill="x", pady=4)
            self.card_cilindro.pack_forget()
            self.metodo_var.set("parafina")
        else:
            self.card_parafina.pack_forget()
            self.card_cilindro.pack(fill="x", pady=4)
            self.metodo_var.set("cilindro")

    def sincronizar_humedad(self):
        h = self.controller.geo_state["ensayos"].get("humedad", {})
        if h and "promedio" in h:
            self.e_hum.delete(0, "end")
            self.e_hum.insert(0, f"{h['promedio']:.2f}")
            messagebox.showinfo("Sincronización Exitosa", f"Humedad sincronizada desde Ensayo 01:\nw = {h['promedio']:.2f} %")
        else:
            messagebox.showwarning("Sin Datos de Humedad", "Aún no se ha calculado el Ensayo 01 (Contenido de Humedad). Ingrésela manualmente.")

    def calcular(self):
        try:
            metodo = self.metodo_var.get()
            w_str = self.e_hum.get().strip()
            w = float(w_str) if w_str else None

            if metodo == "parafina":
                rho_p = float(self.e_rho_parafina.get().strip() or 0.87)
                pruebas = []
                for r in self.filas_parafina:
                    mm_s, mmp_s, msum_s = r["mm"].get().strip(), r["mmp"].get().strip(), r["msum"].get().strip()
                    if not mm_s and not mmp_s and not msum_s:
                        continue
                    if not mm_s or not mmp_s or not msum_s:
                        raise ValueError(f"En Prueba {r['num']}, complete todas las pesadas.")
                    mm, mmp, msum = float(mm_s), float(mmp_s), float(msum_s)
                    if mmp <= mm:
                        raise ValueError(f"En Prueba {r['num']}, la masa parafinada debe ser mayor a la masa de suelo.")
                    vmp = mmp - msum
                    mp = mmp - mm
                    vp = mp / rho_p
                    vm = vmp - vp
                    if vm <= 0:
                        raise ValueError(f"En Prueba {r['num']}, el volumen de suelo es inválido.")
                    rho_h = mm / vm
                    gamma_h = rho_h * 9.80665
                    rho_d = rho_h / (1.0 + w / 100.0) if w is not None else None
                    gamma_d = gamma_h / (1.0 + w / 100.0) if w is not None else None
                    pruebas.append({
                        "num": r["num"], "mm": mm, "mmp": mmp, "msum": msum,
                        "vmp": vmp, "mp": mp, "vp": vp, "vm": vm,
                        "rho_h": rho_h, "gamma_h": gamma_h, "rho_d": rho_d, "gamma_d": gamma_d
                    })

                if not pruebas:
                    raise ValueError("Ingrese datos en al menos una prueba parafinada.")

                prom_rho_h = sum(p["rho_h"] for p in pruebas) / len(pruebas)
                prom_gamma_h = sum(p["gamma_h"] for p in pruebas) / len(pruebas)
                prom_rho_d = sum(p["rho_d"] for p in pruebas) / len(pruebas) if w is not None else None
                prom_gamma_d = sum(p["gamma_d"] for p in pruebas) / len(pruebas) if w is not None else None

                self.datos_calculados = {
                    "metodo": "parafina",
                    "pruebas": pruebas,
                    "humedad": w,
                    "rho_humeda": prom_rho_h,
                    "gamma_kn_m3": prom_gamma_h,
                    "rho_seca": prom_rho_d,
                    "gamma_seca": prom_gamma_d,
                }
            else:
                mm = float(self.form_cilindro.get("mm"))
                mts = float(self.form_cilindro.get("mts"))
                vol = float(self.form_cilindro.get("vol"))
                if mts <= mm or vol <= 0:
                    raise ValueError("Los datos del molde son incoherentes.")
                msuelo = mts - mm
                rho_h = msuelo / vol
                gamma_h = rho_h * 9.80665
                rho_d = rho_h / (1.0 + w / 100.0) if w is not None else None
                gamma_d = gamma_h / (1.0 + w / 100.0) if w is not None else None

                self.datos_calculados = {
                    "metodo": "cilindro",
                    "mm": mm, "mts": mts, "v": vol, "msuelo": msuelo,
                    "humedad": w,
                    "rho_humeda": rho_h,
                    "gamma_kn_m3": gamma_h,
                    "rho_seca": rho_d,
                    "gamma_seca": gamma_d,
                }

            self.calculado = True
            self.controller.geo_state["ensayos"]["volumetrico"] = self.datos_calculados
            self.mostrar_resultados()
            messagebox.showinfo("Cálculo Exitoso", f"Densidad húmeda: {self.datos_calculados['rho_humeda']:.3f} g/cm³\nPeso volumétrico: {self.datos_calculados['gamma_kn_m3']:.2f} kN/m³")

        except Exception as e:
            messagebox.showerror("Error en Peso Volumétrico", str(e))

    def mostrar_resultados(self):
        for w in self.contenedor_resultados.winfo_children():
            w.destroy()

        d = self.datos_calculados
        res_card = ctk.CTkFrame(self.contenedor_resultados, fg_color=PRIMARY_LIGHT, corner_radius=8, border_width=1, border_color=PRIMARY_BORDER)
        res_card.pack(fill="x", pady=(4, 10))

        c_grid = ctk.CTkFrame(res_card, fg_color="transparent")
        c_grid.pack(fill="x", padx=10, pady=8)
        c_grid.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(c_grid, text="DENSIDAD HÚMEDA NATURAL (ρ):", font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY).grid(row=0, column=0, pady=1)
        ctk.CTkLabel(c_grid, text=f"{d['rho_humeda']:.3f} g/cm³", font=ctk.CTkFont(size=20, weight="bold"), text_color=PRIMARY).grid(row=1, column=0, pady=1)

        ctk.CTkLabel(c_grid, text="PESO VOLUMÉTRICO HÚMEDO (γ):", font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY).grid(row=0, column=1, pady=1)
        ctk.CTkLabel(c_grid, text=f"{d['gamma_kn_m3']:.2f} kN/m³", font=ctk.CTkFont(size=20, weight="bold"), text_color=PRIMARY).grid(row=1, column=1, pady=1)

        if d.get("rho_seca"):
            ctk.CTkLabel(c_grid, text="DENSIDAD SECA (ρd):", font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_GREEN).grid(row=2, column=0, pady=(8, 1))
            ctk.CTkLabel(c_grid, text=f"{d['rho_seca']:.3f} g/cm³", font=ctk.CTkFont(size=18, weight="bold"), text_color=ACCENT_GREEN).grid(row=3, column=0, pady=1)

            ctk.CTkLabel(c_grid, text="PESO VOLUMÉTRICO SECO (γd):", font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_GREEN).grid(row=2, column=1, pady=(8, 1))
            ctk.CTkLabel(c_grid, text=f"{d['gamma_seca']:.2f} kN/m³", font=ctk.CTkFont(size=18, weight="bold"), text_color=ACCENT_GREEN).grid(row=3, column=1, pady=1)

        # Cuadro de resumen detallado
        t_frame = ctk.CTkFrame(self.contenedor_resultados, fg_color=CARD_BG, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        t_frame.pack(fill="x", pady=6)
        params = [
            ("Método empleado", "Muestra Parafinada" if d["metodo"] == "parafina" else "Cilindro / Molde"),
            ("Contenido de humedad (w)", f"{d['humedad']:.2f} %" if d.get("humedad") else "No especificado"),
            ("Densidad húmeda (kg/m³)", f"{d['rho_humeda'] * 1000.0:.1f} kg/m³"),
            ("Densidad seca (kg/m³)", f"{d['rho_seca'] * 1000.0:.1f} kg/m³" if d.get("rho_seca") else "---"),
        ]
        for p, v in params:
            rf = ctk.CTkFrame(t_frame, fg_color="transparent")
            rf.pack(fill="x", padx=10, pady=3)
            ctk.CTkLabel(rf, text=p, font=ctk.CTkFont(size=11), text_color=NEUTRAL_BODY).pack(side="left")
            ctk.CTkLabel(rf, text=v, font=ctk.CTkFont(size=11, weight="bold"), text_color=NEUTRAL_HEADING).pack(side="right")

    def cargar_demo(self):
        self.e_hum.delete(0, "end"); self.e_hum.insert(0, "10.68")
        if self.metodo_var.get() == "parafina":
            self.filas_parafina[0]["mm"].delete(0, "end"); self.filas_parafina[0]["mm"].insert(0, "158.40")
            self.filas_parafina[0]["mmp"].delete(0, "end"); self.filas_parafina[0]["mmp"].insert(0, "165.20")
            self.filas_parafina[0]["msum"].delete(0, "end"); self.filas_parafina[0]["msum"].insert(0, "76.50")

            self.filas_parafina[1]["mm"].delete(0, "end"); self.filas_parafina[1]["mm"].insert(0, "182.10")
            self.filas_parafina[1]["mmp"].delete(0, "end"); self.filas_parafina[1]["mmp"].insert(0, "189.90")
            self.filas_parafina[1]["msum"].delete(0, "end"); self.filas_parafina[1]["msum"].insert(0, "88.20")
        else:
            self.form_cilindro.set("mm", "4178.0")
            self.form_cilindro.set("mts", "6186.8")
            self.form_cilindro.set("vol", "944.0")
        self.calcular()

    def exportar_pdf(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar Informe Técnico de Peso Volumétrico",
            defaultextension=".pdf",
            initialfile=f"Informe_Peso_Volumetrico_{self.controller.datos_proyecto.get('muestra', 'M-01')}.pdf",
            filetypes=[("Archivo PDF", "*.pdf")]
        )
        if not ruta:
            return
        try:
            doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            est = obtener_estilos_pdf()
            elems = crear_cabecera_pdf(est, self.titulo, self.codigo_norma)
            elems.append(crear_tabla_metadatos(self.controller.datos_proyecto))
            elems.append(Spacer(1, 10))

            elems.append(Paragraph("SÍNTESIS DE RESULTADOS", est["seccion"]))
            d = self.datos_calculados
            t_data = [
                ["Parámetro", "Símbolo", "Valor Obtenido", "Unidad"],
                ["Densidad húmeda natural", "ρ", f"{d['rho_humeda']:.4f}", "g/cm³"],
                ["Peso volumétrico húmedo", "γ", f"{d['gamma_kn_m3']:.3f}", "kN/m³"],
                ["Densidad seca", "ρd", f"{d['rho_seca']:.4f}" if d.get('rho_seca') else "---", "g/cm³"],
                ["Peso volumétrico seco", "γd", f"{d['gamma_seca']:.3f}" if d.get('gamma_seca') else "---", "kN/m³"],
                ["Contenido de humedad", "w", f"{d['humedad']:.2f} %" if d.get('humedad') else "---", "%"],
            ]
            t = Table(t_data, colWidths=[200, 70, 120, 100])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elems.append(t)
            elems.append(Spacer(1, 16))
            elems.append(crear_bloque_firmas(est))

            doc.build(elems)
            if messagebox.askyesno("PDF Generado", f"Informe guardado con éxito:\n{ruta}\n\n¿Desea abrirlo ahora?"):
                os.startfile(ruta)
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))

# -------------------------------------------------------------------
# ENSAYO 03: GRAVEDAD ESPECÍFICA (ASTM D854 / NTP 339.131)
# -------------------------------------------------------------------
class GravedadEspecifica(BaseEnsayo):
    titulo = "03. GRAVEDAD ESPECÍFICA (Gs)"
    subtitulo = "Gravedad específica de los sólidos mediante picnómetro de agua según ASTM D854"
    codigo_norma = "ASTM D854 • NTP 339.131 • MTC E 107"
    clave_ensayo = "gravedad"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        scroll_in = ctk.CTkScrollableFrame(self.panel_izquierdo, fg_color="transparent")
        scroll_in.pack(fill="both", expand=True)

        self.card_pic = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_pic.pack(fill="x", pady=4)
        hdr = ctk.CTkFrame(self.card_pic, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
        hdr.pack(fill="x", padx=4, pady=4)
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🍶  Ensayos con Picnómetro y Corrección Térmica (K)", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=10, pady=4)

        self.filas_pic = []
        f_tp = ctk.CTkFrame(self.card_pic, fg_color="transparent")
        f_tp.pack(fill="x", padx=6, pady=4)
        headers = ["Prueba", "T° [°C]", "Picn.+Agua (Mpw) [g]", "Suelo Seco (Ms) [g]", "Picn.+Suelo+Agua [g]"]
        cols_w = [55, 65, 125, 115, 125]
        hf = ctk.CTkFrame(f_tp, fg_color=CARD_BG_ALT, height=26)
        hf.pack(fill="x", pady=2)
        for h, w in zip(headers, cols_w):
            ctk.CTkLabel(hf, text=h, font=ctk.CTkFont(size=9, weight="bold"), text_color=NEUTRAL_HEADING, width=w).pack(side="left", padx=2)

        for i in range(1, 3):
            rf = ctk.CTkFrame(f_tp, fg_color="transparent")
            rf.pack(fill="x", pady=2)
            ctk.CTkLabel(rf, text=f"P-{i}", font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY, width=55).pack(side="left", padx=2)
            e_t = ctk.CTkEntry(rf, height=26, width=65, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_t.insert(0, "16.5")
            e_t.pack(side="left", padx=2)
            e_mpw = ctk.CTkEntry(rf, height=26, width=125, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_mpw.pack(side="left", padx=2)
            e_ms = ctk.CTkEntry(rf, height=26, width=115, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_ms.pack(side="left", padx=2)
            e_mpsw = ctk.CTkEntry(rf, height=26, width=125, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_mpsw.pack(side="left", padx=2)
            self.filas_pic.append({"num": i, "temp": e_t, "mpw": e_mpw, "ms": e_ms, "mpsw": e_mpsw})

        # Botonera
        b_bar = ctk.CTkFrame(self.panel_izquierdo, fg_color="transparent")
        b_bar.pack(fill="x", pady=8)
        crear_boton(b_bar, "Calcular", self.calcular, color=PRIMARY, hover=PRIMARY_HOVER, icon="⚡").pack(side="left", padx=3, fill="x", expand=True)
        crear_boton(b_bar, "Ejemplo (Demo)", self.cargar_demo, color=PRIMARY_LIGHT, hover=PRIMARY_BORDER, icon="🧪").pack(side="left", padx=3, fill="x", expand=True)
        b_bar.winfo_children()[-1].configure(text_color=PRIMARY)
        crear_boton(b_bar, "Limpiar", self.limpiar, color=NEUTRAL_MUTED, hover=NEUTRAL_BODY, icon="🗑").pack(side="left", padx=3, fill="x", expand=True)

    def calcular(self):
        try:
            pruebas = []
            for r in self.filas_pic:
                t_s = r["temp"].get().strip()
                mpw_s = r["mpw"].get().strip()
                ms_s = r["ms"].get().strip()
                mpsw_s = r["mpsw"].get().strip()
                if not mpw_s and not ms_s and not mpsw_s:
                    continue
                if not t_s or not mpw_s or not ms_s or not mpsw_s:
                    raise ValueError(f"En Prueba {r['num']}, complete todos los campos.")
                temp, mpw, ms, mpsw = float(t_s), float(mpw_s), float(ms_s), float(mpsw_s)
                rho_w, k = obtener_propiedades_agua(temp)
                desalojada = ms + mpw - mpsw
                if desalojada <= 0:
                    raise ValueError(f"En Prueba {r['num']}, masa de agua desalojada inválida ({desalojada:.2f}g).")
                gt = ms / desalojada
                g20 = k * gt
                pruebas.append({
                    "num": r["num"], "temp": temp, "rho_w": rho_w, "k": k,
                    "mpw": mpw, "ms": ms, "mpsw": mpsw, "desalojada": desalojada,
                    "gt": gt, "g20": g20
                })

            if not pruebas:
                raise ValueError("Ingrese datos en al menos una prueba picnométrica.")

            prom_gs = sum(p["g20"] for p in pruebas) / len(pruebas)
            prom_gt = sum(p["gt"] for p in pruebas) / len(pruebas)
            prom_temp = sum(p["temp"] for p in pruebas) / len(pruebas)

            self.datos_calculados = {
                "pruebas": pruebas,
                "gs": prom_gs,
                "gt": prom_gt,
                "temp": prom_temp,
            }
            self.calculado = True
            self.controller.geo_state["ensayos"]["gravedad"] = self.datos_calculados
            self.mostrar_resultados()
            messagebox.showinfo("Cálculo Exitoso", f"Gravedad Específica corregida a 20°C:\n\nGs = {prom_gs:.3f}")

        except Exception as e:
            messagebox.showerror("Error en Gravedad Específica", str(e))

    def mostrar_resultados(self):
        for w in self.contenedor_resultados.winfo_children():
            w.destroy()

        d = self.datos_calculados
        res_card = ctk.CTkFrame(self.contenedor_resultados, fg_color=PRIMARY_LIGHT, corner_radius=8, border_width=1, border_color=PRIMARY_BORDER)
        res_card.pack(fill="x", pady=(4, 10))
        ctk.CTkLabel(res_card, text="GRAVEDAD ESPECÍFICA CORREGIDA (Gs a 20°C):", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(pady=(8, 2))
        ctk.CTkLabel(res_card, text=f"{d['gs']:.3f}", font=ctk.CTkFont(size=26, weight="bold"), text_color=PRIMARY).pack(pady=(0, 4))
        ctk.CTkLabel(res_card, text=f"Promedio a T°={d['temp']:.1f}°C: Gt = {d['gt']:.3f}", font=ctk.CTkFont(size=10, slant="italic"), text_color=NEUTRAL_MUTED).pack(pady=(0, 6))

        # Detalle por prueba
        t_frame = ctk.CTkFrame(self.contenedor_resultados, fg_color=CARD_BG, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        t_frame.pack(fill="x", pady=4)
        for p in d["pruebas"]:
            f = ctk.CTkFrame(t_frame, fg_color="transparent")
            f.pack(fill="x", padx=10, pady=4)
            ctk.CTkLabel(f, text=f"Prueba {p['num']} (T={p['temp']:.1f}°C, K={p['k']:.5f}):", font=ctk.CTkFont(size=11, weight="bold"), text_color=NEUTRAL_HEADING).pack(side="left")
            ctk.CTkLabel(f, text=f"Gt={p['gt']:.3f}  →  Gs(20°C)={p['g20']:.3f}", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_GREEN).pack(side="right")

    def cargar_demo(self):
        self.filas_pic[0]["temp"].delete(0, "end"); self.filas_pic[0]["temp"].insert(0, "16.5")
        self.filas_pic[0]["mpw"].delete(0, "end"); self.filas_pic[0]["mpw"].insert(0, "650.00")
        self.filas_pic[0]["ms"].delete(0, "end"); self.filas_pic[0]["ms"].insert(0, "50.00")
        self.filas_pic[0]["mpsw"].delete(0, "end"); self.filas_pic[0]["mpsw"].insert(0, "681.30")

        self.filas_pic[1]["temp"].delete(0, "end"); self.filas_pic[1]["temp"].insert(0, "16.5")
        self.filas_pic[1]["mpw"].delete(0, "end"); self.filas_pic[1]["mpw"].insert(0, "650.00")
        self.filas_pic[1]["ms"].delete(0, "end"); self.filas_pic[1]["ms"].insert(0, "50.00")
        self.filas_pic[1]["mpsw"].delete(0, "end"); self.filas_pic[1]["mpsw"].insert(0, "681.25")
        self.calcular()

    def exportar_pdf(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar Informe Técnico de Gravedad Específica",
            defaultextension=".pdf",
            initialfile=f"Informe_Gravedad_Especifica_{self.controller.datos_proyecto.get('muestra', 'M-01')}.pdf",
            filetypes=[("Archivo PDF", "*.pdf")]
        )
        if not ruta:
            return
        try:
            doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            est = obtener_estilos_pdf()
            elems = crear_cabecera_pdf(est, self.titulo, self.codigo_norma)
            elems.append(crear_tabla_metadatos(self.controller.datos_proyecto))
            elems.append(Spacer(1, 10))

            elems.append(Paragraph("REGISTRO DE DETERMINACIONES PICNOMÉTRICAS", est["seccion"]))
            t_data = [["N°", "T° (°C)", "M. Picn.+Agua (g)", "M. Suelo Seco (g)", "M. Picn.+Suelo+Agua (g)", "Agua Desalojada (g)", "Factor K", "Gs (20°C)"]]
            for p in self.datos_calculados["pruebas"]:
                t_data.append([
                    str(p["num"]), f"{p['temp']:.1f}", f"{p['mpw']:.2f}", f"{p['ms']:.2f}",
                    f"{p['mpsw']:.2f}", f"{p['desalojada']:.2f}", f"{p['k']:.5f}", f"{p['g20']:.3f}"
                ])
            t_data.append(["", "", "", "", "", "", "PROMEDIO (Gs):", f"{self.datos_calculados['gs']:.3f}"])

            t = Table(t_data, colWidths=[25, 45, 85, 75, 95, 75, 55, 65])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(PRIMARY_LIGHT)),
                ("FONTNAME", (-2, -1), (-1, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elems.append(t)
            elems.append(Spacer(1, 16))
            elems.append(crear_bloque_firmas(est))

            doc.build(elems)
            if messagebox.askyesno("PDF Generado", f"Informe guardado con éxito:\n{ruta}\n\n¿Desea abrirlo ahora?"):
                os.startfile(ruta)
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))

# -------------------------------------------------------------------
# ENSAYO 04: ANÁLISIS GRANULOMÉTRICO (ASTM D6913 / NTP 339.128)
# -------------------------------------------------------------------
class Granulometria(BaseEnsayo):
    titulo = "04. ANÁLISIS GRANULOMÉTRICO POR TAMIZADO"
    subtitulo = "Distribución de tamaños de partículas y curva granulométrica según ASTM D6913"
    codigo_norma = "ASTM D6913 • NTP 339.128 • MTC E 107"
    clave_ensayo = "granulometria"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        scroll_in = ctk.CTkScrollableFrame(self.panel_izquierdo, fg_color="transparent")
        scroll_in.pack(fill="both", expand=True)

        # 1. Selector de Método de Ensayo
        f_metodo = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        f_metodo.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(f_metodo, text="Método de Tamizado:", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=10, pady=8)
        self.metodo_var = tk.StringVar(value="a-compuesto")
        self.seg_metodo = ctk.CTkSegmentedButton(
            f_metodo,
            values=["Compuesto (2 col - TM > 3/4\")", "Simple (1 col - TM < 3/4\")"],
            command=self.cambiar_metodo
        )
        self.seg_metodo.set("Compuesto (2 col - TM > 3/4\")")
        self.seg_metodo.pack(side="right", padx=10, pady=6)

        # 1b. Lector de hojas escaneadas (foto o PDF)
        f_lector = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        f_lector.pack(fill="x", pady=(0, 6))
        fila_lector = ctk.CTkFrame(f_lector, fg_color="transparent")
        fila_lector.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(fila_lector, text="Leer datos desde foto o PDF:", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left")
        self.btn_lector = crear_boton(fila_lector, "Subir foto / PDF", self.leer_desde_archivo, color=PRIMARY, hover=PRIMARY_HOVER, icon="📄", width=160, height=30)
        self.btn_lector.pack(side="right")
        self.var_autocalc = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(fila_lector, text="Calcular al terminar", variable=self.var_autocalc, font=ctk.CTkFont(size=10), text_color=NEUTRAL_BODY, checkbox_width=18, checkbox_height=18).pack(side="right", padx=12)
        self.lbl_lector = ctk.CTkLabel(
            f_lector,
            text="Suba la hoja escaneada y el programa rellenará el formulario. Los campos leídos quedan con borde naranja: revíselos.",
            font=ctk.CTkFont(size=10), text_color=NEUTRAL_MUTED, wraplength=470, justify="left", anchor="w"
        )
        self.lbl_lector.pack(fill="x", padx=10, pady=(0, 8))
        self._cola_lector = queue.Queue()

        # 2. Datos del Ensayo (Identificación y Encabezado)
        self.card_hdr = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_hdr.pack(fill="x", pady=4)
        hdr_box = ctk.CTkFrame(self.card_hdr, fg_color=PRIMARY_LIGHT, corner_radius=6, height=30)
        hdr_box.pack(fill="x", padx=4, pady=4)
        hdr_box.pack_propagate(False)
        ctk.CTkLabel(hdr_box, text="📋  Identificación y Masas Generales", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=8, pady=2)

        f_hgrid = ctk.CTkFrame(self.card_hdr, fg_color="transparent")
        f_hgrid.pack(fill="x", padx=8, pady=4)
        f_hgrid.grid_columnconfigure((0, 1), weight=1)

        # Row 0: Calicata y Muestra
        f0_1 = ctk.CTkFrame(f_hgrid, fg_color="transparent")
        f0_1.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(f0_1, text="Calicata/Cantera:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=115, anchor="w").pack(side="left")
        self.e_calicata = ctk.CTkEntry(f0_1, height=24, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.e_calicata.insert(0, "C-1")
        self.e_calicata.pack(side="left", fill="x", expand=True)

        f0_2 = ctk.CTkFrame(f_hgrid, fg_color="transparent")
        f0_2.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(f0_2, text="Muestra N°:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=95, anchor="w").pack(side="left")
        self.e_muestra = ctk.CTkEntry(f0_2, height=24, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.e_muestra.insert(0, "M-1")
        self.e_muestra.pack(side="left", fill="x", expand=True)

        # Row 1: Profundidad y Equipos
        f1_1 = ctk.CTkFrame(f_hgrid, fg_color="transparent")
        f1_1.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(f1_1, text="Profundidad [m]:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=115, anchor="w").pack(side="left")
        self.e_profundidad = ctk.CTkEntry(f1_1, height=24, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.e_profundidad.insert(0, "15.60")
        self.e_profundidad.pack(side="left", fill="x", expand=True)

        f1_2 = ctk.CTkFrame(f_hgrid, fg_color="transparent")
        f1_2.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(f1_2, text="Horno / Balanza:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=95, anchor="w").pack(side="left")
        self.e_horno = ctk.CTkEntry(f1_2, height=24, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.e_horno.insert(0, "HR-3 / BL-18")
        self.e_horno.pack(side="left", fill="x", expand=True)

        # Row 2: Masa Total húmeda y Recipiente
        f2_1 = ctk.CTkFrame(f_hgrid, fg_color="transparent")
        f2_1.grid(row=2, column=0, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(f2_1, text="Masa Total Húm. [g]:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=115, anchor="w").pack(side="left")
        self.e_masa_total = ctk.CTkEntry(f2_1, height=24, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.e_masa_total.insert(0, "25939.0")
        self.e_masa_total.pack(side="left", fill="x", expand=True)

        f2_2 = ctk.CTkFrame(f_hgrid, fg_color="transparent")
        f2_2.grid(row=2, column=1, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(f2_2, text="Recipiente [g]:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=95, anchor="w").pack(side="left")
        self.e_recipiente = ctk.CTkEntry(f2_2, height=24, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.e_recipiente.insert(0, "1490 / 123.3")
        self.e_recipiente.pack(side="left", fill="x", expand=True)

        # Row 3: Masa Parte Gruesa Húm. y Masa Parte Fina Húm.
        f3_1 = ctk.CTkFrame(f_hgrid, fg_color="transparent")
        f3_1.grid(row=3, column=0, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(f3_1, text="M. Gruesa Húm. [g]:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=115, anchor="w").pack(side="left")
        self.e_masa_gruesa = ctk.CTkEntry(f3_1, height=24, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.e_masa_gruesa.insert(0, "19703.0")
        self.e_masa_gruesa.pack(side="left", fill="x", expand=True)

        f3_2 = ctk.CTkFrame(f_hgrid, fg_color="transparent")
        f3_2.grid(row=3, column=1, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(f3_2, text="M. Fina Húm. [g]:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=95, anchor="w").pack(side="left")
        self.e_masa_fina = ctk.CTkEntry(f3_2, height=24, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.e_masa_fina.insert(0, "6236.0")
        self.e_masa_fina.pack(side="left", fill="x", expand=True)

        # 3. Control de Secado (Para Tamizado Compuesto)
        self.card_secado = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_secado.pack(fill="x", pady=4)
        hdr_s = ctk.CTkFrame(self.card_secado, fg_color=PRIMARY_LIGHT, corner_radius=6, height=30)
        hdr_s.pack(fill="x", padx=4, pady=4)
        hdr_s.pack_propagate(False)
        ctk.CTkLabel(hdr_s, text="🔥  Control de Secado (Cálculo Automático de Humedades y Pérdidas)", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=8, pady=2)

        f_sgrid = ctk.CTkFrame(self.card_secado, fg_color="transparent")
        f_sgrid.pack(fill="x", padx=8, pady=4)
        f_sgrid.grid_columnconfigure((0, 1), weight=1)

        # Columna izquierda: Parte Gruesa
        cg_box = ctk.CTkFrame(f_sgrid, fg_color=CARD_BG_ALT, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        cg_box.grid(row=0, column=0, sticky="nsew", padx=3, pady=2)
        ctk.CTkLabel(cg_box, text="PARTE GRUESA (C-g)", font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY).pack(anchor="w", padx=8, pady=(4, 2))

        row_g1 = ctk.CTkFrame(cg_box, fg_color="transparent")
        row_g1.pack(fill="x", padx=6, pady=1)
        ctk.CTkLabel(row_g1, text="g1 Masa húmeda [g]:", font=ctk.CTkFont(size=9), text_color=NEUTRAL_BODY, width=130, anchor="w").pack(side="left")
        self.sec_g1 = ctk.CTkEntry(row_g1, height=22, width=85, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.sec_g1.insert(0, "19703.0")
        self.sec_g1.pack(side="left", fill="x", expand=True)

        row_g2 = ctk.CTkFrame(cg_box, fg_color="transparent")
        row_g2.pack(fill="x", padx=6, pady=1)
        ctk.CTkLabel(row_g2, text="g2 Masa seca [g]:", font=ctk.CTkFont(size=9, weight="bold"), text_color=NEUTRAL_HEADING, width=130, anchor="w").pack(side="left")
        self.sec_g2 = ctk.CTkEntry(row_g2, height=22, width=85, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.sec_g2.insert(0, "19541.0")
        self.sec_g2.pack(side="left", fill="x", expand=True)

        row_g3 = ctk.CTkFrame(cg_box, fg_color="transparent")
        row_g3.pack(fill="x", padx=6, pady=(1, 4))
        ctk.CTkLabel(row_g3, text="g3 Masa lavada seca [g]:", font=ctk.CTkFont(size=9), text_color=NEUTRAL_BODY, width=130, anchor="w").pack(side="left")
        self.sec_g3 = ctk.CTkEntry(row_g3, height=22, width=85, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.sec_g3.insert(0, "19491.0")
        self.sec_g3.pack(side="left", fill="x", expand=True)

        # Columna derecha: Parte Fina
        cf_box = ctk.CTkFrame(f_sgrid, fg_color=CARD_BG_ALT, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        cf_box.grid(row=0, column=1, sticky="nsew", padx=3, pady=2)
        ctk.CTkLabel(cf_box, text="PARTE FINA / SUBMUESTRA (Mo)", font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY).pack(anchor="w", padx=8, pady=(4, 2))

        row_f1 = ctk.CTkFrame(cf_box, fg_color="transparent")
        row_f1.pack(fill="x", padx=6, pady=1)
        ctk.CTkLabel(row_f1, text="f1 Subm. húmeda [g]:", font=ctk.CTkFont(size=9), text_color=NEUTRAL_BODY, width=130, anchor="w").pack(side="left")
        self.sec_f1 = ctk.CTkEntry(row_f1, height=22, width=85, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.sec_f1.insert(0, "639.5")
        self.sec_f1.pack(side="left", fill="x", expand=True)

        row_f2 = ctk.CTkFrame(cf_box, fg_color="transparent")
        row_f2.pack(fill="x", padx=6, pady=1)
        ctk.CTkLabel(row_f2, text="f2 Subm. seca Mo [g]:", font=ctk.CTkFont(size=9, weight="bold"), text_color=NEUTRAL_HEADING, width=130, anchor="w").pack(side="left")
        self.sec_f2 = ctk.CTkEntry(row_f2, height=22, width=85, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.sec_f2.insert(0, "623.3")
        self.sec_f2.pack(side="left", fill="x", expand=True)

        row_f3 = ctk.CTkFrame(cf_box, fg_color="transparent")
        row_f3.pack(fill="x", padx=6, pady=(1, 4))
        ctk.CTkLabel(row_f3, text="f3 Subm. lavada [g]:", font=ctk.CTkFont(size=9), text_color=NEUTRAL_BODY, width=130, anchor="w").pack(side="left")
        self.sec_f3 = ctk.CTkEntry(row_f3, height=22, width=85, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.sec_f3.insert(0, "581.3")
        self.sec_f3.pack(side="left", fill="x", expand=True)

        # 4. Control de Masas (Para Tamizado Simple)
        self.card_simple_masas = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        hdr_sm = ctk.CTkFrame(self.card_simple_masas, fg_color=PRIMARY_LIGHT, corner_radius=6, height=30)
        hdr_sm.pack(fill="x", padx=4, pady=4)
        hdr_sm.pack_propagate(False)
        ctk.CTkLabel(hdr_sm, text="⚖  Control de Masas (Tamizado Simple)", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=8, pady=2)

        f_sm_grid = ctk.CTkFrame(self.card_simple_masas, fg_color="transparent")
        f_sm_grid.pack(fill="x", padx=8, pady=4)
        f_sm_grid.grid_columnconfigure((0, 1), weight=1)

        rsm1 = ctk.CTkFrame(f_sm_grid, fg_color="transparent")
        rsm1.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(rsm1, text="Masa Seca Total (W1) [g]:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=160, anchor="w").pack(side="left")
        self.simple_masa_total = ctk.CTkEntry(rsm1, height=24, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.simple_masa_total.insert(0, "2708.0")
        self.simple_masa_total.pack(side="left", fill="x", expand=True)

        rsm2 = ctk.CTkFrame(f_sm_grid, fg_color="transparent")
        rsm2.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(rsm2, text="Masa Seca Lavada (W0) [g]:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=160, anchor="w").pack(side="left")
        self.simple_masa_lavada = ctk.CTkEntry(rsm2, height=24, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.simple_masa_lavada.insert(0, "2708.0")
        self.simple_masa_lavada.pack(side="left", fill="x", expand=True)

        # 5. Tabla de Tamices ASTM
        self.card_tamices = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_tamices.pack(fill="x", pady=4)
        hdr_t = ctk.CTkFrame(self.card_tamices, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
        hdr_t.pack(fill="x", padx=4, pady=4)
        hdr_t.pack_propagate(False)
        ctk.CTkLabel(hdr_t, text="🔬  Juego de Tamices Estándar ASTM (ASTM D6913)", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=10, pady=4)

        f_tams = ctk.CTkFrame(self.card_tamices, fg_color="transparent")
        f_tams.pack(fill="x", padx=6, pady=4)

        self.h_frame = ctk.CTkFrame(f_tams, fg_color=CARD_BG_ALT, height=26)
        self.h_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(self.h_frame, text="Tamiz ASTM", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=95, anchor="w").pack(side="left", padx=2)
        ctk.CTkLabel(self.h_frame, text="Abertura [mm]", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=85, anchor="w").pack(side="left", padx=2)
        self.lbl_col_m1 = ctk.CTkLabel(self.h_frame, text="M-1 Gruesa [g]", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=115, anchor="w")
        self.lbl_col_m1.pack(side="left", padx=2)
        self.lbl_col_m2 = ctk.CTkLabel(self.h_frame, text="M-2 Fina [g]", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING, width=115, anchor="w")
        self.lbl_col_m2.pack(side="left", padx=2)

        self.filas_tamices_m1 = {}
        self.filas_tamices_m2 = {}
        self.filas_ui_m2 = {}

        for s in ASTM_SIEVES:
            rf = ctk.CTkFrame(f_tams, fg_color="transparent")
            rf.pack(fill="x", pady=1)

            tag_txt = ""
            tag_color = PRIMARY
            if s["id"] == "n4":
                tag_txt = " (G/A)"
                tag_color = "#2563EB"
            elif s["id"] == "n200":
                tag_txt = " (A/F)"
                tag_color = "#7C3AED"
            elif s["id"] == "n10":
                tag_txt = " (Plat.1)"
                tag_color = "#0D9488"
            elif s["id"] == "mmo":
                tag_txt = " (Lavado)"
                tag_color = "#D97706"

            lbl_nom = ctk.CTkLabel(rf, text=f"{s['nombre']}{tag_txt}", font=ctk.CTkFont(size=10, weight="bold"), text_color=tag_color, width=95, anchor="w")
            lbl_nom.pack(side="left", padx=2)

            ab_txt = f"{s['abertura']:.3f}" if s["abertura"] > 0 else "—"
            lbl_ab = ctk.CTkLabel(rf, text=ab_txt, font=ctk.CTkFont(size=10), text_color=NEUTRAL_MUTED, width=85, anchor="w")
            lbl_ab.pack(side="left", padx=2)

            e1 = ctk.CTkEntry(rf, height=24, width=115, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e1.pack(side="left", padx=2)
            self.filas_tamices_m1[s["id"]] = e1

            e2 = ctk.CTkEntry(rf, height=24, width=115, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e2.pack(side="left", padx=2)
            self.filas_tamices_m2[s["id"]] = e2
            self.filas_ui_m2[s["id"]] = (rf, e2)

            if s["id"] == "mmo":
                e1.configure(placeholder_text="Auto lavado")
                e2.configure(placeholder_text="Auto lavado")

        # Botonera
        b_bar = ctk.CTkFrame(self.panel_izquierdo, fg_color="transparent")
        b_bar.pack(fill="x", pady=8)
        crear_boton(b_bar, "Calcular", self.calcular, color=PRIMARY, hover=PRIMARY_HOVER, icon="⚡").pack(side="left", padx=2, fill="x", expand=True)
        crear_boton(b_bar, "Demo Compuesto (UNI)", self.cargar_demo_compuesto, color=PRIMARY_LIGHT, hover=PRIMARY_BORDER, icon="🏛").pack(side="left", padx=2, fill="x", expand=True)
        b_bar.winfo_children()[-1].configure(text_color=PRIMARY)
        crear_boton(b_bar, "Demo Simple", self.cargar_demo_simple, color=PRIMARY_LIGHT, hover=PRIMARY_BORDER, icon="🧪").pack(side="left", padx=2, fill="x", expand=True)
        b_bar.winfo_children()[-1].configure(text_color=PRIMARY)
        crear_boton(b_bar, "Limpiar", self.limpiar, color=NEUTRAL_MUTED, hover=NEUTRAL_BODY, icon="🗑").pack(side="left", padx=2, fill="x", expand=True)

        # Estado inicial: Compuesto
        self.cambiar_metodo("Compuesto (2 col - TM > 3/4\")")

    # ---------------------------------------------------------------
    # Lector de hojas escaneadas
    # ---------------------------------------------------------------
    COLOR_LEIDO = "#F0A500"

    def _poner(self, entry, valor):
        """Escribe un valor leído y marca el campo en naranja. Devuelve 1 si escribió algo."""
        if valor is None or str(valor).strip() == "":
            return 0
        entry.delete(0, "end")
        entry.insert(0, str(valor).strip())
        entry.configure(border_color=self.COLOR_LEIDO)
        return 1

    def _entradas_lector(self):
        return ([self.e_calicata, self.e_muestra, self.e_profundidad, self.e_horno, self.e_masa_total, self.e_recipiente,
                 self.e_masa_gruesa, self.e_masa_fina, self.sec_g1, self.sec_g2, self.sec_g3, self.sec_f1, self.sec_f2,
                 self.sec_f3, self.simple_masa_total, self.simple_masa_lavada]
                + list(self.filas_tamices_m1.values()) + list(self.filas_tamices_m2.values()))

    def aplicar_lectura(self, d):
        """Rellena el formulario con lo leído de la hoja. Devuelve cuántos campos se completaron."""
        # Empezar de cero: así no se mezclan los datos de la hoja con valores de ejemplo o anteriores
        self.limpiar()
        for e in self._entradas_lector():
            e.configure(border_color=BORDER_COLOR)
        for e in (self.e_calicata, self.e_muestra, self.e_profundidad, self.e_horno, self.e_masa_total,
                  self.e_recipiente, self.e_masa_gruesa, self.e_masa_fina):
            e.delete(0, "end")

        metodo = d.get("metodo") or ""
        valores = list(self.seg_metodo.cget("values"))      # [compuesto, simple]
        if metodo == "a-compuesto":
            self.seg_metodo.set(valores[0]); self.cambiar_metodo(valores[0])
        elif metodo in ("a-simple", "b-simple"):
            self.seg_metodo.set(valores[1]); self.cambiar_metodo(valores[1])

        n = 0
        h = d.get("encabezado") or {}
        n += self._poner(self.e_calicata, h.get("calicata"))
        n += self._poner(self.e_muestra, h.get("muestra"))
        n += self._poner(self.e_profundidad, h.get("profundidad"))
        horno = " / ".join(str(x) for x in (h.get("horno"), h.get("balanza")) if x not in (None, ""))
        n += self._poner(self.e_horno, horno)
        n += self._poner(self.e_masa_total, h.get("masa-total"))
        n += self._poner(self.e_recipiente, h.get("recipiente"))
        n += self._poner(self.e_masa_gruesa, h.get("masa-gruesa"))
        n += self._poner(self.e_masa_fina, h.get("masa-fina"))

        sec = d.get("secado") or {}
        for clave, entry in (("g1", self.sec_g1), ("g2", self.sec_g2), ("g3", self.sec_g3),
                             ("f1", self.sec_f1), ("f2", self.sec_f2), ("f3", self.sec_f3)):
            n += self._poner(entry, sec.get(clave))
        n += self._poner(self.simple_masa_total, d.get("masa_total"))
        n += self._poner(self.simple_masa_lavada, d.get("masa_lavada"))

        for sid, t in (d.get("tamices") or {}).items():
            if not isinstance(t, dict):
                continue
            if sid in self.filas_tamices_m1:
                n += self._poner(self.filas_tamices_m1[sid], t.get("m1"))
            if sid in self.filas_tamices_m2:
                n += self._poner(self.filas_tamices_m2[sid], t.get("m2"))
        return n

    def leer_desde_archivo(self):
        if lector_formatos is None or api_client is None:
            messagebox.showwarning("Falta una librería", "Para usar el lector instale 'requests' y 'pillow':\n\npip install requests pillow")
            return
        if not api_client.hay_sesion():
            messagebox.showinfo("Inicie sesión", "Para usar el lector inicie sesión en el botón ☁ Servidor (arriba a la derecha).")
            return
        ruta = filedialog.askopenfilename(
            title="Seleccione la hoja escaneada",
            filetypes=[("Foto o PDF", "*.pdf *.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("Todos los archivos", "*.*")]
        )
        if not ruta:
            return
        con_datos = any(e.get().strip() for e in list(self.filas_tamices_m1.values()) + list(self.filas_tamices_m2.values()))
        if con_datos and not messagebox.askyesno("Reemplazar datos", "El formulario ya tiene valores de tamices.\nSe reemplazarán con los de la hoja. ¿Continuar?"):
            return

        self.btn_lector.configure(state="disabled")
        self.lbl_lector.configure(text="Leyendo la hoja... (puede tardar hasta un minuto)", text_color=NEUTRAL_MUTED)

        def tarea():
            try:
                self._cola_lector.put(("ok", lector_formatos.leer_formato(ruta, "granulometria")))
            except api_client.ErrorAPI as e:
                self._cola_lector.put(("error", str(e)))
            except Exception as e:
                self._cola_lector.put(("error", f"Error inesperado: {e}"))

        threading.Thread(target=tarea, daemon=True).start()
        self.after(300, self._esperar_lector)

    def _esperar_lector(self):
        if not self.winfo_exists():
            return
        try:
            estado, contenido = self._cola_lector.get_nowait()
        except queue.Empty:
            self.after(300, self._esperar_lector)
            return
        self.btn_lector.configure(state="normal")
        if estado == "error":
            self.lbl_lector.configure(text=contenido, text_color=ACCENT_RED)
            messagebox.showerror("Lector de hojas", contenido)
            return

        n = self.aplicar_lectura(contenido)
        if not n:
            msg = "No se encontraron datos legibles en el archivo. Pruebe con una foto más nítida y completa."
            self.lbl_lector.configure(text=msg, text_color=ACCENT_RED)
            messagebox.showwarning("Lector de hojas", msg)
            return

        notas = lector_formatos.validar_granulometria(contenido)
        avisos = [t for nivel, t in notas if nivel == "aviso"]
        resumen = f"Se rellenaron {n} campos (borde naranja). " + ("Revise los avisos." if avisos else "Las sumas de la hoja cuadran.")
        self.lbl_lector.configure(text=resumen, text_color=ACCENT_RED if avisos else ACCENT_GREEN)
        if self.var_autocalc.get():
            self.calcular()
        if avisos:
            messagebox.showwarning("Revise estos datos con la hoja original", "\n\n".join(avisos))

    def cambiar_metodo(self, opcion):
        if "Compuesto" in opcion:
            self.metodo_var.set("a-compuesto")
            self.card_secado.pack(fill="x", pady=4, after=self.card_hdr)
            self.card_simple_masas.pack_forget()
            self.lbl_col_m1.configure(text="M-1 Gruesa [g]")
            if not self.lbl_col_m2.winfo_ismapped():
                self.lbl_col_m2.pack(side="left", padx=2)
            for sid, (rf, e2) in self.filas_ui_m2.items():
                if not e2.winfo_ismapped():
                    e2.pack(side="left", padx=2)
        else:
            self.metodo_var.set("a-simple")
            self.card_secado.pack_forget()
            self.card_simple_masas.pack(fill="x", pady=4, after=self.card_hdr)
            self.lbl_col_m1.configure(text="Masa Retenida [g]")
            self.lbl_col_m2.pack_forget()
            for sid, (rf, e2) in self.filas_ui_m2.items():
                e2.pack_forget()

    def calcular(self):
        try:
            metodo = self.metodo_var.get()
            compuesto = (metodo == "a-compuesto")

            items = []
            if compuesto:
                # 1. Control de Secado
                g1_s = self.sec_g1.get().strip()
                g2_s = self.sec_g2.get().strip()
                g3_s = self.sec_g3.get().strip()
                f1_s = self.sec_f1.get().strip()
                f2_s = self.sec_f2.get().strip()
                f3_s = self.sec_f3.get().strip()

                m_cg_hum = float(g1_s) if g1_s else float(self.e_masa_gruesa.get() or 0.0)
                m_cg_sec = float(g2_s) if g2_s else 0.0
                if m_cg_sec <= 0:
                    raise ValueError("Ingrese la Masa Seca de la Parte Gruesa (g2) en Control de Secado (> 0).")
                m_cg_lav = float(g3_s) if g3_s else m_cg_sec

                m_fg_sub_hum = float(f1_s) if f1_s else 0.0
                m_fg_sub_sec = float(f2_s) if f2_s else 0.0
                if m_fg_sub_sec <= 0:
                    raise ValueError("Ingrese la Masa Seca de la Submuestra Fina Mo (f2) en Control de Secado (> 0).")
                if m_fg_sub_hum < m_fg_sub_sec:
                    raise ValueError("La masa húmeda de la submuestra fina (f1) debe ser mayor o igual a la seca (f2).")
                m_fg_sub_lav = float(f3_s) if f3_s else m_fg_sub_sec

                # Humedades según norma (0.1 %)
                hum_fina = round(((m_fg_sub_hum - m_fg_sub_sec) / m_fg_sub_sec) * 100.0, 1)
                hum_gruesa = round(((m_cg_hum - m_cg_sec) / m_cg_sec) * 100.0, 1) if m_cg_hum else None

                # Masa parte fina húmeda total
                m_fg_hum_s = self.e_masa_fina.get().strip()
                if m_fg_hum_s:
                    m_fg_hum = float(m_fg_hum_s)
                else:
                    tot_s = self.e_masa_total.get().strip()
                    m_tot_h = float(tot_s) if tot_s else 0.0
                    m_fg_hum = m_tot_h - m_cg_hum if (m_tot_h and m_cg_hum) else 0.0

                if m_fg_hum <= 0:
                    raise ValueError("Ingrese la Masa de la Parte Fina húmeda (o la Masa Total y Masa Gruesa).")

                m_fg_sec_total = m_fg_hum / (1.0 + hum_fina / 100.0)
                m_total_sec = m_cg_sec + m_fg_sec_total
                hum_total = (((m_cg_hum or m_cg_sec) + m_fg_hum - m_total_sec) / m_total_sec) * 100.0

                perd_cg = max(0.0, m_cg_sec - m_cg_lav)
                perd_fg = max(0.0, m_fg_sub_sec - m_fg_sub_lav)

                # Leer valores crudos
                crudos = []
                for s in ASTM_SIEVES:
                    sid = s["id"]
                    if sid == "mmo":
                        v1 = perd_cg
                        v2 = perd_fg
                    else:
                        v1_s = self.filas_tamices_m1[sid].get().strip()
                        v2_s = self.filas_tamices_m2[sid].get().strip()
                        v1 = float(v1_s) if v1_s else 0.0
                        v2 = float(v2_s) if v2_s else 0.0
                    if v1 < 0 or v2 < 0:
                        raise ValueError(f"Las masas en {s['nombre']} no pueden ser negativas.")
                    crudos.append({"s": s, "v1": v1, "v2": v2})

                platillo_m1 = sum(c["v1"] for c in crudos if c["s"]["id"] != "mmo" and (c["s"]["abertura"] <= 2.0 or c["s"]["id"] == "pan"))
                suma_col2 = sum(c["v2"] for c in crudos)

                factor_k = (m_fg_sec_total + platillo_m1 + perd_cg) / (suma_col2 if suma_col2 > 0 else m_fg_sub_sec)

                # Masas retenidas equivalentes y porcentajes
                acum = 0.0
                suma_m1 = 0.0
                suma_m2 = 0.0
                suma_eq = 0.0

                for c in crudos:
                    s = c["s"]
                    v1 = c["v1"]
                    v2 = c["v2"]
                    if s["id"] != "mmo":
                        suma_m1 += v1
                        suma_m2 += v2
                    if s["id"] == "mmo" or (s["abertura"] <= 2.0 and s["abertura"] > 0) or s["id"] == "pan":
                        m_eq = v2 * factor_k
                    else:
                        m_eq = v1 + v2 * factor_k

                    suma_eq += m_eq
                    parcial = (m_eq / m_total_sec) * 100.0 if m_total_sec > 0 else 0.0
                    acum += parcial
                    pasa = max(0.0, 100.0 - acum)

                    items.append({
                        "id": s["id"], "nombre": s["nombre"], "abertura": s["abertura"], "desc": s["desc"],
                        "m1": v1, "m2": v2, "retenido": m_eq, "corregido": m_eq,
                        "porc_parcial": parcial, "porc_acumulado": acum, "porc_pasa": pasa
                    })

                err_cg = abs(m_cg_sec - (suma_m1 + perd_cg)) / m_cg_sec * 100.0 if m_cg_sec > 0 else 0.0
                err_fg = abs(m_fg_sub_sec - (suma_m2 + perd_fg)) / m_fg_sub_sec * 100.0 if m_fg_sub_sec > 0 else 0.0
                porc_error = max(err_cg, err_fg)
                perdida_lavado = perd_cg + perd_fg * factor_k
                masa_lavada = m_total_sec - perdida_lavado

                datos_comp = {
                    "humedad_fina": hum_fina,
                    "humedad_gruesa": hum_gruesa,
                    "humedad_total": hum_total,
                    "masa_seca_gruesa": m_cg_sec,
                    "masa_seca_fina_total": m_fg_sec_total,
                    "masa_seca_submuestra": m_fg_sub_sec,
                    "platillo_m1": platillo_m1,
                    "perdida_gruesa": perd_cg,
                    "perdida_fina": perd_fg,
                    "err_gruesa": err_cg,
                    "err_fina": err_fg,
                    "suma_eq": suma_eq,
                }
            else:
                # Modo simple (1 columna)
                m_tot_s = self.simple_masa_total.get().strip()
                m_lav_s = self.simple_masa_lavada.get().strip()
                if not m_tot_s or float(m_tot_s) <= 0:
                    raise ValueError("Ingrese la Masa Seca Total (> 0).")
                m_total_sec = float(m_tot_s)
                masa_lavada = float(m_lav_s) if m_lav_s and float(m_lav_s) > 0 else m_total_sec
                perdida_lavado = max(0.0, m_total_sec - masa_lavada)
                factor_k = 1.0
                datos_comp = None

                suma = 0.0
                acum = 0.0
                for s in ASTM_SIEVES:
                    sid = s["id"]
                    if sid == "mmo":
                        continue
                    val_s = self.filas_tamices_m1[sid].get().strip()
                    ret = float(val_s) if val_s else 0.0
                    suma += ret
                    parcial = (ret / m_total_sec) * 100.0
                    acum += parcial
                    pasa = max(0.0, 100.0 - acum)

                    items.append({
                        "id": sid, "nombre": s["nombre"], "abertura": s["abertura"], "desc": s["desc"],
                        "m1": ret, "m2": 0.0, "retenido": ret, "corregido": ret,
                        "porc_parcial": parcial, "porc_acumulado": acum, "porc_pasa": pasa
                    })
                porc_error = abs(m_total_sec - suma) / m_total_sec * 100.0

            porc_perdida_lavado = (perdida_lavado / m_total_sec) * 100.0 if m_total_sec > 0 else 0.0

            # Fracciones de suelo (ASTM D2487)
            def get_pasa(tam_id):
                for t in items:
                    if t["id"] == tam_id:
                        return t["porc_pasa"]
                return 0.0

            pasa4 = get_pasa("n4")
            pasa10 = get_pasa("n10")
            pasa40 = get_pasa("n40")
            pasa200 = get_pasa("n200")

            grava = max(0.0, 100.0 - pasa4)
            arena = max(0.0, pasa4 - pasa200)
            finos = max(0.0, pasa200)
            fe = fracciones_enteras(grava, arena, finos)

            # Interpolación logarítmica de diámetros D10, D30, D60, D85
            tams_curva = [it for it in items if it["abertura"] > 0]
            tams_curva.sort(key=lambda x: x["abertura"], reverse=True)

            def find_diameter(pct_target):
                for i in range(len(tams_curva) - 1):
                    p1 = tams_curva[i]
                    p2 = tams_curva[i + 1]
                    y1 = p1["porc_pasa"]
                    y2 = p2["porc_pasa"]
                    if (y1 >= pct_target >= y2) or (y2 >= pct_target >= y1):
                        if y1 == y2:
                            return p1["abertura"]
                        if p1["abertura"] <= 0 or p2["abertura"] <= 0:
                            return None
                        l1 = math.log10(p1["abertura"])
                        l2 = math.log10(p2["abertura"])
                        return 10.0 ** (l1 + ((pct_target - y1) / (y2 - y1)) * (l2 - l1))
                return None

            d10 = find_diameter(10.0) if finos <= 10.0 else None
            d30 = find_diameter(30.0)
            d60 = find_diameter(60.0)
            d85 = find_diameter(85.0)

            cu = (d60 / d10) if (d60 and d10 and d10 > 0) else None
            cc = ((d30 ** 2) / (d60 * d10)) if (d30 and d60 and d10 and d10 > 0 and d60 > 0) else None

            if cu and cc:
                if grava > arena:
                    bien = (cu >= 4.0 and 1.0 <= cc <= 3.0)
                else:
                    bien = (cu >= 6.0 and 1.0 <= cc <= 3.0)
                eval_grad = "Bien graduada (W)" if bien else "Pobremente graduada (P)"
            else:
                eval_grad = "Gradación por evaluar (finos > 10% o faltan diámetros)"

            self.datos_calculados = {
                "metodo": metodo,
                "m_total": m_total_sec,
                "masa_lavada": masa_lavada,
                "perdida_lavado": perdida_lavado,
                "porc_perdida_lavado": porc_perdida_lavado,
                "tamices": items,
                "factor_k": factor_k,
                "porc_error": porc_error,
                "grava": grava,
                "arena": arena,
                "finos": finos,
                "fe": fe,
                "p4": pasa4,
                "p10": pasa10,
                "p40": pasa40,
                "p200": pasa200,
                "d10": d10,
                "d30": d30,
                "d60": d60,
                "d85": d85,
                "cu": cu,
                "cc": cc,
                "eval_grad": eval_grad,
                "comp": datos_comp,
                "encabezado": {
                    "calicata": self.e_calicata.get().strip() or "C-1",
                    "muestra": self.e_muestra.get().strip() or "M-1",
                    "profundidad": self.e_profundidad.get().strip() or "---",
                    "horno": self.e_horno.get().strip() or "---",
                }
            }
            self.calculado = True
            self.controller.geo_state["ensayos"]["granulometria"] = self.datos_calculados
            self.mostrar_resultados()
            if getattr(self.controller, "origen_clasificacion", False):
                if messagebox.askyesno(
                    "Granulometría Calculada",
                    f"Granulometría ASTM D6913 calculada con éxito:\n\n"
                    f"• Grava (> N°4): {fe['grava']} %\n"
                    f"• Arena (N°4 - N°200): {fe['arena']} %\n"
                    f"• Finos (< N°200): {fe['finos']} %\n\n"
                    f"¿Desea regresar ahora a la Clasificación de Suelos (SUCS / AASHTO)?"
                ):
                    self.volver_a_clasificacion()
                    return
            messagebox.showinfo(
                "Cálculo Granulométrico Exitoso",
                f"Granulometría ASTM D6913 calculada:\n\n"
                f"• Grava (> N°4): {fe['grava']} %\n"
                f"• Arena (N°4 - N°200): {fe['arena']} %\n"
                f"• Finos (< N°200): {fe['finos']} %\n\n"
                f"Error de tamizado: {porc_error:.2f} % "
                f"({'Conforme ≤ 1.0%' if porc_error <= 1.0 else 'Alerta > 1.0%'})"
            )

        except Exception as e:
            messagebox.showerror("Error en Granulometría", str(e))

    def mostrar_resultados(self):
        for w in self.contenedor_resultados.winfo_children():
            w.destroy()

        d = self.datos_calculados
        fe = d["fe"]

        # 1. Resumen de fracciones como enteros oficiales ASTM D2487
        c_frac = ctk.CTkFrame(self.contenedor_resultados, fg_color=PRIMARY_LIGHT, corner_radius=8, border_width=1, border_color=PRIMARY_BORDER)
        c_frac.pack(fill="x", pady=(4, 6))
        f_grid = ctk.CTkFrame(c_frac, fg_color="transparent")
        f_grid.pack(fill="x", padx=8, pady=6)
        f_grid.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(f_grid, text="GRAVA (>N°4):", font=ctk.CTkFont(size=9, weight="bold"), text_color=PRIMARY).grid(row=0, column=0)
        ctk.CTkLabel(f_grid, text=f"{fe['grava']} %", font=ctk.CTkFont(size=20, weight="bold"), text_color=PRIMARY).grid(row=1, column=0)

        ctk.CTkLabel(f_grid, text="ARENA (N°4 - N°200):", font=ctk.CTkFont(size=9, weight="bold"), text_color=PRIMARY).grid(row=0, column=1)
        ctk.CTkLabel(f_grid, text=f"{fe['arena']} %", font=ctk.CTkFont(size=20, weight="bold"), text_color=PRIMARY).grid(row=1, column=1)

        ctk.CTkLabel(f_grid, text="FINOS (<N°200):", font=ctk.CTkFont(size=9, weight="bold"), text_color=PRIMARY).grid(row=0, column=2)
        ctk.CTkLabel(f_grid, text=f"{fe['finos']} %", font=ctk.CTkFont(size=20, weight="bold"), text_color=PRIMARY).grid(row=1, column=2)

        # 2. Diámetros y coeficientes
        c_coef = ctk.CTkFrame(self.contenedor_resultados, fg_color=CARD_BG, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        c_coef.pack(fill="x", pady=4)
        d10_txt = f"{d['d10']:.3f} mm" if d['d10'] else ("< 0.075 mm" if d['finos'] > 10 else "---")
        d30_txt = f"{d['d30']:.3f} mm" if d['d30'] else "---"
        d60_txt = f"{d['d60']:.3f} mm" if d['d60'] else "---"
        d85_txt = f"{d['d85']:.3f} mm" if d['d85'] else "---"
        txt_d = f"D10: {d10_txt}  •  D30: {d30_txt}  •  D60: {d60_txt}  •  D85: {d85_txt}"
        txt_c = f"Cu = {d['cu']:.2f}  |  Cc = {d['cc']:.2f}  |  {d['eval_grad']}" if (d['cu'] and d['cc']) else f"{d['eval_grad']}"
        ctk.CTkLabel(c_coef, text=txt_d, font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(pady=(4, 2))
        ctk.CTkLabel(c_coef, text=txt_c, font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_GREEN if "Bien" in d['eval_grad'] else PRIMARY).pack(pady=(0, 4))

        # 3. Control de tamizado y factor K si es compuesto
        c_ctrl = ctk.CTkFrame(self.contenedor_resultados, fg_color=CARD_BG_ALT, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        c_ctrl.pack(fill="x", pady=3)
        err_col = ACCENT_GREEN if d['porc_error'] <= 1.0 else ACCENT_RED
        err_txt = f"Error de tamizado: {d['porc_error']:.2f} %  •  {'Conforme (≤ 1.0 %)' if d['porc_error'] <= 1.0 else 'Alerta: fuera de tolerancia (> 1.0 %)'}"
        ctk.CTkLabel(c_ctrl, text=err_txt, font=ctk.CTkFont(size=10, weight="bold"), text_color=err_col).pack(pady=(3, 1))

        if d.get("comp"):
            comp = d["comp"]
            comp_txt = f"Factor K: {d['factor_k']:.4f}  •  w Fina: {comp['humedad_fina']:.1f}%  •  w Gruesa: {comp['humedad_gruesa']:.1f}%  •  Masa Seca Tot: {d['m_total']:.1f} g"
            ctk.CTkLabel(c_ctrl, text=comp_txt, font=ctk.CTkFont(size=9), text_color=NEUTRAL_MUTED).pack(pady=(0, 3))

        # 4. Gráfico Matplotlib interactivo
        fig = self.generar_figura()
        canvas = FigureCanvasTkAgg(fig, master=self.contenedor_resultados)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, pady=6)

    def generar_figura(self):
        d = self.datos_calculados
        pts = [(it["abertura"], it["porc_pasa"]) for it in d["tamices"] if it["abertura"] > 0]
        pts.sort(key=lambda x: x[0], reverse=True)

        fig, ax = plt.subplots(figsize=(5.6, 3.4), dpi=100)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]

        ax.plot(xs, ys, color=PRIMARY, marker="o", markersize=4, linewidth=1.8, label="Curva Granulométrica")
        ax.set_xscale("log")
        ax.set_xlim(100.0, 0.01) # escala geotécnica invertida estándar
        ax.set_ylim(0, 100)
        ax.set_xlabel("Abertura del Tamiz (mm) [Escala Logarítmica]", fontsize=8, fontweight="bold", color=NEUTRAL_HEADING)
        ax.ylabel = ax.set_ylabel("% Que Pasa Acumulado", fontsize=8, fontweight="bold", color=NEUTRAL_HEADING)

        met_tit = "Tamizado Compuesto (ASTM D6913)" if d.get("metodo") == "a-compuesto" else "Tamizado Simple (ASTM D6913)"
        ax.set_title(f"CURVA GRANULOMÉTRICA — {met_tit}", fontsize=9, fontweight="bold", color=PRIMARY)
        ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)

        # Límites geotécnicos N°4 (4.75mm) y N°200 (0.075mm)
        ax.axvline(x=4.75, color=ACCENT_RED, linestyle=":", linewidth=1)
        ax.text(4.75, 92, " N°4 (4.75mm)", fontsize=7, color=ACCENT_RED, fontweight="bold")
        ax.axvline(x=0.075, color="#7C3AED", linestyle=":", linewidth=1)
        ax.text(0.075, 12, " N°200 (0.075mm)", fontsize=7, color="#7C3AED", fontweight="bold")

        ax.legend(fontsize=7, loc="upper right")
        fig.tight_layout()
        return fig

    def cargar_demo_compuesto(self):
        self.seg_metodo.set("Compuesto (2 col - TM > 3/4\")")
        self.cambiar_metodo("Compuesto (2 col - TM > 3/4\")")

        self.e_calicata.delete(0, "end"); self.e_calicata.insert(0, "C-1")
        self.e_muestra.delete(0, "end"); self.e_muestra.insert(0, "M-1")
        self.e_profundidad.delete(0, "end"); self.e_profundidad.insert(0, "15.60")
        self.e_horno.delete(0, "end"); self.e_horno.insert(0, "HR-3 / BL-18 y BL-8")
        self.e_masa_total.delete(0, "end"); self.e_masa_total.insert(0, "25939.0")
        self.e_recipiente.delete(0, "end"); self.e_recipiente.insert(0, "1490 (BNS-44) / 123.3 (R-12)")
        self.e_masa_gruesa.delete(0, "end"); self.e_masa_gruesa.insert(0, "19703.0")
        self.e_masa_fina.delete(0, "end"); self.e_masa_fina.insert(0, "6236.0")

        self.sec_g1.delete(0, "end"); self.sec_g1.insert(0, "19703.0")
        self.sec_g2.delete(0, "end"); self.sec_g2.insert(0, "19541.0")
        self.sec_g3.delete(0, "end"); self.sec_g3.insert(0, "19491.0")
        self.sec_f1.delete(0, "end"); self.sec_f1.insert(0, "639.5")
        self.sec_f2.delete(0, "end"); self.sec_f2.insert(0, "623.3")
        self.sec_f3.delete(0, "end"); self.sec_f3.insert(0, "581.3")

        m1 = {'2in': '3536.0', '1_5in': '4670.0', '1in': '4734.0', '3_4in': '1855.0', '1_2in': '2109.0', '3_8in': '1061.0', '1_4in': '1046.0', 'n4': '459.0', 'n10': '21.0'}
        m2 = {'n10': '88.1', 'n20': '37.2', 'n30': '39.1', 'n40': '87.3', 'n60': '168.9', 'n100': '107.4', 'n140': '37.2', 'n200': '15.8', 'pan': '0.3'}

        for s in ASTM_SIEVES:
            sid = s["id"]
            self.filas_tamices_m1[sid].delete(0, "end")
            if sid in m1:
                self.filas_tamices_m1[sid].insert(0, m1[sid])
            self.filas_tamices_m2[sid].delete(0, "end")
            if sid in m2:
                self.filas_tamices_m2[sid].insert(0, m2[sid])

        self.calcular()

    def cargar_demo_simple(self):
        self.seg_metodo.set("Simple (1 col - TM < 3/4\")")
        self.cambiar_metodo("Simple (1 col - TM < 3/4\")")

        self.simple_masa_total.delete(0, "end"); self.simple_masa_total.insert(0, "2708.00")
        self.simple_masa_lavada.delete(0, "end"); self.simple_masa_lavada.insert(0, "2708.00")

        demos = {
            '3in': '0.00', '2in': '233.10', '1_5in': '346.80', '1in': '517.50', '3_4in': '289.30',
            '1_2in': '46.50', '3_8in': '22.20', '1_4in': '195.00', 'n4': '121.50', 'n10': '342.10',
            'n20': '171.60', 'n30': '32.60', 'n40': '42.50', 'n60': '61.10', 'n100': '78.30',
            'n140': '0.00', 'n200': '199.60', 'pan': '6.60'
        }
        for s in ASTM_SIEVES:
            sid = s["id"]
            self.filas_tamices_m1[sid].delete(0, "end")
            if sid in demos:
                self.filas_tamices_m1[sid].insert(0, demos[sid])
            self.filas_tamices_m2[sid].delete(0, "end")

        self.calcular()

    def cargar_demo(self):
        self.cargar_demo_compuesto()

    def limpiar(self):
        super().limpiar()
        for e in self.filas_tamices_m1.values():
            e.delete(0, "end")
        for e in self.filas_tamices_m2.values():
            e.delete(0, "end")
        self.sec_g1.delete(0, "end")
        self.sec_g2.delete(0, "end")
        self.sec_g3.delete(0, "end")
        self.sec_f1.delete(0, "end")
        self.sec_f2.delete(0, "end")
        self.sec_f3.delete(0, "end")
        self.simple_masa_total.delete(0, "end")
        self.simple_masa_lavada.delete(0, "end")

    def exportar_pdf(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar Informe de Análisis Granulométrico (UNI / ASTM D6913)",
            defaultextension=".pdf",
            initialfile=f"Informe_Granulometria_{self.datos_calculados.get('encabezado', {}).get('muestra', 'M-01')}.pdf",
            filetypes=[("Archivo PDF", "*.pdf")]
        )
        if not ruta:
            return
        try:
            doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            est = obtener_estilos_pdf()
            d = self.datos_calculados
            fe = d["fe"]
            enc = d.get("encabezado", {})
            metodo_txt = "Método A — Tamizado Compuesto (T.M. > 3/4\")" if d.get("metodo") == "a-compuesto" else "Tamizado Simple (T.M. < 3/4\")"

            elems = crear_cabecera_pdf(est, self.titulo, self.codigo_norma)

            meta_dict = dict(self.controller.datos_proyecto)
            meta_dict["muestra"] = enc.get("muestra", meta_dict.get("muestra", "M-01"))
            meta_dict["profundidad"] = enc.get("profundidad", "---")
            elems.append(crear_tabla_metadatos(meta_dict))
            elems.append(Spacer(1, 6))

            elems.append(Paragraph("DATOS DEL ENSAYO Y RESULTADOS GRANULOMÉTRICOS", est["seccion"]))
            comp = d.get("comp")
            hum_txt = f"Fina: {comp['humedad_fina']:.1f}% | Gruesa: {comp['humedad_gruesa']:.1f}%" if comp else "---"
            k_txt = f"{d['factor_k']:.4f}" if d.get("factor_k") else "1.0000"

            t_res_data = [
                ["Método de Ensayo", metodo_txt, "Factor K (Homogenización)", k_txt],
                ["Masa Seca Total (g)", f"{d['m_total']:.1f} g", "Pérdida por Lavado", f"{d['perdida_lavado']:.1f} g ({d['porc_perdida_lavado']:.2f}%)"],
                ["Fracción Grava (> N°4)", f"{fe['grava']} %", "D10 / D30 / D60 (mm)", f"{d['d10']:.3f} / {d['d30']:.3f} / {d['d60']:.3f}" if (d['d10'] and d['d30'] and d['d60']) else "---"],
                ["Fracción Arena (N°4 - N°200)", f"{fe['arena']} %", "Cu / Cc", f"{d['cu']:.2f} / {d['cc']:.2f}" if (d['cu'] and d['cc']) else "---"],
                ["Fracción Finos (< N°200)", f"{fe['finos']} %", "Dictamen de Gradación", d['eval_grad']],
                ["Error de Tamizado", f"{d['porc_error']:.2f} %", "Tolerancia ASTM (≤ 1.0%)", "Conforme" if d['porc_error'] <= 1.0 else "No conforme"],
            ]
            t_res = Table(t_res_data, colWidths=[130, 140, 130, 95])
            t_res.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(CARD_BG)),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("ALIGN", (3, 0), (3, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]))
            elems.append(t_res)
            elems.append(Spacer(1, 6))

            elems.append(Paragraph("DISTRIBUCIÓN GRANULOMÉTRICA POR TAMIZADO (ASTM D6913)", est["seccion"]))
            t_tam_data = [["Tamiz ASTM", "Abertura (mm)", "Masa Ret. (g)", "% Parcial Ret.", "% Acum. Ret.", "% Que Pasa"]]
            for it in d["tamices"]:
                if it["id"] == "mmo":
                    continue
                ab_s = f"{it['abertura']:.3f}" if it["abertura"] > 0 else "---"
                t_tam_data.append([
                    it["nombre"], ab_s, f"{it['retenido']:.2f}",
                    f"{it['porc_parcial']:.2f} %", f"{it['porc_acumulado']:.2f} %", f"{it['porc_pasa']:.2f} %"
                ])
            mmo_it = next((x for x in d["tamices"] if x["id"] == "mmo"), None)
            if mmo_it and mmo_it["retenido"] > 0:
                t_tam_data.append([
                    "M - Mo (Lavado)", "---", f"{mmo_it['retenido']:.2f}",
                    f"{mmo_it['porc_parcial']:.2f} %", f"{mmo_it['porc_acumulado']:.2f} %", f"{mmo_it['porc_pasa']:.2f} %"
                ])

            t_tam = Table(t_tam_data, colWidths=[95, 75, 80, 80, 80, 85])
            t_tam.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            elems.append(t_tam)
            elems.append(Spacer(1, 6))

            fig = self.generar_figura()
            img = figura_a_imagen_reportlab(fig, width=440, height=200)
            elems.append(img)
            elems.append(Spacer(1, 8))
            elems.append(crear_bloque_firmas(est))

            doc.build(elems)
            if messagebox.askyesno("PDF Generado", f"Informe guardado con éxito:\n{ruta}\n\n¿Desea abrirlo ahora?"):
                os.startfile(ruta)
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))

# -------------------------------------------------------------------
# ENSAYO 05: LÍMITES DE ATTERBERG (ASTM D4318 / NTP 339.129)
# -------------------------------------------------------------------
class LimitesAtterberg(BaseEnsayo):
    titulo = "05. LÍMITES DE ATTERBERG (LL, LP, IP)"
    subtitulo = "Límite líquido por copa de Casagrande y límite plástico según ASTM D4318"
    codigo_norma = "ASTM D4318 • NTP 339.129 • MTC E 110 / 111"
    clave_ensayo = "atterberg"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        scroll_in = ctk.CTkScrollableFrame(self.panel_izquierdo, fg_color="transparent")
        scroll_in.pack(fill="both", expand=True)

        # Suelo No Plástico (NP)
        self.var_np = tk.BooleanVar(value=False)
        f_np = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        f_np.pack(fill="x", pady=(0, 6))
        self.chk_np = ctk.CTkCheckBox(
            f_np,
            text="Material No Plástico (NP) — Sin plasticidad / Suelos arenosos limpios",
            variable=self.var_np,
            command=self.toggle_np,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=ACCENT_RED
        )
        self.chk_np.pack(padx=12, pady=8, anchor="w")

        # Tarjeta Condiciones / Tipo de Muestra
        f_tm = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        f_tm.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(f_tm, text="Tipo de Muestra:", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(side="left", padx=10, pady=6)
        self.txt_tipo_muestra = ctk.CTkEntry(f_tm, height=26, fg_color="#FFFFFF", border_color=BORDER_COLOR)
        self.txt_tipo_muestra.insert(0, "Pasante malla N°40 (ASTM D4318)")
        self.txt_tipo_muestra.pack(side="left", fill="x", expand=True, padx=8, pady=6)

        # Tarjeta Límite Líquido
        self.card_ll = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_ll.pack(fill="x", pady=4)
        hdr_ll = ctk.CTkFrame(self.card_ll, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
        hdr_ll.pack(fill="x", padx=4, pady=4)
        hdr_ll.pack_propagate(False)
        ctk.CTkLabel(hdr_ll, text="🥣  Límite Líquido (LL) — Copa de Casagrande", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=10, pady=4)

        self.filas_ll = []
        f_tll = ctk.CTkFrame(self.card_ll, fg_color="transparent")
        f_tll.pack(fill="x", padx=6, pady=4)
        headers_ll = ["N°", "Recipiente", "Intervalo", "N° Golpes", "Cáp.+Húmedo [g]", "Cáp.+Seco [g]", "Recipiente (Mc) [g]"]
        cols_wll = [25, 65, 65, 65, 105, 105, 95]
        hf_ll = ctk.CTkFrame(f_tll, fg_color=CARD_BG_ALT, height=26)
        hf_ll.pack(fill="x", pady=2)
        for h, w in zip(headers_ll, cols_wll):
            ctk.CTkLabel(hf_ll, text=h, font=ctk.CTkFont(size=9, weight="bold"), text_color=NEUTRAL_HEADING, width=w).pack(side="left", padx=2)

        intervalos_def = ["25–35", "20–30", "15–25", "10–20"]
        for i in range(1, 5):
            rf = ctk.CTkFrame(f_tll, fg_color="transparent")
            rf.pack(fill="x", pady=1)
            ctk.CTkLabel(rf, text=str(i), font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY, width=25).pack(side="left", padx=2)
            e_id = ctk.CTkEntry(rf, height=24, width=65, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_id.insert(0, f"R-{i}")
            e_id.pack(side="left", padx=2)
            e_inter = ctk.CTkEntry(rf, height=24, width=65, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_inter.insert(0, intervalos_def[i - 1])
            e_inter.pack(side="left", padx=2)
            e_g = ctk.CTkEntry(rf, height=24, width=65, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_g.pack(side="left", padx=2)
            e_mh = ctk.CTkEntry(rf, height=24, width=105, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_mh.pack(side="left", padx=2)
            e_ms = ctk.CTkEntry(rf, height=24, width=105, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_ms.pack(side="left", padx=2)
            e_cap = ctk.CTkEntry(rf, height=24, width=95, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_cap.insert(0, "14.00")
            e_cap.pack(side="left", padx=2)
            self.filas_ll.append({"num": i, "id": e_id, "intervalo": e_inter, "golpes": e_g, "mh": e_mh, "ms": e_ms, "cap": e_cap})

        # Tarjeta Límite Plástico
        self.card_lp = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_lp.pack(fill="x", pady=4)
        hdr_lp = ctk.CTkFrame(self.card_lp, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
        hdr_lp.pack(fill="x", padx=4, pady=4)
        hdr_lp.pack_propagate(False)
        ctk.CTkLabel(hdr_lp, text="🥢  Límite Plástico (LP) — Cilindros de 3 mm", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=10, pady=4)

        self.filas_lp = []
        f_tlp = ctk.CTkFrame(self.card_lp, fg_color="transparent")
        f_tlp.pack(fill="x", padx=6, pady=4)
        headers_lp = ["N°", "Recipiente", "Cáp.+Húmedo [g]", "Cáp.+Seco [g]", "Recipiente (Mc) [g]"]
        cols_wlp = [25, 80, 130, 130, 110]
        hf_lp = ctk.CTkFrame(f_tlp, fg_color=CARD_BG_ALT, height=26)
        hf_lp.pack(fill="x", pady=2)
        for h, w in zip(headers_lp, cols_wlp):
            ctk.CTkLabel(hf_lp, text=h, font=ctk.CTkFont(size=9, weight="bold"), text_color=NEUTRAL_HEADING, width=w).pack(side="left", padx=2)

        for i in range(1, 3):
            rf = ctk.CTkFrame(f_tlp, fg_color="transparent")
            rf.pack(fill="x", pady=1)
            ctk.CTkLabel(rf, text=str(i), font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY, width=25).pack(side="left", padx=2)
            e_id = ctk.CTkEntry(rf, height=24, width=80, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_id.insert(0, f"P-{i}")
            e_id.pack(side="left", padx=2)
            e_mh = ctk.CTkEntry(rf, height=24, width=130, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_mh.pack(side="left", padx=2)
            e_ms = ctk.CTkEntry(rf, height=24, width=130, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_ms.pack(side="left", padx=2)
            e_cap = ctk.CTkEntry(rf, height=24, width=110, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_cap.insert(0, "14.00")
            e_cap.pack(side="left", padx=2)
            self.filas_lp.append({"num": i, "id": e_id, "mh": e_mh, "ms": e_ms, "cap": e_cap})

        # Botonera
        b_bar = ctk.CTkFrame(self.panel_izquierdo, fg_color="transparent")
        b_bar.pack(fill="x", pady=8)
        crear_boton(b_bar, "Calcular", self.calcular, color=PRIMARY, hover=PRIMARY_HOVER, icon="⚡").pack(side="left", padx=3, fill="x", expand=True)
        crear_boton(b_bar, "Ejemplo (Demo)", self.cargar_demo, color=PRIMARY_LIGHT, hover=PRIMARY_BORDER, icon="🧪").pack(side="left", padx=3, fill="x", expand=True)
        b_bar.winfo_children()[-1].configure(text_color=PRIMARY)
        crear_boton(b_bar, "Limpiar", self.limpiar, color=NEUTRAL_MUTED, hover=NEUTRAL_BODY, icon="🗑").pack(side="left", padx=3, fill="x", expand=True)

    def toggle_np(self):
        es_np = self.var_np.get()
        if es_np:
            self.card_ll.pack_forget()
            self.card_lp.pack_forget()
        else:
            self.card_ll.pack(fill="x", pady=4)
            self.card_lp.pack(fill="x", pady=4)

    def calcular(self):
        try:
            if self.var_np.get():
                self.datos_calculados = {
                    "np": True, "ll": None, "lp": None, "ip": None,
                    "m": None, "b": None, "r2": None, "ll_pts": [], "lp_pts": []
                }
                self.calculado = True
                self.controller.geo_state["ensayos"]["atterberg"] = self.datos_calculados
                self.mostrar_resultados()
                if getattr(self.controller, "origen_clasificacion", False):
                    if messagebox.askyesno(
                        "Atterberg Registrado",
                        "Suelo registrado como No Plástico (NP).\n\n¿Desea regresar ahora a la Clasificación de Suelos (SUCS / AASHTO)?"
                    ):
                        self.volver_a_clasificacion()
                        return
                messagebox.showinfo("Atterberg", "Suelo registrado como No Plástico (NP).")
                return

            # Procesar Límite Líquido
            ll_pts = []
            for r in self.filas_ll:
                g_s, mh_s, ms_s, cap_s = r["golpes"].get().strip(), r["mh"].get().strip(), r["ms"].get().strip(), r["cap"].get().strip()
                if not g_s and not mh_s and not ms_s:
                    continue
                if not g_s or not mh_s or not ms_s or not cap_s:
                    raise ValueError(f"En fila {r['num']} de LL, complete todos los campos.")
                g, mh, ms, cap = float(g_s), float(mh_s), float(ms_s), float(cap_s)
                if g <= 0 or ms <= cap or mh < ms:
                    raise ValueError(f"Datos inválidos en fila {r['num']} del Límite Líquido.")
                m_seco = ms - cap
                w = ((mh - ms) / m_seco) * 100.0
                id_val = r["id"].get().strip() or f"R-{r['num']}"
                inter_val = r["intervalo"].get().strip()
                ll_pts.append({"num": r["num"], "id": id_val, "intervalo": inter_val, "golpes": g, "w": w, "log_g": math.log10(g)})

            if len(ll_pts) < 2:
                raise ValueError("Se requieren al menos 2 determinaciones de Límite Líquido.")

            # Regresión semilogarítmica: w = m * log10(golpes) + b
            m, b, r2 = regresion_lineal([p["log_g"] for p in ll_pts], [p["w"] for p in ll_pts])
            ll = m * math.log10(25.0) + b

            # Procesar Límite Plástico
            lp_pts = []
            for r in self.filas_lp:
                mh_s, ms_s, cap_s = r["mh"].get().strip(), r["ms"].get().strip(), r["cap"].get().strip()
                if not mh_s and not ms_s:
                    continue
                if not mh_s or not ms_s or not cap_s:
                    raise ValueError(f"En fila {r['num']} de LP, complete todos los campos.")
                mh, ms, cap = float(mh_s), float(ms_s), float(cap_s)
                if ms <= cap or mh < ms:
                    raise ValueError(f"Datos inválidos en fila {r['num']} del Límite Plástico.")
                w = ((mh - ms) / (ms - cap)) * 100.0
                id_val = r["id"].get().strip() or f"P-{r['num']}"
                lp_pts.append({"num": r["num"], "id": id_val, "w": w})

            lp = sum(p["w"] for p in lp_pts) / len(lp_pts) if lp_pts else None
            ip = (ll - lp) if (ll is not None and lp is not None) else None
            ip_ent = ip_entero(ll, lp, ip)
            clase = clasificar_plasticidad(ll, ip) if (ll is not None and ip is not None and ip > 0) else None

            self.datos_calculados = {
                "np": False, "ll": ll, "lp": lp, "ip": ip,
                "ll_entero": int(round(ll)) if ll is not None else None,
                "lp_entero": int(round(lp)) if lp is not None else None,
                "ip_entero": ip_ent,
                "clase": clase,
                "m": m, "b": b, "r2": r2, "ll_pts": ll_pts, "lp_pts": lp_pts,
                "tipo_muestra": self.txt_tipo_muestra.get().strip()
            }
            self.calculado = True
            self.controller.geo_state["ensayos"]["atterberg"] = self.datos_calculados
            self.mostrar_resultados()
            if getattr(self.controller, "origen_clasificacion", False):
                clase_info = f"\n• Plasticidad (Casagrande): {clase['grupo']} — {clase['nombre']} ({clase['nivel']})" if clase else ""
                if messagebox.askyesno(
                    "Límites Calculados",
                    f"Límites de Atterberg calculados con éxito:\n\n"
                    f"• Límite Líquido (LL): {round(ll)} %\n"
                    f"• Límite Plástico (LP): {round(lp)} %\n"
                    f"• Índice de Plasticidad (IP): {ip_ent} %{clase_info}\n\n"
                    f"¿Desea regresar ahora a la Clasificación de Suelos (SUCS / AASHTO)?"
                ):
                    self.volver_a_clasificacion()
                    return
            clase_info = f"\n• Plasticidad (Casagrande): {clase['grupo']} — {clase['nombre']} ({clase['nivel']})" if clase else ""
            messagebox.showinfo(
                "Cálculo de Atterberg",
                f"Límites según ASTM D4318 / NTP 339.129:\n\n"
                f"• Límite Líquido (LL): {round(ll)} % ({ll:.2f}%)\n"
                f"• Límite Plástico (LP): {round(lp)} % ({lp:.2f}%)\n"
                f"• Índice de Plasticidad (IP): {ip_ent} % ({ip:.2f}%){clase_info}"
            )

        except Exception as e:
            messagebox.showerror("Error en Atterberg", str(e))

    def mostrar_resultados(self):
        for w in self.contenedor_resultados.winfo_children():
            w.destroy()

        d = self.datos_calculados
        if d.get("np"):
            res_card = ctk.CTkFrame(self.contenedor_resultados, fg_color=PRIMARY_LIGHT, corner_radius=8, border_width=1, border_color=PRIMARY_BORDER)
            res_card.pack(fill="x", pady=(4, 10))
            ctk.CTkLabel(res_card, text="MATERIAL NO PLÁSTICO (NP)", font=ctk.CTkFont(size=18, weight="bold"), text_color=ACCENT_RED).pack(pady=16)
            return

        res_card = ctk.CTkFrame(self.contenedor_resultados, fg_color=PRIMARY_LIGHT, corner_radius=8, border_width=1, border_color=PRIMARY_BORDER)
        res_card.pack(fill="x", pady=(4, 6))
        f_grid = ctk.CTkFrame(res_card, fg_color="transparent")
        f_grid.pack(fill="x", padx=8, pady=6)
        f_grid.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(f_grid, text="LÍMITE LÍQUIDO (LL):", font=ctk.CTkFont(size=9, weight="bold"), text_color=PRIMARY).grid(row=0, column=0)
        ctk.CTkLabel(f_grid, text=f"{d['ll_entero']} %", font=ctk.CTkFont(size=18, weight="bold"), text_color=PRIMARY).grid(row=1, column=0)
        ctk.CTkLabel(f_grid, text=f"({d['ll']:.2f}%)", font=ctk.CTkFont(size=9), text_color=NEUTRAL_MUTED).grid(row=2, column=0)

        ctk.CTkLabel(f_grid, text="LÍMITE PLÁSTICO (LP):", font=ctk.CTkFont(size=9, weight="bold"), text_color=PRIMARY).grid(row=0, column=1)
        ctk.CTkLabel(f_grid, text=f"{d['lp_entero']} %", font=ctk.CTkFont(size=18, weight="bold"), text_color=PRIMARY).grid(row=1, column=1)
        ctk.CTkLabel(f_grid, text=f"({d['lp']:.2f}%)", font=ctk.CTkFont(size=9), text_color=NEUTRAL_MUTED).grid(row=2, column=1)

        ctk.CTkLabel(f_grid, text="ÍNDICE PLÁSTICO (IP):", font=ctk.CTkFont(size=9, weight="bold"), text_color=PRIMARY).grid(row=0, column=2)
        ctk.CTkLabel(f_grid, text=f"{d['ip_entero']} %", font=ctk.CTkFont(size=18, weight="bold"), text_color=ACCENT_GREEN).grid(row=1, column=2)
        ctk.CTkLabel(f_grid, text=f"({d['ip']:.2f}%)", font=ctk.CTkFont(size=9), text_color=NEUTRAL_MUTED).grid(row=2, column=2)

        # Tarjeta Casagrande
        if d.get("clase"):
            cl = d["clase"]
            c_casa = ctk.CTkFrame(self.contenedor_resultados, fg_color=CARD_BG, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
            c_casa.pack(fill="x", pady=4)
            ctk.CTkLabel(c_casa, text=f"Carta de Casagrande: {cl['grupo']} — {cl['nombre']}", font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY).pack(pady=(4, 1))
            ctk.CTkLabel(c_casa, text=f"Nivel: {cl['nivel']}  •  Línea A: IP = 0.73·(LL−20) = {cl['linea_a']:.2f} %", font=ctk.CTkFont(size=9), text_color=NEUTRAL_MUTED).pack(pady=(0, 4))

        # Gráfico Curva de Fluidez Matplotlib
        fig = self.generar_figura()
        canvas = FigureCanvasTkAgg(fig, master=self.contenedor_resultados)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, pady=6)

    def generar_figura(self):
        d = self.datos_calculados
        fig, ax = plt.subplots(figsize=(5.5, 3.2), dpi=100)
        if not d.get("np") and d.get("ll_pts"):
            pts = d["ll_pts"]
            xs = [p["golpes"] for p in pts]
            ys = [p["w"] for p in pts]
            ax.scatter(xs, ys, color=PRIMARY, s=35, zorder=3, label="Puntos Ensayados")

            m, b = d["m"], d["b"]
            line_xs = [10, 20, 25, 30, 45]
            line_ys = [m * math.log10(x) + b for x in line_xs]
            ax.plot(line_xs, line_ys, color=ACCENT_RED, linestyle="-", linewidth=1.5, label=f"Ajuste (R²={d['r2']:.4f})")

            ll = d["ll"]
            ax.scatter([25], [ll], color="#F59E0B", edgecolors="#111827", s=70, zorder=4, label=f"LL (25 golpes) = {ll:.1f}%")
            ax.axvline(x=25, color="#6B7280", linestyle=":", linewidth=1)
            ax.axhline(y=ll, color="#6B7280", linestyle=":", linewidth=1)

        ax.set_xscale("log")
        ax.set_xlim(10, 50)
        ax.set_xlabel("Número de Golpes (Escala Log)", fontsize=8, fontweight="bold", color=NEUTRAL_HEADING)
        ax.set_ylabel("Contenido de Humedad (%)", fontsize=8, fontweight="bold", color=NEUTRAL_HEADING)
        ax.set_title("CURVA DE FLUIDEZ (LÍMITE LÍQUIDO)", fontsize=9, fontweight="bold", color=PRIMARY)
        ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)
        ax.legend(fontsize=7, loc="upper right")
        fig.tight_layout()
        return fig

    def cargar_demo(self):
        self.var_np.set(False)
        self.toggle_np()
        self.txt_tipo_muestra.delete(0, "end")
        self.txt_tipo_muestra.insert(0, "Pasante malla N°40 (ASTM D4318)")
        demos_ll = [
            ["R-01", "25–35", 33, 38.95, 32.10],
            ["R-02", "20–30", 27, 40.55, 33.05],
            ["R-03", "15–25", 21, 37.60, 30.75],
            ["R-04", "10–20", 15, 39.10, 31.60]
        ]
        for i, (cid, inter, g, mh, ms) in enumerate(demos_ll):
            self.filas_ll[i]["id"].delete(0, "end"); self.filas_ll[i]["id"].insert(0, cid)
            self.filas_ll[i]["intervalo"].delete(0, "end"); self.filas_ll[i]["intervalo"].insert(0, inter)
            self.filas_ll[i]["golpes"].delete(0, "end"); self.filas_ll[i]["golpes"].insert(0, str(g))
            self.filas_ll[i]["mh"].delete(0, "end"); self.filas_ll[i]["mh"].insert(0, f"{mh:.2f}")
            self.filas_ll[i]["ms"].delete(0, "end"); self.filas_ll[i]["ms"].insert(0, f"{ms:.2f}")
            self.filas_ll[i]["cap"].delete(0, "end"); self.filas_ll[i]["cap"].insert(0, "14.00")

        demos_lp = [
            ["P-01", 24.30, 22.35, 14.10],
            ["P-02", 25.15, 23.05, 14.00]
        ]
        for i, (cid, mh, ms, cap) in enumerate(demos_lp):
            self.filas_lp[i]["id"].delete(0, "end"); self.filas_lp[i]["id"].insert(0, cid)
            self.filas_lp[i]["mh"].delete(0, "end"); self.filas_lp[i]["mh"].insert(0, f"{mh:.2f}")
            self.filas_lp[i]["ms"].delete(0, "end"); self.filas_lp[i]["ms"].insert(0, f"{ms:.2f}")
            self.filas_lp[i]["cap"].delete(0, "end"); self.filas_lp[i]["cap"].insert(0, f"{cap:.2f}")

        self.calcular()

    def exportar_pdf(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar Informe Técnico de Límites de Atterberg",
            defaultextension=".pdf",
            initialfile=f"Informe_Atterberg_{self.controller.datos_proyecto.get('muestra', 'M-01')}.pdf",
            filetypes=[("Archivo PDF", "*.pdf")]
        )
        if not ruta:
            return
        try:
            doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            est = obtener_estilos_pdf()
            elems = crear_cabecera_pdf(est, self.titulo, self.codigo_norma)
            elems.append(crear_tabla_metadatos(self.controller.datos_proyecto))
            elems.append(Spacer(1, 10))

            elems.append(Paragraph("SÍNTESIS DE LÍMITES DE CONSISTENCIA", est["seccion"]))
            d = self.datos_calculados
            if d.get("np"):
                elems.append(Paragraph("<b>Material clasificado como No Plástico (NP).</b>", est["celda_bold"]))
            else:
                t_data = [
                    ["Parámetro", "Símbolo", "Valor Obtenido", "Unidad"],
                    ["Límite Líquido (a 25 golpes)", "LL", f"{d['ll']:.1f}", "%"],
                    ["Límite Plástico", "LP", f"{d['lp']:.1f}", "%"],
                    ["Índice de Plasticidad", "IP", f"{d['ip']:.1f}", "%"],
                    ["Coeficiente de Regresión", "R²", f"{d['r2']:.4f}", "---"]
                ]
                t = Table(t_data, colWidths=[180, 80, 120, 100])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                elems.append(t)
                elems.append(Spacer(1, 10))

                fig = self.generar_figura()
                img = figura_a_imagen_reportlab(fig, width=440, height=210)
                elems.append(img)

            elems.append(Spacer(1, 12))
            elems.append(crear_bloque_firmas(est))

            doc.build(elems)
            if messagebox.askyesno("PDF Generado", f"Informe guardado con éxito:\n{ruta}\n\n¿Desea abrirlo ahora?"):
                os.startfile(ruta)
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))

# -------------------------------------------------------------------
# ENSAYO 06: CLASIFICACIÓN SUCS Y AASHTO (ASTM D2487 / AASHTO M 145)
# -------------------------------------------------------------------
class ClasificacionSuelos(BaseEnsayo):
    titulo = "06. CLASIFICACIÓN SUCS Y AASHTO"
    subtitulo = "ASTM D2487 (SUCS) • AASHTO M 145 • NTP 339.134"
    codigo_norma = "ASTM D2487 • AASHTO M 145"
    clave_ensayo = "clasificacion"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.modo_manual = False

        scroll_in = ctk.CTkScrollableFrame(self.panel_izquierdo, fg_color="transparent")
        scroll_in.pack(fill="both", expand=True)

        # Banner informativo de requerimientos
        card_info = ctk.CTkFrame(scroll_in, fg_color=PRIMARY_LIGHT, corner_radius=8, border_width=1, border_color=PRIMARY_BORDER)
        card_info.pack(fill="x", pady=(0, 6), padx=2)

        ctk.CTkLabel(
            card_info,
            text="🏷️ Requisitos para la Clasificación (SUCS ASTM D2487 y AASHTO M 145):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=PRIMARY
        ).pack(anchor="w", padx=10, pady=(6, 2))

        ctk.CTkLabel(
            card_info,
            text="Para clasificar el suelo se requieren 2 componentes: Granulometría y Límites de Atterberg. Puede abrir el ensayo respectivo para ingresar los tamices o copas de Casagrande, o escribir los valores directamente en las tarjetas inferiores:",
            font=ctk.CTkFont(size=9),
            text_color=NEUTRAL_MUTED,
            wraplength=480,
            justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # ------------------------------------------------------------------
        # 1. OPCIÓN 1: AGREGAR GRANULOMETRÍA
        # ------------------------------------------------------------------
        self.card_gr = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_gr.pack(fill="x", pady=4, padx=2)

        hdr_gr = ctk.CTkFrame(self.card_gr, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
        hdr_gr.pack(fill="x", padx=4, pady=4)
        hdr_gr.pack_propagate(False)

        ctk.CTkLabel(
            hdr_gr,
            text="🔬  Opción 1: Agregar Granulometría (ASTM D6913)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=PRIMARY
        ).pack(side="left", padx=8, pady=3)

        self.lbl_estado_gr = ctk.CTkLabel(
            hdr_gr,
            text="⏳ Pendiente",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=ACCENT_RED
        )
        self.lbl_estado_gr.pack(side="right", padx=8)

        # Botón destacado para abrir el ensayo completo de granulometría
        f_btn_gr = ctk.CTkFrame(self.card_gr, fg_color="transparent")
        f_btn_gr.pack(fill="x", padx=8, pady=(4, 2))

        crear_boton(
            f_btn_gr,
            "📋 Abrir Ensayo de Granulometría (Poner tamices y todo)",
            self.abrir_ensayo_granulometria,
            color=PRIMARY,
            hover=PRIMARY_HOVER,
            icon="🔬",
            height=30
        ).pack(side="left", fill="x", expand=True)

        crear_boton(
            f_btn_gr,
            "Traer datos",
            self.sincronizar_granulometria,
            color=CARD_BG_ALT,
            hover=BORDER_COLOR,
            width=100,
            height=30,
            icon="🔗"
        ).pack(side="right", padx=(6, 0))

        ctk.CTkLabel(
            self.card_gr,
            text="Llene la serie de tamices (3\" a Fondo) para calcular la curva y pasantes, o escriba abajo los %:",
            font=ctk.CTkFont(size=9),
            text_color=NEUTRAL_MUTED,
            wraplength=480,
            justify="left"
        ).pack(anchor="w", padx=10, pady=(1, 4))

        # Grid de Mallas Pasantes
        f_grid_p = ctk.CTkFrame(self.card_gr, fg_color="transparent")
        f_grid_p.pack(fill="x", padx=8, pady=2)
        f_grid_p.columnconfigure((0, 1), weight=1)

        # % P4
        f_p4 = ctk.CTkFrame(f_grid_p, fg_color="transparent")
        f_p4.grid(row=0, column=0, padx=4, pady=3, sticky="ew")
        ctk.CTkLabel(f_p4, text="% Pasante malla N°4", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_p4 = ctk.CTkEntry(f_p4, height=26, fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_p4.insert(0, "100.00")
        self.e_p4.pack(fill="x", pady=1)

        # % P10
        f_p10 = ctk.CTkFrame(f_grid_p, fg_color="transparent")
        f_p10.grid(row=0, column=1, padx=4, pady=3, sticky="ew")
        ctk.CTkLabel(f_p10, text="% Pasante malla N°10", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_p10 = ctk.CTkEntry(f_p10, height=26, fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_p10.insert(0, "99.50")
        self.e_p10.pack(fill="x", pady=1)

        # % P40
        f_p40 = ctk.CTkFrame(f_grid_p, fg_color="transparent")
        f_p40.grid(row=1, column=0, padx=4, pady=3, sticky="ew")
        ctk.CTkLabel(f_p40, text="% Pasante malla N°40", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_p40 = ctk.CTkEntry(f_p40, height=26, fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_p40.insert(0, "96.80")
        self.e_p40.pack(fill="x", pady=1)

        # % P200
        f_p200 = ctk.CTkFrame(f_grid_p, fg_color="transparent")
        f_p200.grid(row=1, column=1, padx=4, pady=3, sticky="ew")
        ctk.CTkLabel(f_p200, text="% Pasante malla N°200", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_p200 = ctk.CTkEntry(f_p200, height=26, fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_p200.insert(0, "78.40")
        self.e_p200.pack(fill="x", pady=1)

        # Diámetros D60, D30, D10
        f_grid_d = ctk.CTkFrame(self.card_gr, fg_color="transparent")
        f_grid_d.pack(fill="x", padx=8, pady=2)
        f_grid_d.columnconfigure((0, 1, 2), weight=1)

        f_d60 = ctk.CTkFrame(f_grid_d, fg_color="transparent")
        f_d60.grid(row=0, column=0, padx=3, pady=2, sticky="ew")
        ctk.CTkLabel(f_d60, text="D60 (mm)", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_d60 = ctk.CTkEntry(f_d60, height=26, placeholder_text="—", fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_d60.pack(fill="x", pady=1)

        f_d30 = ctk.CTkFrame(f_grid_d, fg_color="transparent")
        f_d30.grid(row=0, column=1, padx=3, pady=2, sticky="ew")
        ctk.CTkLabel(f_d30, text="D30 (mm)", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_d30 = ctk.CTkEntry(f_d30, height=26, placeholder_text="—", fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_d30.pack(fill="x", pady=1)

        f_d10 = ctk.CTkFrame(f_grid_d, fg_color="transparent")
        f_d10.grid(row=0, column=2, padx=3, pady=2, sticky="ew")
        ctk.CTkLabel(f_d10, text="D10 (mm)", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_d10 = ctk.CTkEntry(f_d10, height=26, placeholder_text="—", fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_d10.pack(fill="x", pady=1)

        # Coeficientes Cu y Cc
        f_grid_c = ctk.CTkFrame(self.card_gr, fg_color="transparent")
        f_grid_c.pack(fill="x", padx=8, pady=2)
        f_grid_c.columnconfigure((0, 1), weight=1)

        f_cu = ctk.CTkFrame(f_grid_c, fg_color="transparent")
        f_cu.grid(row=0, column=0, padx=4, pady=2, sticky="ew")
        ctk.CTkLabel(f_cu, text="Coef. de uniformidad, Cu", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_cu = ctk.CTkEntry(f_cu, height=26, placeholder_text="= D60 / D10", fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_cu.pack(fill="x", pady=1)

        f_cc = ctk.CTkFrame(f_grid_c, fg_color="transparent")
        f_cc.grid(row=0, column=1, padx=4, pady=2, sticky="ew")
        ctk.CTkLabel(f_cc, text="Coef. de curvatura, Cc", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_cc = ctk.CTkEntry(f_cc, height=26, placeholder_text="= D30² / (D60·D10)", fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_cc.pack(fill="x", pady=1)

        ctk.CTkLabel(
            self.card_gr,
            text="💡 Si escribe D60, D30 y D10, Cu y Cc se calculan solos.",
            font=ctk.CTkFont(size=9),
            text_color=NEUTRAL_MUTED
        ).pack(anchor="w", padx=10, pady=(2, 6))

        # ------------------------------------------------------------------
        # 2. OPCIÓN 2: AGREGAR LÍMITES DE ATTERBERG
        # ------------------------------------------------------------------
        self.card_att = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_att.pack(fill="x", pady=4, padx=2)

        hdr_att = ctk.CTkFrame(self.card_att, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
        hdr_att.pack(fill="x", padx=4, pady=4)
        hdr_att.pack_propagate(False)

        ctk.CTkLabel(
            hdr_att,
            text="🥣  Opción 2: Agregar Límites de Atterberg (ASTM D4318)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=PRIMARY
        ).pack(side="left", padx=8, pady=3)

        self.lbl_estado_att = ctk.CTkLabel(
            hdr_att,
            text="⏳ Pendiente",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=ACCENT_RED
        )
        self.lbl_estado_att.pack(side="right", padx=8)

        # Botón destacado para abrir el ensayo completo de atterberg
        f_btn_att = ctk.CTkFrame(self.card_att, fg_color="transparent")
        f_btn_att.pack(fill="x", padx=8, pady=(4, 2))

        crear_boton(
            f_btn_att,
            "📋 Abrir Ensayo de Límites de Atterberg (Copas, golpes y taras)",
            self.abrir_ensayo_atterberg,
            color=PRIMARY,
            hover=PRIMARY_HOVER,
            icon="🥣",
            height=30
        ).pack(side="left", fill="x", expand=True)

        crear_boton(
            f_btn_att,
            "Traer datos",
            self.sincronizar_atterberg,
            color=CARD_BG_ALT,
            hover=BORDER_COLOR,
            width=100,
            height=30,
            icon="🔗"
        ).pack(side="right", padx=(6, 0))

        # Barra secundaria con NP y ayuda
        f_sub_att = ctk.CTkFrame(self.card_att, fg_color="transparent")
        f_sub_att.pack(fill="x", padx=8, pady=(2, 2))

        self.var_np = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            f_sub_att,
            text="Material No Plástico (NP) — Sin plasticidad",
            variable=self.var_np,
            command=self.toggle_np,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=ACCENT_RED,
            height=18
        ).pack(side="left")

        ctk.CTkLabel(
            self.card_att,
            text="Abra el ensayo para registrar puntos de Casagrande, o escriba abajo LL y LP:",
            font=ctk.CTkFont(size=9),
            text_color=NEUTRAL_MUTED,
            wraplength=480,
            justify="left"
        ).pack(anchor="w", padx=10, pady=(1, 4))

        f_grid_att = ctk.CTkFrame(self.card_att, fg_color="transparent")
        f_grid_att.pack(fill="x", padx=8, pady=2)
        f_grid_att.columnconfigure((0, 1, 2), weight=1)

        f_ll = ctk.CTkFrame(f_grid_att, fg_color="transparent")
        f_ll.grid(row=0, column=0, padx=3, pady=2, sticky="ew")
        ctk.CTkLabel(f_ll, text="Límite Líquido (LL)", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_ll = ctk.CTkEntry(f_ll, height=26, fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_ll.insert(0, "39.70")
        self.e_ll.pack(fill="x", pady=1)

        f_lp = ctk.CTkFrame(f_grid_att, fg_color="transparent")
        f_lp.grid(row=0, column=1, padx=3, pady=2, sticky="ew")
        ctk.CTkLabel(f_lp, text="Límite Plástico (LP)", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_lp = ctk.CTkEntry(f_lp, height=26, fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_lp.insert(0, "23.40")
        self.e_lp.pack(fill="x", pady=1)

        f_ip = ctk.CTkFrame(f_grid_att, fg_color="transparent")
        f_ip.grid(row=0, column=2, padx=3, pady=2, sticky="ew")
        ctk.CTkLabel(f_ip, text="Índice Plástico (IP)", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w")
        self.e_ip = ctk.CTkEntry(f_ip, height=26, placeholder_text="= LL − LP", fg_color="#FFFFFF", border_color=BORDER_COLOR, font=ctk.CTkFont(family="Consolas", size=11))
        self.e_ip.insert(0, "16.30")
        self.e_ip.pack(fill="x", pady=1)

        ctk.CTkLabel(
            self.card_att,
            text="💡 Si escribe LL y LP, el IP se calcula automáticamente.",
            font=ctk.CTkFont(size=9),
            text_color=NEUTRAL_MUTED
        ).pack(anchor="w", padx=10, pady=(2, 6))

        # Eventos reactivos en tiempo real
        self.e_d60.bind("<KeyRelease>", self.calc_cu_cc_event)
        self.e_d30.bind("<KeyRelease>", self.calc_cu_cc_event)
        self.e_d10.bind("<KeyRelease>", self.calc_cu_cc_event)
        self.e_ll.bind("<KeyRelease>", self.calc_ip_event)
        self.e_lp.bind("<KeyRelease>", self.calc_ip_event)

        # 4. Botonera inferior
        b_bar = ctk.CTkFrame(self.panel_izquierdo, fg_color="transparent")
        b_bar.pack(fill="x", pady=6)
        crear_boton(b_bar, "Evaluar Clasificación", self.calcular, color=PRIMARY, hover=PRIMARY_HOVER, icon="⚡").pack(side="left", padx=2, fill="x", expand=True)
        crear_boton(b_bar, "Sincronizar Ambos", self.sincronizar_desde_ensayos, color=PRIMARY_LIGHT, hover=PRIMARY_BORDER, icon="🔗").pack(side="left", padx=2, fill="x", expand=True)
        b_bar.winfo_children()[-1].configure(text_color=PRIMARY)
        crear_boton(b_bar, "Cargar ejemplo", self.cargar_demo, color=CARD_BG_ALT, hover=BORDER_COLOR, icon="🧪").pack(side="left", padx=2, fill="x", expand=True)
        crear_boton(b_bar, "Limpiar", self.limpiar, color=NEUTRAL_MUTED, hover=NEUTRAL_BODY, icon="🗑").pack(side="left", padx=2, fill="x", expand=True)

    def calc_cu_cc_event(self, event=None):
        try:
            d60_s = self.e_d60.get().strip()
            d30_s = self.e_d30.get().strip()
            d10_s = self.e_d10.get().strip()
            if d60_s and d10_s:
                d60 = float(d60_s)
                d10 = float(d10_s)
                if d10 > 0 and d60 > 0:
                    cu = d60 / d10
                    self.e_cu.delete(0, "end"); self.e_cu.insert(0, f"{cu:.2f}")
                    if d30_s:
                        d30 = float(d30_s)
                        cc = (d30 * d30) / (d60 * d10)
                        self.e_cc.delete(0, "end"); self.e_cc.insert(0, f"{cc:.2f}")
        except Exception:
            pass

    def calc_ip_event(self, event=None):
        try:
            ll_s = self.e_ll.get().strip()
            lp_s = self.e_lp.get().strip()
            if ll_s and lp_s:
                ll = float(ll_s)
                lp = float(lp_s)
                if lp >= 0:
                    ip = max(0.0, ll - lp)
                    self.e_ip.delete(0, "end")
                    self.e_ip.insert(0, f"{ip:.1f}")
        except Exception:
            pass

    def toggle_np(self):
        if self.var_np.get():
            self.e_ll.delete(0, "end"); self.e_ll.insert(0, "0.0")
            self.e_lp.delete(0, "end"); self.e_lp.insert(0, "0.0")
            self.e_ip.delete(0, "end"); self.e_ip.insert(0, "0.0")
            self.e_ll.configure(state="disabled")
            self.e_lp.configure(state="disabled")
            self.e_ip.configure(state="disabled")
        else:
            self.e_ll.configure(state="normal")
            self.e_lp.configure(state="normal")
            self.e_ip.configure(state="normal")
        if hasattr(self, "lbl_estado_att"):
            self.actualizar_estados_insumos()

    def abrir_ensayo_granulometria(self):
        """Abre el ensayo de granulometría para colocar los tamices y calcular."""
        self.controller.origen_clasificacion = True
        self.controller.mostrar("Granulometria")

    def abrir_ensayo_atterberg(self):
        """Abre el ensayo de límites de Atterberg para registrar copas de Casagrande y calcular."""
        self.controller.origen_clasificacion = True
        self.controller.mostrar("LimitesAtterberg")

    def sincronizar_granulometria(self, silent=False):
        g = self.controller.geo_state["ensayos"].get("granulometria", {})
        if g and g.get("p4") is not None:
            self.e_p4.delete(0, "end"); self.e_p4.insert(0, f"{g['p4']:.2f}")
            self.e_p10.delete(0, "end"); self.e_p10.insert(0, f"{g['p10']:.2f}")
            self.e_p40.delete(0, "end"); self.e_p40.insert(0, f"{g['p40']:.2f}")
            self.e_p200.delete(0, "end"); self.e_p200.insert(0, f"{g['p200']:.2f}")

            self.e_d60.delete(0, "end")
            if g.get("d60"): self.e_d60.insert(0, f"{g['d60']:.3f}")
            self.e_d30.delete(0, "end")
            if g.get("d30"): self.e_d30.insert(0, f"{g['d30']:.3f}")
            self.e_d10.delete(0, "end")
            if g.get("d10"): self.e_d10.insert(0, f"{g['d10']:.3f}")

            self.e_cu.delete(0, "end")
            if g.get("cu"): self.e_cu.insert(0, f"{g['cu']:.2f}")
            self.e_cc.delete(0, "end")
            if g.get("cc"): self.e_cc.insert(0, f"{g['cc']:.2f}")
            self.actualizar_estados_insumos()
            if not silent:
                messagebox.showinfo("Granulometría", "Datos de Granulometría cargados con éxito.")
            return True
        else:
            if not silent:
                messagebox.showwarning("Sin Granulometría", "Aún no se ha calculado el ensayo de Granulometría.\nPresione 'Abrir Ensayo de Granulometría' para ingresar los tamices.")
            return False

    def sincronizar_atterberg(self, silent=False):
        a = self.controller.geo_state["ensayos"].get("atterberg", {})
        if a and (a.get("ll") is not None or a.get("np")):
            if a.get("np"):
                self.var_np.set(True)
                self.toggle_np()
            else:
                self.var_np.set(False)
                self.toggle_np()
                self.e_ll.delete(0, "end"); self.e_ll.insert(0, f"{a['ll']:.2f}")
                self.e_lp.delete(0, "end"); self.e_lp.insert(0, f"{a['lp']:.2f}")
                ip_v = a.get("ip_entero") if a.get("ip_entero") is not None else a.get("ip")
                self.e_ip.delete(0, "end"); self.e_ip.insert(0, f"{ip_v:.2f}" if isinstance(ip_v, float) else f"{ip_v}")
            self.actualizar_estados_insumos()
            if not silent:
                messagebox.showinfo("Límites de Atterberg", "Datos de Límites de Atterberg cargados con éxito.")
            return True
        else:
            if not silent:
                messagebox.showwarning("Sin Límites", "Aún no se han calculado los Límites de Atterberg.\nPresione 'Abrir Ensayo de Límites' para ingresar las copas o registrar suelo NP.")
            return False

    def actualizar_estados_insumos(self):
        # 1. Estado Granulometría
        g = self.controller.geo_state["ensayos"].get("granulometria", {})
        if g and g.get("p4") is not None and g.get("p200") is not None:
            self.lbl_estado_gr.configure(
                text=f"✔ Listo (P4={g['p4']:.1f}%, P200={g['p200']:.1f}%)",
                text_color=ACCENT_GREEN
            )
        else:
            p4_val = self.e_p4.get().strip() if hasattr(self, "e_p4") else ""
            p200_val = self.e_p200.get().strip() if hasattr(self, "e_p200") else ""
            if p4_val and p200_val:
                self.lbl_estado_gr.configure(
                    text=f"✔ Datos Manuales (P4={p4_val}%, P200={p200_val}%)",
                    text_color=ACCENT_GREEN
                )
            else:
                self.lbl_estado_gr.configure(text="⏳ Pendiente", text_color=ACCENT_RED)

        # 2. Estado Atterberg
        a = self.controller.geo_state["ensayos"].get("atterberg", {})
        if a and a.get("np"):
            self.lbl_estado_att.configure(text="✔ No Plástico (NP)", text_color=ACCENT_GREEN)
        elif a and a.get("ll") is not None and a.get("lp") is not None:
            ip_val = a.get("ip_entero", a.get("ip"))
            self.lbl_estado_att.configure(
                text=f"✔ Listo (LL={a['ll']:.1f}%, LP={a['lp']:.1f}%, IP={ip_val})",
                text_color=ACCENT_GREEN
            )
        else:
            if self.var_np.get():
                self.lbl_estado_att.configure(text="✔ No Plástico (NP)", text_color=ACCENT_GREEN)
            else:
                ll_val = self.e_ll.get().strip() if hasattr(self, "e_ll") else ""
                lp_val = self.e_lp.get().strip() if hasattr(self, "e_lp") else ""
                if ll_val and lp_val:
                    self.lbl_estado_att.configure(text=f"✔ Datos Manuales (LL={ll_val}%, LP={lp_val}%)", text_color=ACCENT_GREEN)
                else:
                    self.lbl_estado_att.configure(text="⏳ Pendiente", text_color=ACCENT_RED)

    def al_mostrar(self):
        super().al_mostrar()
        self.sincronizar_desde_ensayos(silent=True)
        self.actualizar_estados_insumos()
        try:
            self.calcular(silent=True)
        except Exception:
            pass

    def sincronizar_desde_ensayos(self, silent=False):
        sg = self.sincronizar_granulometria(silent=True)
        sa = self.sincronizar_atterberg(silent=True)
        algo = sg or sa
        self.actualizar_estados_insumos()
        if algo:
            if not silent:
                messagebox.showinfo("Sincronización Exitosa", "Datos traídos exitosamente de Granulometría y Atterberg.")
            self.calcular(silent=silent)
        else:
            if not silent:
                messagebox.showwarning("Sin Ensayos Previos", "Aún no hay Granulometría ni Límites calculados.\nUse los botones 'Abrir Ensayo' para poner los tamices y copas, o escriba los datos a mano.")
        return algo

    def calcular(self, silent=False):
        try:
            p4_s = self.e_p4.get().strip()
            p10_s = self.e_p10.get().strip()
            p40_s = self.e_p40.get().strip()
            p200_s = self.e_p200.get().strip()

            if not p4_s or not p10_s or not p40_s or not p200_s:
                raise ValueError("Ingrese los % que pasan las mallas N°4, N°10, N°40 y N°200.")

            p4 = float(p4_s)
            p10 = float(p10_s)
            p40 = float(p40_s)
            p200 = float(p200_s)

            for v, nom in [(p4, "N°4"), (p10, "N°10"), (p40, "N°40"), (p200, "N°200")]:
                if v < 0.0 or v > 100.0:
                    raise ValueError(f"El % pasante de la malla {nom} debe estar entre 0 y 100 %.")

            d60_s = self.e_d60.get().strip()
            d30_s = self.e_d30.get().strip()
            d10_s = self.e_d10.get().strip()
            d60 = float(d60_s) if d60_s else None
            d30 = float(d30_s) if d30_s else None
            d10 = float(d10_s) if d10_s else None

            cu_s = self.e_cu.get().strip()
            cc_s = self.e_cc.get().strip()
            cu = float(cu_s) if cu_s else None
            cc = float(cc_s) if cc_s else None

            if self.var_np.get():
                ll = 0.0
                lp = 0.0
                ip = 0.0
            else:
                ll_s = self.e_ll.get().strip()
                lp_s = self.e_lp.get().strip()
                ip_s = self.e_ip.get().strip()
                ll = float(ll_s) if ll_s else 0.0
                lp = float(lp_s) if lp_s else 0.0
                ip = float(ip_s) if ip_s else max(0.0, ll - lp)

            res = clasificar_sucs(p4, p10, p40, p200, ll, ip, cu, cc)
            sucs = res["sucs"]
            aashto = res["aashto"]

            self.datos_calculados = {
                "p4": p4, "p10": p10, "p40": p40, "p200": p200,
                "d60": d60, "d30": d30, "d10": d10,
                "cu": cu, "cc": cc,
                "ll": ll, "lp": lp, "ip": ip,
                "np": self.var_np.get(),
                "sucs": sucs, "aashto": aashto,
                "pasos": res["pasos"],
                "lineaA": res["lineaA"],
                "graficar": res["graficar"],
                "incompleto": res["incompleto"]
            }
            self.calculado = True
            self.controller.geo_state["ensayos"]["clasificacion"] = self.datos_calculados
            self.actualizar_estados_insumos()
            self.mostrar_resultados()
            if not silent:
                messagebox.showinfo("Clasificación Geotécnica", f"Resultados:\n• SUCS: {sucs['simbolo']} ({sucs['desc']})\n• AASHTO: {aashto['texto']} — {aashto['desc']}")

        except Exception as e:
            if not silent:
                messagebox.showerror("Error en Clasificación", str(e))

    def mostrar_resultados(self):
        for w in self.contenedor_resultados.winfo_children():
            w.destroy()

        d = self.datos_calculados

        # 1. KPI Grid de Resultados (SUCS y AASHTO)
        kpi_frame = ctk.CTkFrame(self.contenedor_resultados, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        kpi_frame.pack(fill="x", pady=(4, 6))

        # Mini-card SUCS
        f_sucs = ctk.CTkFrame(kpi_frame, fg_color=PRIMARY_LIGHT, corner_radius=6, border_width=1, border_color=PRIMARY_BORDER)
        f_sucs.pack(fill="x", padx=6, pady=4)
        ctk.CTkLabel(f_sucs, text="SUCS (ASTM D2487)", font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY).pack(pady=(4, 1))
        ctk.CTkLabel(f_sucs, text=d['sucs']['simbolo'], font=ctk.CTkFont(size=24, weight="bold"), text_color=PRIMARY).pack(pady=(0, 1))
        ctk.CTkLabel(f_sucs, text=d['sucs']['desc'], font=ctk.CTkFont(size=11, weight="bold"), text_color=NEUTRAL_BODY).pack(pady=(0, 4))

        # Mini-card AASHTO
        f_aash = ctk.CTkFrame(kpi_frame, fg_color=CARD_BG_ALT, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        f_aash.pack(fill="x", padx=6, pady=(0, 4))
        ctk.CTkLabel(f_aash, text="AASHTO (M 145)", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_MUTED).pack(pady=(4, 1))
        ctk.CTkLabel(f_aash, text=d['aashto']['texto'], font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT_GREEN).pack(pady=(0, 1))
        ctk.CTkLabel(f_aash, text=d['aashto']['desc'], font=ctk.CTkFont(size=10), text_color=NEUTRAL_BODY, wraplength=460).pack(pady=(0, 4))

        # 2. Cómo se llegó a la clasificación (Pasos analíticos)
        c_pasos = ctk.CTkFrame(self.contenedor_resultados, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        c_pasos.pack(fill="x", pady=4)
        ctk.CTkLabel(c_pasos, text="📋  Cómo se llegó a la clasificación (Procedimiento):", font=ctk.CTkFont(size=10, weight="bold"), text_color=NEUTRAL_HEADING).pack(anchor="w", padx=8, pady=(6, 3))
        for idx, paso in enumerate(d["pasos"], 1):
            ctk.CTkLabel(c_pasos, text=f"{idx}. {paso}", font=ctk.CTkFont(size=9), text_color=NEUTRAL_BODY, wraplength=470, justify="left").pack(anchor="w", padx=12, pady=1)
        ctk.CTkLabel(c_pasos, text="", font=ctk.CTkFont(size=2)).pack(pady=(0, 3))

        # 3. Carta de Plasticidad de Casagrande
        c_chart = ctk.CTkFrame(self.contenedor_resultados, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        c_chart.pack(fill="both", expand=True, pady=4)
        ctk.CTkLabel(c_chart, text="📊  Carta de Plasticidad de Casagrande (para finos):", font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY).pack(anchor="w", padx=8, pady=(6, 2))

        fig = self.generar_figura()
        canvas = FigureCanvasTkAgg(fig, master=c_chart)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=2)

        # Nota condicional idéntica a la web
        if d["graficar"]:
            nota_txt = f"Punto de la muestra: LL = {d['ll']:.1f} %, IP = {d['ip']:.1f} % (marcador amarillo)."
            nota_col = PRIMARY
        else:
            nota_txt = "El punto (LL, IP) solo se grafica cuando hay suelo fino (N°200 ≥ 50 %) o más de 12 % de finos."
            nota_col = NEUTRAL_MUTED

        ctk.CTkLabel(c_chart, text=nota_txt, font=ctk.CTkFont(size=9), text_color=nota_col).pack(pady=(0, 6))

    def generar_figura(self):
        d = self.datos_calculados
        fig, ax = plt.subplots(figsize=(5.4, 3.2), dpi=100)

        # Polígonos de zonas Casagrande idénticos a js/app.js
        poly_mh = patches.Polygon([[50, 0], [100, 0], [100, 0.73 * (100 - 20)], [50, 21.9]], closed=True, facecolor="#F4A582", alpha=0.85, label="MH / OH")
        poly_ch = patches.Polygon([[50, 21.9], [100, 0.73 * (100 - 20)], [100, 0.9 * (100 - 8)], [50, 37.8]], closed=True, facecolor="#7CA1CC", alpha=0.85, label="CH")
        poly_cl = patches.Polygon([[15.78, 7], [29.59, 7], [50, 21.9], [50, 37.8]], closed=True, facecolor="#A6D0D6", alpha=0.85, label="CL")
        poly_ml = patches.Polygon([[8, 0], [12.44, 4], [25.48, 4], [50, 21.9], [50, 0]], closed=True, facecolor="#FCD29F", alpha=0.85, label="ML / OL")
        poly_clml = patches.Polygon([[12.44, 4], [15.78, 7], [29.59, 7], [25.48, 4]], closed=True, facecolor="#C5D3E8", hatch="//", alpha=0.9, label="CL-ML")

        for p in [poly_mh, poly_ch, poly_cl, poly_ml, poly_clml]:
            ax.add_patch(p)

        # Línea A: IP = 0.73 * (LL - 20)
        ax.plot([20, 100], [0, 0.73 * 80], color="#002855", linestyle="-", linewidth=1.4, label="Línea A: IP=0.73(LL-20)")
        # Línea U: IP = 0.9 * (LL - 8)
        ax.plot([8, 100], [0, 0.9 * 92], color="#1A365D", linestyle="--", linewidth=1.1, label="Línea U: IP=0.9(LL-8)")
        # Línea LL = 50
        ax.axvline(x=50, color="#D62728", linestyle=":", linewidth=1.2, label="Límite LL=50%")

        # Textos de zonas
        ax.text(36, 18, "CL", fontsize=9, fontweight="bold", color="#111", ha="center")
        ax.text(72, 42, "CH", fontsize=9, fontweight="bold", color="#111", ha="center")
        ax.text(38, 5, "ML / OL", fontsize=8, fontweight="bold", color="#111", ha="center")
        ax.text(76, 15, "MH / OH", fontsize=8, fontweight="bold", color="#111", ha="center")
        ax.text(19, 5.5, "CL-ML", fontsize=7, fontweight="bold", color="#111", ha="center")

        # Graficar muestra solo si graficar == True
        if d.get("graficar"):
            ll = d["ll"]
            ip = d["ip"]
            ax.scatter([ll], [ip], color="#FBBF24", edgecolors="#111827", s=90, zorder=6, label=f"Muestra (LL={ll:.1f}, IP={ip:.1f})")

        ax.set_xlim(0, 100)
        ax.set_ylim(0, 60)
        ax.set_xlabel("LÍMITE LÍQUIDO (LL), %", fontsize=8, fontweight="bold", color=NEUTRAL_HEADING)
        ax.set_ylabel("ÍNDICE DE PLASTICIDAD (IP), %", fontsize=8, fontweight="bold", color=NEUTRAL_HEADING)
        ax.set_title("CARTA DE PLASTICIDAD DE CASAGRANDE (ASTM D2487)", fontsize=9, fontweight="bold", color=PRIMARY)
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.legend(fontsize=6.5, loc="upper left", framealpha=0.85)

        fig.tight_layout()
        return fig

    def cargar_demo(self):
        self.var_np.set(False)
        self.toggle_np()
        self.e_p4.delete(0, "end"); self.e_p4.insert(0, "100.00")
        self.e_p10.delete(0, "end"); self.e_p10.insert(0, "99.50")
        self.e_p40.delete(0, "end"); self.e_p40.insert(0, "96.80")
        self.e_p200.delete(0, "end"); self.e_p200.insert(0, "78.40")

        self.e_d60.delete(0, "end")
        self.e_d30.delete(0, "end")
        self.e_d10.delete(0, "end")
        self.e_cu.delete(0, "end")
        self.e_cc.delete(0, "end")

        self.e_ll.delete(0, "end"); self.e_ll.insert(0, "39.70")
        self.e_lp.delete(0, "end"); self.e_lp.insert(0, "23.40")
        self.e_ip.delete(0, "end"); self.e_ip.insert(0, "16.30")
        self.modo_manual = True
        self.actualizar_estados_insumos()
        self.calcular()

    def limpiar(self):
        super().limpiar()
        self.e_p4.delete(0, "end")
        self.e_p10.delete(0, "end")
        self.e_p40.delete(0, "end")
        self.e_p200.delete(0, "end")
        self.e_d60.delete(0, "end")
        self.e_d30.delete(0, "end")
        self.e_d10.delete(0, "end")
        self.e_cu.delete(0, "end")
        self.e_cc.delete(0, "end")
        self.e_ll.delete(0, "end")
        self.e_lp.delete(0, "end")
        self.e_ip.delete(0, "end")
        self.var_np.set(False)
        self.toggle_np()
        self.actualizar_estados_insumos()

    def exportar_pdf(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar Informe de Clasificación Geotécnica",
            defaultextension=".pdf",
            initialfile=f"Informe_Clasificacion_{self.controller.datos_proyecto.get('muestra', 'M-01')}.pdf",
            filetypes=[("Archivo PDF", "*.pdf")]
        )
        if not ruta:
            return
        try:
            doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            est = obtener_estilos_pdf()
            elems = crear_cabecera_pdf(est, self.titulo, self.codigo_norma)
            elems.append(crear_tabla_metadatos(self.controller.datos_proyecto))
            elems.append(Spacer(1, 10))

            elems.append(Paragraph("RESULTADO OFICIAL DE CLASIFICACIÓN GEOTÉCNICA", est["seccion"]))
            d = self.datos_calculados
            t_data = [
                ["Sistema de Clasificación", "Símbolo / Grupo", "Descripción del Suelo", "Norma"],
                ["SUCS (ASTM D2487)", d['sucs']['simbolo'], d['sucs']['desc'], "ASTM D2487 / NTP 339.134"],
                ["AASHTO (M 145)", d['aashto']['texto'], f"Grupo {d['aashto']['grupo']} (IG={d['aashto']['ig']}) • {d['aashto']['desc']}", "AASHTO M 145 / MTC E 101"]
            ]
            t = Table(t_data, colWidths=[120, 85, 205, 90])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            elems.append(t)
            elems.append(Spacer(1, 10))

            elems.append(Paragraph("PARÁMETROS GEOTÉCNICOS UTILIZADOS", est["seccion"]))
            cu_txt = f"{d['cu']:.2f}" if d.get('cu') is not None else "---"
            cc_txt = f"{d['cc']:.2f}" if d.get('cc') is not None else "---"
            t_params_data = [
                ["% Pasa N°4", "% Pasa N°10", "% Pasa N°40", "% Pasa N°200", "Límite Líquido", "Índice Plástico", "Cu", "Cc"],
                [f"{d['p4']:.1f}%", f"{d['p10']:.1f}%", f"{d['p40']:.1f}%", f"{d['p200']:.1f}%", f"{round(d['ll'])}%", f"{round(d['ip'])}%", cu_txt, cc_txt]
            ]
            t_params = Table(t_params_data, colWidths=[62, 62, 62, 65, 65, 64, 60, 60])
            t_params.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY_LIGHT)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elems.append(t_params)
            elems.append(Spacer(1, 10))

            # Pasos
            elems.append(Paragraph("PROCEDIMIENTO Y JUSTIFICACIÓN NORMATIVA", est["seccion"]))
            for idx, paso in enumerate(d["pasos"], 1):
                elems.append(Paragraph(f"<b>{idx}.</b> {paso}", est["celda_normal"]))
            elems.append(Spacer(1, 8))

            fig = self.generar_figura()
            img = figura_a_imagen_reportlab(fig, width=440, height=220)
            elems.append(img)
            elems.append(Spacer(1, 12))
            elems.append(crear_bloque_firmas(est))

            doc.build(elems)
            if messagebox.askyesno("PDF Generado", f"Informe guardado con éxito:\n{ruta}\n\n¿Desea abrirlo ahora?"):
                os.startfile(ruta)
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))

# -------------------------------------------------------------------
# ENSAYO 07: COMPACTACIÓN PROCTOR (ASTM D698 / ASTM D1557)
# -------------------------------------------------------------------
class CompactacionProctor(BaseEnsayo):
    titulo = "07. COMPACTACIÓN PROCTOR"
    subtitulo = "Máxima densidad seca (MDS) y óptimo contenido de humedad (OCH) según ASTM D698 / D1557"
    codigo_norma = "ASTM D698 • ASTM D1557 • NTP 339.141 / 142"
    clave_ensayo = "proctor"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        scroll_in = ctk.CTkScrollableFrame(self.panel_izquierdo, fg_color="transparent")
        scroll_in.pack(fill="both", expand=True)

        # Datos del molde y equipo
        self.form_molde = TablaFormulario(scroll_in, "Datos del Molde y Suelo", "🥫")
        self.form_molde.pack(fill="x", pady=(0, 6))
        self.form_molde.agregar_fila("vol", "Volumen del molde (V)", "cm³", "944.0")
        self.form_molde.agregar_fila("peso_molde", "Peso del molde vacío", "g", "4178.0")
        self.form_molde.agregar_fila("gs", "Gravedad Específica de sólidos (Gs)", "", "2.650")

        f_gs_btn = ctk.CTkFrame(self.form_molde, fg_color="transparent")
        f_gs_btn.pack(fill="x", padx=8, pady=(0, 4))
        b_usar_gs = crear_boton(
            f_gs_btn,
            "🔗 Usar Gs del Ensayo 03",
            self.usar_gs_ensayo3,
            color=PRIMARY_LIGHT,
            hover=PRIMARY_BORDER,
            height=24,
            icon="🔗"
        )
        b_usar_gs.pack(side="right")
        b_usar_gs.configure(text_color=PRIMARY)

        # Tabla de puntos de ensayo
        self.card_pts = ctk.CTkFrame(scroll_in, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_pts.pack(fill="x", pady=4)
        hdr = ctk.CTkFrame(self.card_pts, fg_color=PRIMARY_LIGHT, corner_radius=6, height=32)
        hdr.pack(fill="x", padx=4, pady=4)
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="📈  Puntos de Ensayo (Compactación)", font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY).pack(side="left", padx=10, pady=4)

        self.filas_pro = []
        f_tp = ctk.CTkFrame(self.card_pts, fg_color="transparent")
        f_tp.pack(fill="x", padx=6, pady=4)
        headers = ["Punto", "Molde+Suelo (g)", "Tarro (g)", "Tarro+Húm. (g)", "Tarro+Seco (g)"]
        cols_w = [40, 115, 95, 115, 115]
        hf = ctk.CTkFrame(f_tp, fg_color=CARD_BG_ALT, height=26)
        hf.pack(fill="x", pady=2)
        for h, w in zip(headers, cols_w):
            ctk.CTkLabel(hf, text=h, font=ctk.CTkFont(size=9, weight="bold"), text_color=NEUTRAL_HEADING, width=w).pack(side="left", padx=2)

        for i in range(1, 6):
            rf = ctk.CTkFrame(f_tp, fg_color="transparent")
            rf.pack(fill="x", pady=1)
            ctk.CTkLabel(rf, text=f"P-{i}", font=ctk.CTkFont(size=10, weight="bold"), text_color=PRIMARY, width=40).pack(side="left", padx=2)
            e_msh = ctk.CTkEntry(rf, height=24, width=115, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_msh.pack(side="left", padx=2)
            e_tarro = ctk.CTkEntry(rf, height=24, width=95, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_tarro.insert(0, "30.0")
            e_tarro.pack(side="left", padx=2)
            e_tsh = ctk.CTkEntry(rf, height=24, width=115, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_tsh.pack(side="left", padx=2)
            e_tss = ctk.CTkEntry(rf, height=24, width=115, fg_color="#FFFFFF", border_color=BORDER_COLOR)
            e_tss.pack(side="left", padx=2)
            self.filas_pro.append({"num": i, "msh": e_msh, "tarro": e_tarro, "tsh": e_tsh, "tss": e_tss})

        # Botonera
        b_bar = ctk.CTkFrame(self.panel_izquierdo, fg_color="transparent")
        b_bar.pack(fill="x", pady=8)
        crear_boton(b_bar, "Calcular", self.calcular, color=PRIMARY, hover=PRIMARY_HOVER, icon="⚡").pack(side="left", padx=3, fill="x", expand=True)
        crear_boton(b_bar, "Ejemplo (Demo)", self.cargar_demo, color=PRIMARY_LIGHT, hover=PRIMARY_BORDER, icon="🧪").pack(side="left", padx=3, fill="x", expand=True)
        b_bar.winfo_children()[-1].configure(text_color=PRIMARY)
        crear_boton(b_bar, "Limpiar", self.limpiar, color=NEUTRAL_MUTED, hover=NEUTRAL_BODY, icon="🗑").pack(side="left", padx=3, fill="x", expand=True)

    def usar_gs_ensayo3(self):
        g = self.controller.geo_state["ensayos"].get("gravedad", {})
        if g and "promedio_g20" in g:
            val = g["promedio_g20"]
            self.form_molde.set("gs", f"{val:.3f}")
            messagebox.showinfo("Gs Importado", f"Se cargó Gs = {val:.3f} desde el Ensayo 03 (Gravedad Específica).")
        else:
            messagebox.showwarning("Sin Ensayo 03", "Aún no se ha calculado el Ensayo 03. Ingrese Gs manualmente.")

    def calcular(self):
        try:
            vol = float(self.form_molde.get("vol") or 944.0)
            p_molde = float(self.form_molde.get("peso_molde") or 4178.0)
            gs_s = self.form_molde.get("gs")
            gs = float(gs_s) if gs_s else 2.650

            puntos = []
            for r in self.filas_pro:
                msh_s, tarro_s, tsh_s, tss_s = r["msh"].get().strip(), r["tarro"].get().strip(), r["tsh"].get().strip(), r["tss"].get().strip()
                if not msh_s and not tsh_s and not tss_s:
                    continue
                if not msh_s or not tarro_s or not tsh_s or not tss_s:
                    raise ValueError(f"En Punto {r['num']}, complete todas las pesadas.")
                msh, tarro, tsh, tss = float(msh_s), float(tarro_s), float(tsh_s), float(tss_s)
                if msh <= p_molde or tss <= tarro or tsh < tss:
                    raise ValueError(f"Datos incoherentes en Punto {r['num']}.")

                m_suelo = msh - p_molde
                m_seco = tss - tarro
                w = ((tsh - tss) / m_seco) * 100.0
                rho_h = m_suelo / vol
                rho_d = rho_h / (1.0 + w / 100.0)

                puntos.append({"num": r["num"], "msuelo": m_suelo, "rho_h": rho_h, "w": w, "rho_d": rho_d})

            if len(puntos) < 3:
                raise ValueError("Se requieren al menos 3 puntos válidos para ajustar la curva Proctor.")

            # Ajuste cuadrático: rho_d = a*w^2 + b*w + c
            fit = regresion_parabolica([p["w"] for p in puntos], [p["rho_d"] for p in puntos])
            if not fit or fit[0] >= 0:
                raise ValueError("Los datos no forman una parábola con máximo (cóncava hacia abajo). Verifique la progresión de humedades y densidades.")

            a, b, c, r2 = fit
            och = -b / (2.0 * a)
            mds = a * (och ** 2) + b * och + c
            mds95 = 0.95 * mds
            gamma_kn = mds * 9.80665

            w_vals = [p["w"] for p in puntos]
            opt_dentro = (min(w_vals) <= och <= max(w_vals))
            sr = (((och / 100.0) * gs) / ((gs / mds) - 1.0) * 100.0) if (gs and mds and (gs / mds) > 1.0) else None

            self.datos_calculados = {
                "vol": vol, "peso_molde": p_molde, "gs": gs,
                "puntos": puntos,
                "a": a, "b": b, "c": c, "r2": r2,
                "och": och, "mds": mds, "mds95": mds95, "gamma_kn_m3": gamma_kn,
                "opt_dentro": opt_dentro, "sr": sr
            }
            self.calculado = True
            self.controller.geo_state["ensayos"]["proctor"] = self.datos_calculados
            self.mostrar_resultados()
            messagebox.showinfo("Cálculo Proctor", f"Resultados de Compactación:\n• Máxima Densidad Seca (MDS): {mds:.3f} g/cm³\n• Óptimo Contenido de Humedad (OCH): {och:.2f} %\n• Peso volumétrico seco: {gamma_kn:.2f} kN/m³")

        except Exception as e:
            messagebox.showerror("Error en Proctor", str(e))

    def mostrar_resultados(self):
        for w in self.contenedor_resultados.winfo_children():
            w.destroy()

        d = self.datos_calculados
        res_card = ctk.CTkFrame(self.contenedor_resultados, fg_color=PRIMARY_LIGHT, corner_radius=8, border_width=1, border_color=PRIMARY_BORDER)
        res_card.pack(fill="x", pady=(4, 6))
        f_grid = ctk.CTkFrame(res_card, fg_color="transparent")
        f_grid.pack(fill="x", padx=8, pady=6)
        f_grid.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(f_grid, text="MÁXIMA DENSIDAD SECA (MDS):", font=ctk.CTkFont(size=9, weight="bold"), text_color=PRIMARY).grid(row=0, column=0)
        ctk.CTkLabel(f_grid, text=f"{d['mds']:.3f} g/cm³", font=ctk.CTkFont(size=18, weight="bold"), text_color=PRIMARY).grid(row=1, column=0)

        ctk.CTkLabel(f_grid, text="ÓPTIMO CONTENIDO DE HUMEDAD (OCH):", font=ctk.CTkFont(size=9, weight="bold"), text_color=PRIMARY).grid(row=0, column=1)
        ctk.CTkLabel(f_grid, text=f"{d['och']:.2f} %", font=ctk.CTkFont(size=18, weight="bold"), text_color=PRIMARY).grid(row=1, column=1)

        sr_txt = f"   |   Sr = {d['sr']:.1f} %" if d.get("sr") else ""
        ctk.CTkLabel(f_grid, text=f"95% de MDS: {d['mds95']:.3f} g/cm³   |   γd = {d['gamma_kn_m3']:.2f} kN/m³{sr_txt}", font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_GREEN).grid(row=2, column=0, columnspan=2, pady=(4, 2))

        aviso_txt = "✓ El óptimo cae dentro del rango de humedades ensayadas." if d.get("opt_dentro") else "⚠ El óptimo queda fuera del rango ensayado: conviene extender humedades."
        aviso_col = ACCENT_GREEN if d.get("opt_dentro") else ACCENT_RED
        ctk.CTkLabel(res_card, text=aviso_txt, font=ctk.CTkFont(size=9, weight="bold"), text_color=aviso_col).pack(pady=(0, 4))

        # Gráfico Curva de Compactación Matplotlib
        fig = self.generar_figura()
        canvas = FigureCanvasTkAgg(fig, master=self.contenedor_resultados)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, pady=6)

    def generar_figura(self):
        d = self.datos_calculados
        fig, ax = plt.subplots(figsize=(5.5, 3.2), dpi=100)

        pts = d["puntos"]
        xs = [p["w"] for p in pts]
        ys = [p["rho_d"] for p in pts]
        ax.scatter(xs, ys, color=PRIMARY, s=40, zorder=3, label="Puntos Ensayados")

        # Parábola suave
        a, b, c = d["a"], d["b"], d["c"]
        min_w = min(xs) - 1.5
        max_w = max(xs) + 1.5
        w_curve = [min_w + (max_w - min_w) * (i / 100.0) for i in range(101)]
        rho_curve = [a * (w ** 2) + b * w + c for w in w_curve]
        ax.plot(w_curve, rho_curve, color=PRIMARY, linewidth=1.8, label=f"Parábola (R²={d['r2']:.4f})")

        # Punto óptimo
        och, mds, mds95 = d["och"], d["mds"], d["mds95"]
        ax.scatter([och], [mds], color="#EF4444", marker="*", s=140, zorder=5, label=f"Óptimo ({och:.1f}%, {mds:.3f})")
        ax.axvline(x=och, color="#EF4444", linestyle=":", linewidth=1)
        ax.axhline(y=mds, color="#EF4444", linestyle=":", linewidth=1)
        ax.axhline(y=mds95, color=ACCENT_GREEN, linestyle="--", linewidth=1, label=f"95% MDS ({mds95:.3f})")

        # Curva de Saturación al 100% (ZAV)
        gs = d.get("gs") or 2.650
        zav_w = [min_w + (max_w - min_w) * (i / 50.0) for i in range(51)]
        zav_rho = [(gs * 1.0) / (1.0 + (w / 100.0) * gs) for w in zav_w]
        ax.plot(zav_w, zav_rho, color="#6B7280", linestyle="-.", linewidth=1, label=f"Saturación 100% (Gs={gs:.3f})")

        ax.set_xlabel("Contenido de Humedad, w (%)", fontsize=8, fontweight="bold", color=NEUTRAL_HEADING)
        ax.set_ylabel("Densidad Seca, ρd (g/cm³)", fontsize=8, fontweight="bold", color=NEUTRAL_HEADING)
        ax.set_title("CURVA DE COMPACTACIÓN PROCTOR (ASTM D698 / D1557)", fontsize=9, fontweight="bold", color=PRIMARY)
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(fontsize=6.5, loc="lower left", framealpha=0.9)

        fig.tight_layout()
        return fig

    def cargar_demo(self):
        self.form_molde.set("vol", "944.0")
        self.form_molde.set("peso_molde", "4178.0")
        self.form_molde.set("gs", "2.650")
        demos = [
            [5992.8, 30.0, 138.0, 130.0],
            [6109.4, 30.0, 140.0, 130.0],
            [6186.8, 30.0, 142.0, 130.0],
            [6190.5, 30.0, 144.0, 130.0],
            [6149.1, 30.0, 146.0, 130.0]
        ]
        for i, (msh, tarro, tsh, tss) in enumerate(demos):
            self.filas_pro[i]["msh"].delete(0, "end"); self.filas_pro[i]["msh"].insert(0, f"{msh:.1f}")
            self.filas_pro[i]["tarro"].delete(0, "end"); self.filas_pro[i]["tarro"].insert(0, f"{tarro:.1f}")
            self.filas_pro[i]["tsh"].delete(0, "end"); self.filas_pro[i]["tsh"].insert(0, f"{tsh:.1f}")
            self.filas_pro[i]["tss"].delete(0, "end"); self.filas_pro[i]["tss"].insert(0, f"{tss:.1f}")
        self.calcular()

    def exportar_pdf(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar Informe Técnico de Compactación Proctor",
            defaultextension=".pdf",
            initialfile=f"Informe_Proctor_{self.controller.datos_proyecto.get('muestra', 'M-01')}.pdf",
            filetypes=[("Archivo PDF", "*.pdf")]
        )
        if not ruta:
            return
        try:
            doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            est = obtener_estilos_pdf()
            elems = crear_cabecera_pdf(est, self.titulo, self.codigo_norma)
            elems.append(crear_tabla_metadatos(self.controller.datos_proyecto))
            elems.append(Spacer(1, 10))

            elems.append(Paragraph("SÍNTESIS DE COMPACTACIÓN PROCTOR", est["seccion"]))
            d = self.datos_calculados
            t_data = [
                ["Parámetro de Compactación", "Símbolo", "Valor Obtenido", "Unidad"],
                ["Máxima Densidad Seca", "MDS", f"{d['mds']:.3f}", "g/cm³"],
                ["Óptimo Contenido de Humedad", "OCH", f"{d['och']:.2f}", "%"],
                ["95% de la Máxima Densidad Seca", "95% MDS", f"{d['mds95']:.3f}", "g/cm³"],
                ["Peso Volumétrico Seco Máximo", "γd,max", f"{d['gamma_kn_m3']:.2f}", "kN/m³"],
                ["Gravedad Específica asumida", "Gs", f"{d['gs']:.3f}", "---"]
            ]
            t = Table(t_data, colWidths=[180, 80, 120, 100])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elems.append(t)
            elems.append(Spacer(1, 10))

            fig = self.generar_figura()
            img = figura_a_imagen_reportlab(fig, width=440, height=210)
            elems.append(img)
            elems.append(Spacer(1, 12))
            elems.append(crear_bloque_firmas(est))

            doc.build(elems)
            if messagebox.askyesno("PDF Generado", f"Informe guardado con éxito:\n{ruta}\n\n¿Desea abrirlo ahora?"):
                os.startfile(ruta)
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))

# -------------------------------------------------------------------
# PANEL PRINCIPAL / DASHBOARD (PORTADA CON LOS 7 ENSAYOS)
# -------------------------------------------------------------------
class MenuPrincipal(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=FONDO)
        self.controller = controller

        # Banner institucional formal
        Cabecera(
            self,
            "LABORATORIO DE MECÁNICA DE SUELOS • ING. GEOLÓGICA FIGMM",
            "Sistema profesional de cálculo geotécnico y emisión de informes técnicos de laboratorio"
        ).pack(fill="x", padx=20, pady=(14, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Cuadrícula de los 7 Ensayos
        grid_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        grid_frame.pack(fill="x", pady=4)
        grid_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.ensayos_info = [
            ("01", "Contenido de Humedad", "ASTM D2216 • NTP 339.127", "ContenidoHumedad", "humedad"),
            ("02", "Peso Volumétrico", "NTP 339.139 • ASTM D7263", "PesoVolumetrico", "volumetrico"),
            ("03", "Gravedad Específica (Gs)", "ASTM D854 • NTP 339.131", "GravedadEspecifica", "gravedad"),
            ("04", "Granulometría por Tamizado", "ASTM D6913 • NTP 339.128", "Granulometria", "granulometria"),
            ("05", "Límites de Atterberg", "ASTM D4318 • NTP 339.129", "LimitesAtterberg", "atterberg"),
            ("06", "Clasificación SUCS y AASHTO", "ASTM D2487 • AASHTO M 145", "ClasificacionSuelos", "clasificacion"),
            ("07", "Compactación Proctor", "ASTM D698 • ASTM D1557", "CompactacionProctor", "proctor"),
        ]

        self.chips_estado = {}

        for idx, (num, titulo, norma, destino, clave) in enumerate(self.ensayos_info):
            r = idx // 3
            c = idx % 3

            card = ctk.CTkFrame(grid_frame, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
            card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

            # Encabezado tarjeta
            h_top = ctk.CTkFrame(card, fg_color="transparent")
            h_top.pack(fill="x", padx=10, pady=(10, 4))

            # Número distintivo
            num_lbl = ctk.CTkLabel(
                h_top,
                text=num,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=PRIMARY,
                fg_color=PRIMARY_LIGHT,
                corner_radius=4,
                width=32,
                height=32
            )
            num_lbl.pack(side="left")

            # Chip de estado
            chip = ctk.CTkLabel(
                h_top,
                text="Pendiente",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=NEUTRAL_MUTED,
                fg_color=CARD_BG_ALT,
                corner_radius=4,
                width=75,
                height=22
            )
            chip.pack(side="right")
            self.chips_estado[clave] = chip

            # Título y norma
            ctk.CTkLabel(
                card,
                text=titulo,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=NEUTRAL_HEADING,
                anchor="w",
                justify="left"
            ).pack(fill="x", padx=12, pady=(4, 1))

            ctk.CTkLabel(
                card,
                text=norma,
                font=ctk.CTkFont(size=10),
                text_color=NEUTRAL_MUTED,
                anchor="w"
            ).pack(fill="x", padx=12, pady=(0, 10))

            # Botón de ingreso directo
            crear_boton(
                card,
                "Ingresar Datos / Revisar →",
                lambda d=destino: controller.mostrar(d),
                color=PRIMARY_LIGHT,
                hover=PRIMARY_BORDER,
                width=200,
                height=30
            ).pack(fill="x", padx=10, pady=(0, 10))
            card.winfo_children()[-1].configure(text_color=PRIMARY)

        # Barra inferior de consolidación general
        b_cons = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        b_cons.pack(fill="x", padx=20, pady=(4, 10))

        ctk.CTkLabel(
            b_cons,
            text="📑  Consolidación de Informes y Resumen Ejecutivo",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PRIMARY
        ).pack(side="left", padx=16, pady=10)

        crear_boton(
            b_cons,
            "Resumen General de Resultados",
            self.abrir_resumen,
            color=PRIMARY_LIGHT,
            hover=PRIMARY_BORDER,
            width=210,
            height=32,
            icon="📋"
        ).pack(side="right", padx=(4, 12), pady=8)
        b_cons.winfo_children()[-1].configure(text_color=PRIMARY)

        crear_boton(
            b_cons,
            "Exportar Informe Consolidado (PDF)",
            self.controller.exportar_informe_consolidado,
            color=ACCENT_GREEN,
            hover=ACCENT_GREEN_HOVER,
            width=250,
            height=32,
            icon="📄"
        ).pack(side="right", padx=4, pady=8)

    def actualizar_estados(self):
        for num, tit, norma, dest, clave in self.ensayos_info:
            frame = self.controller.frames.get(dest)
            ok = bool(frame and frame.calculado)
            chip = self.chips_estado.get(clave)
            if chip:
                if ok:
                    chip.configure(text="Calculado", text_color=ACCENT_GREEN, fg_color=ACCENT_GREEN_LIGHT)
                else:
                    chip.configure(text="Pendiente", text_color=NEUTRAL_MUTED, fg_color=CARD_BG_ALT)

    def abrir_resumen(self):
        ResumenGeneralDialog(self, self.controller)

class ResumenGeneralDialog(ctk.CTkToplevel):
    """Ventana modal de síntesis de propiedades geotécnicas."""
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.title("Resumen General de Resultados Geotécnicos")
        self.geometry("740x580")
        self.transient(parent.winfo_toplevel())
        self.configure(fg_color=FONDO)

        Cabecera(self, "SÍNTESIS GEOTÉCNICA DEL SUELO", "Resultados consolidados de todos los ensayos de laboratorio").pack(fill="x", padx=16, pady=(16, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # Construir tabla
        st = controller.geo_state["ensayos"]
        hum = st.get("humedad", {})
        vol = st.get("volumetrico", {})
        gs = st.get("gravedad", {})
        gran = st.get("granulometria", {})
        att = st.get("atterberg", {})
        cls = st.get("clasificacion", {})
        pro = st.get("proctor", {})

        filas = [
            ("Contenido de humedad (w)", f"{hum['promedio']:.1f} %" if hum.get('promedio') else "Pendiente", "01. Humedad"),
            ("Densidad natural húmeda (ρ)", f"{vol['rho_humeda']:.3f} g/cm³" if vol.get('rho_humeda') else "Pendiente", "02. Peso Volumétrico"),
            ("Peso volumétrico húmedo (γ)", f"{vol['gamma_kn_m3']:.2f} kN/m³" if vol.get('gamma_kn_m3') else "Pendiente", "02. Peso Volumétrico"),
            ("Densidad seca (ρd)", f"{vol['rho_seca']:.3f} g/cm³" if vol.get('rho_seca') else "---", "02. Peso Volumétrico"),
            ("Peso volumétrico seco (γd)", f"{vol['gamma_seca']:.2f} kN/m³" if vol.get('gamma_seca') else "---", "02. Peso Volumétrico"),
            ("Gravedad específica (Gs)", f"{gs['gs']:.3f}" if gs.get('gs') else "Pendiente", "03. Gravedad Específica"),
        ]

        # Relaciones de fases estimadas
        val_gs = gs.get("gs")
        val_rhod = vol.get("rho_seca")
        val_w = hum.get("promedio")
        if val_gs and val_rhod and val_rhod > 0:
            e_rel = (val_gs * 1.0 / val_rhod) - 1.0
            if e_rel > 0:
                n_poro = (e_rel / (1.0 + e_rel)) * 100.0
                filas.append(("Relación de vacíos estimada (e)", f"{e_rel:.3f}", "Fases (Gs y ρd)"))
                filas.append(("Porosidad estimada (n)", f"{n_poro:.1f} %", "Fases (Gs y ρd)"))
                if val_w:
                    sr = (val_w * val_gs) / e_rel
                    filas.append(("Grado de saturación (Sr)", f"{sr:.1f} %", "Fases (w, Gs y e)"))

        fe = gran.get("fe")
        if fe:
            frac_txt = f"{fe['grava']}% Grava / {fe['arena']}% Arena / {fe['finos']}% Finos"
        elif gran.get("grava") is not None:
            frac_txt = f"{gran['grava']:.1f}% Grava / {gran['arena']:.1f}% Arena / {gran['finos']:.1f}% Finos"
        else:
            frac_txt = "Pendiente"

        if att.get('ll') is not None:
            ll_txt = f"LL={att.get('ll_entero', round(att['ll']))}% / LP={att.get('lp_entero', round(att['lp']))}% / IP={att.get('ip_entero', round(att['ip']))}%"
        elif att.get('np'):
            ll_txt = "No Plástico (NP)"
        else:
            ll_txt = "Pendiente"

        filas.extend([
            ("Fracción Grava / Arena / Finos", frac_txt, "04. Granulometría"),
            ("Coeficientes Cu / Cc", f"Cu={gran['cu']:.2f} / Cc={gran['cc']:.2f}" if gran.get('cu') else "---", "04. Granulometría"),
            ("Límites LL / LP / IP", ll_txt, "05. Atterberg"),
            ("Clasificación SUCS", f"{cls['sucs']['simbolo']} ({cls['sucs']['desc']})" if cls.get('sucs') else "Pendiente", "06. Clasificación"),
            ("Clasificación AASHTO", f"{cls['aashto']['texto']}" if cls.get('aashto') else "Pendiente", "06. Clasificación"),
            ("Proctor: MDS / OCH", f"MDS={pro['mds']:.3f} g/cm³ / OCH={pro['och']:.2f}%" if pro.get('mds') else "Pendiente", "07. Proctor"),
        ])

        # Renderizar filas
        for i, (param, val, origen) in enumerate(filas):
            f = ctk.CTkFrame(scroll, fg_color="#FFFFFF" if i % 2 == 0 else CARD_BG_ALT)
            f.pack(fill="x", pady=1)
            ctk.CTkLabel(f, text=param, font=ctk.CTkFont(size=11, weight="bold"), text_color=NEUTRAL_HEADING, width=280, anchor="w").pack(side="left", padx=10, pady=5)
            ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY if "Pendiente" not in val else NEUTRAL_MUTED, width=250, anchor="w").pack(side="left", padx=6)
            ctk.CTkLabel(f, text=origen, font=ctk.CTkFont(size=10, slant="italic"), text_color=NEUTRAL_MUTED, anchor="e").pack(side="right", padx=10)

        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=16, pady=(0, 16))
        crear_boton(btn_bar, "Cerrar", self.destroy, color=NEUTRAL_MUTED, hover=NEUTRAL_BODY, width=120).pack(side="right")

# -------------------------------------------------------------------
# APLICACIÓN PRINCIPAL (CONTROLLER)
# -------------------------------------------------------------------
class SoftwareMecanicaSuelos(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GeoLab - Sistema de Mecánica de Suelos (FIGMM / UNI)")
        self.geometry("1300x800")
        self.minsize(1120, 680)
        self.configure(fg_color=FONDO)

        # Datos globales de proyecto
        self.datos_proyecto = DEFAULT_PROYECTO.copy()
        self.origen_clasificacion = False

        # Estado global de ensayos GeoState idéntico a app.js
        self.geo_state = {
            "proyecto": self.datos_proyecto,
            "ensayos": {
                "humedad": {},
                "volumetrico": {},
                "gravedad": {},
                "granulometria": {},
                "atterberg": {},
                "clasificacion": {},
                "proctor": {}
            }
        }

        # Cinta superior de datos de proyecto
        # Cola de resultados del guardado en la base de datos (se revisa cada 0.4 s)
        self.cola_servidor = queue.Queue()
        self._aviso_servidor_mostrado = False

        self.barra_proyecto = BarraProyecto(self, self)
        self.barra_proyecto.pack(fill="x")

        # Contenedor para alternar vistas
        self.contenedor = ctk.CTkFrame(self, fg_color=FONDO)
        self.contenedor.pack(fill="both", expand=True)
        self.contenedor.grid_rowconfigure(0, weight=1)
        self.contenedor.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for Clase in (
            MenuPrincipal,
            ContenidoHumedad,
            PesoVolumetrico,
            GravedadEspecifica,
            Granulometria,
            LimitesAtterberg,
            ClasificacionSuelos,
            CompactacionProctor
        ):
            frame = Clase(self.contenedor, self)
            self.frames[Clase.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.mostrar("MenuPrincipal")

        # Al abrir, reenviar informes que hayan quedado pendientes de la vez anterior
        if api_client is not None and api_client.hay_sesion():
            threading.Thread(target=api_client.enviar_pendientes, daemon=True).start()
        self.after(400, self._revisar_cola_servidor)

    # ---------------------------------------------------------------
    # Base de datos
    # ---------------------------------------------------------------
    def registrar_informe(self, clave, ruta_pdf, tipo="individual"):
        """Envía a la base de datos el informe recién exportado (en segundo plano)."""
        if api_client is None:
            return
        try:
            payload = construir_informe(self, clave, ruta_pdf, tipo)
        except Exception as e:
            self.barra_proyecto.actualizar_servidor(f"No se pudo preparar el informe: {e}", "error")
            return
        self.barra_proyecto.actualizar_servidor("☁ Guardando informe en la base de datos...", "pendiente")
        api_client.guardar_en_segundo_plano(payload, self.cola_servidor)

    def _revisar_cola_servidor(self):
        mensajes = []
        try:
            while True:
                mensajes.append(self.cola_servidor.get_nowait())
        except queue.Empty:
            pass
        self.after(400, self._revisar_cola_servidor)
        for estado, mensaje in mensajes:
            self.barra_proyecto.actualizar_servidor(mensaje, estado)
            if estado in ("sin_sesion", "pendiente") and not self._aviso_servidor_mostrado:
                self._aviso_servidor_mostrado = True
                messagebox.showinfo("Base de datos", mensaje)

    def mostrar(self, nombre):
        frame = self.frames.get(nombre)
        if frame:
            if nombre == "MenuPrincipal":
                frame.actualizar_estados()
            if hasattr(frame, "al_mostrar"):
                frame.al_mostrar()
            frame.tkraise()

    def exportar_informe_consolidado(self):
        ESTADO_PDF["ultimo"] = None
        self._exportar_informe_consolidado_pdf()
        if ESTADO_PDF["ultimo"]:
            self.registrar_informe("consolidado", ESTADO_PDF["ultimo"], "consolidado")

    def _exportar_informe_consolidado_pdf(self):
        """Genera el informe consolidado completo con todos los 7 ensayos en PDF."""
        calculados = []
        for name, fr in self.frames.items():
            if name != "MenuPrincipal" and getattr(fr, "calculado", False):
                calculados.append(fr)

        if not calculados:
            messagebox.showwarning(
                "Sin Ensayos Calculados",
                "Aún no se ha calculado ningún ensayo.\n\nIngrese a cualquiera de los ensayos y presione '⚡ Calcular'."
            )
            return

        ruta = filedialog.asksaveasfilename(
            title="Guardar Informe Técnico Consolidado",
            defaultextension=".pdf",
            initialfile=f"Informe_Consolidado_{self.datos_proyecto.get('muestra', 'M-01')}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
            filetypes=[("Archivo PDF", "*.pdf")]
        )
        if not ruta:
            return

        try:
            doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            est = obtener_estilos_pdf()
            elems = []

            # Encabezado consolidado
            elems.append(Paragraph("LABORATORIO DE MECÁNICA DE SUELOS • ING. GEOLÓGICA FIGMM", est["titulo_institucion"]))
            elems.append(Paragraph("INFORME TÉCNICO GENERAL CONSOLIDADO DE LABORATORIO", est["titulo_informe"]))
            elems.append(Paragraph("Ensayos de Caracterización Física, Propiedades Índice y Mecánica de Suelos", est["norma_ref"]))
            elems.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(PRIMARY), spaceAfter=6))
            elems.append(crear_tabla_metadatos(self.datos_proyecto))
            elems.append(Spacer(1, 10))

            # Resumen Ejecutivo
            elems.append(Paragraph("SÍNTESIS DE PROPIEDADES GEOTÉCNICAS OBTENIDAS", est["seccion"]))
            st = self.geo_state["ensayos"]
            hum = st.get("humedad", {})
            vol = st.get("volumetrico", {})
            gs = st.get("gravedad", {})
            gran = st.get("granulometria", {})
            att = st.get("atterberg", {})
            cls = st.get("clasificacion", {})
            pro = st.get("proctor", {})

            fe_gran = gran.get("fe")
            frac_res_txt = f"{fe_gran['grava']}% G / {fe_gran['arena']}% S / {fe_gran['finos']}% F" if fe_gran else ("---" if gran.get("grava") is None else f"{gran['grava']:.1f}% / {gran['arena']:.1f}% / {gran['finos']:.1f}%")

            res_data = [
                ["Parámetro Físico / Geotécnico", "Símbolo", "Valor Obtenido", "Unidad", "Estado"],
                ["Contenido de humedad", "w", f"{hum['promedio']:.1f}" if hum.get('promedio') else "---", "%", "Calculado" if hum.get('promedio') else "Pendiente"],
                ["Densidad húmeda", "ρ", f"{vol['rho_humeda']:.4f}" if vol.get('rho_humeda') else "---", "g/cm³", "Calculado" if vol.get('rho_humeda') else "Pendiente"],
                ["Peso volumétrico húmedo", "γ", f"{vol['gamma_kn_m3']:.3f}" if vol.get('gamma_kn_m3') else "---", "kN/m³", "Calculado" if vol.get('gamma_kn_m3') else "Pendiente"],
                ["Densidad seca", "ρd", f"{vol['rho_seca']:.4f}" if vol.get('rho_seca') else "---", "g/cm³", "Calculado" if vol.get('rho_seca') else "---"],
                ["Peso volumétrico seco", "γd", f"{vol['gamma_seca']:.3f}" if vol.get('gamma_seca') else "---", "kN/m³", "Calculado" if vol.get('gamma_seca') else "---"],
                ["Gravedad específica", "Gs", f"{gs['gs']:.3f}" if gs.get('gs') else "---", "---", "Calculado" if gs.get('gs') else "Pendiente"],
                ["Fracciones de Suelo (G / S / F)", "G/S/F", frac_res_txt, "%", "Calculado" if fe_gran or gran.get("grava") is not None else "Pendiente"],
                ["Límite Líquido", "LL", f"{att.get('ll_entero', round(att['ll']))}" if att.get('ll') is not None else ("NP" if att.get('np') else "---"), "%", "Calculado" if att.get('ll') is not None or att.get('np') else "Pendiente"],
                ["Límite Plástico", "LP", f"{att.get('lp_entero', round(att['lp']))}" if att.get('lp') is not None else ("NP" if att.get('np') else "---"), "%", "Calculado" if att.get('lp') is not None or att.get('np') else "Pendiente"],
                ["Índice de Plasticidad", "IP", f"{att.get('ip_entero', round(att['ip']))}" if att.get('ip') is not None else ("NP" if att.get('np') else "---"), "%", "Calculado" if att.get('ip') is not None or att.get('np') else "Pendiente"],
                ["Clasificación SUCS", "SUCS", f"{cls['sucs']['simbolo']}" if cls.get('sucs') else "---", "---", "Calculado" if cls.get('sucs') else "Pendiente"],
                ["Clasificación AASHTO", "AASHTO", f"{cls['aashto']['texto']}" if cls.get('aashto') else "---", "---", "Calculado" if cls.get('aashto') else "Pendiente"],
                ["Máxima Densidad Seca", "MDS", f"{pro['mds']:.3f}" if pro.get('mds') else "---", "g/cm³", "Calculado" if pro.get('mds') else "Pendiente"],
                ["Óptimo Contenido de Humedad", "OCH", f"{pro['och']:.2f}" if pro.get('och') else "---", "%", "Calculado" if pro.get('och') else "Pendiente"],
            ]

            t_res = Table(res_data, colWidths=[170, 55, 115, 70, 130])
            t_res.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elems.append(t_res)
            elems.append(Spacer(1, 14))

            # Gráficos si están calculados
            f_gran = self.frames.get("Granulometria")
            if f_gran and f_gran.calculado:
                elems.append(Paragraph("CURVA GRANULOMÉTRICA (ASTM D6913)", est["seccion"]))
                fig_g = f_gran.generar_figura()
                elems.append(figura_a_imagen_reportlab(fig_g, width=440, height=210))
                elems.append(Spacer(1, 10))

            f_cls = self.frames.get("ClasificacionSuelos")
            if f_cls and f_cls.calculado:
                elems.append(Paragraph("CARTA DE PLASTICIDAD DE CASAGRANDE (SUCS)", est["seccion"]))
                fig_c = f_cls.generar_figura()
                elems.append(figura_a_imagen_reportlab(fig_c, width=440, height=210))
                elems.append(Spacer(1, 10))

            f_pro = self.frames.get("CompactacionProctor")
            if f_pro and f_pro.calculado:
                elems.append(Paragraph("CURVA DE COMPACTACIÓN PROCTOR (ASTM D698 / D1557)", est["seccion"]))
                fig_p = f_pro.generar_figura()
                elems.append(figura_a_imagen_reportlab(fig_p, width=440, height=210))
                elems.append(Spacer(1, 10))

            elems.append(KeepTogether([
                crear_bloque_firmas(est),
                Spacer(1, 6),
                Paragraph("Documento oficial emitido por GeoLab • FIGMM / UNI", est["subtitulo_sistema"])
            ]))

            doc.build(elems)
            if messagebox.askyesno("Informe Consolidado Generado", f"Informe Técnico Consolidado guardado con éxito:\n\n{ruta}\n\n¿Desea abrirlo ahora?"):
                os.startfile(ruta)

        except Exception as e:
            messagebox.showerror("Error al generar Informe Consolidado", str(e))

if __name__ == "__main__":
    import traceback
    try:
        app = SoftwareMecanicaSuelos()
        app.mainloop()
    except Exception as error:
        traceback.print_exc()
        print(f"Error al ejecutar GeoLab Desktop: {error}")
