#!/usr/bin/env python3
"""Registro central y contratos mínimos de las fuentes configuradas de BA Data.

Las URLs no se consideran verificadas hasta que la ingesta descarga el recurso y valida
su contenido. Si BA Data cambia una ruta o esquema, la corrida oficial falla cerrada en
vez de publicar datos incompatibles.
"""
from __future__ import annotations

BASE = "https://data.buenosaires.gob.ar"

FUENTES = {
    "ecobici": {
        "url": f"{BASE}/api/datasets/estaciones-bicicletas-publicas/estaciones-bicicletas-publicas.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Secretaría de Transporte y Obras Públicas (GCBA)",
        "fuente": "Buenos Aires Data",
        "columnas_requeridas": ["id", "nombre", "comuna", "lat", "long", "anclajes_totales"],
    },
    "ciclovias": {
        "url": f"{BASE}/api/datasets/ciclovias/ciclovias.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Secretaría de Transporte y Obras Públicas (GCBA)",
        "fuente": "Buenos Aires Data",
        "columnas_requeridas": ["id", "nombre", "comuna", "long_metros", "tipo"],
    },
    "espacios_verdes": {
        "url": f"{BASE}/api/datasets/espacios-verdes/espacios-verdes.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Ministerio de Espacio Público e Higiene Urbana (GCBA)",
        "fuente": "Buenos Aires Data",
        "columnas_requeridas": ["id", "nombre", "comuna", "area_m2", "clasificacion", "lat", "lon"],
    },
    "hospitales": {
        "url": f"{BASE}/api/datasets/hospitales/hospitales.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Ministerio de Salud (GCBA)",
        "fuente": "Buenos Aires Data",
        "columnas_requeridas": ["id", "nombre", "tipo", "comuna", "direccion", "lat", "lon"],
    },
    "comunas": {
        "url": f"{BASE}/api/datasets/comunas/comunas.geojson",
        "formato": "geojson",
        "licencia": "CC-BY",
        "organismo": "GCBA",
        "fuente": "Buenos Aires Data",
    },
}
