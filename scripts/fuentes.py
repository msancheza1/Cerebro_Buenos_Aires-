#!/usr/bin/env python3
"""
Registro central de FUENTES (Tramo 1). Cada entrada apunta a un recurso descargable
real de Buenos Aires Data. Las URLs siguen el patrón del portal CKAN de CABA
(https://data.buenosaires.gob.ar/). Verificá la vigencia contra catalogo/catalogo.csv.

Nota: BA Data reorganiza rutas cada tanto. Si una URL da 404, buscá el dataset por su
slug en el portal o vía la API CKAN (scripts/catalogo_ckan.py) y actualizá acá.
"""
from __future__ import annotations

BASE = "https://data.buenosaires.gob.ar"
CDN = "https://cdn.buenosaires.gob.ar/datosabiertos/datasets"

# dominio -> {url, formato, licencia, organismo}
# URLs verificadas (2026-10): el portal CKAN tiene un WAF que rechaza api/datasets/*,
# por eso usamos el CDN (sin WAF) o el endpoint /resource/<uuid>/download.
FUENTES = {
    "ecobici": {
        "url": f"{CDN}/transporte-y-obras-publicas/estaciones-bicicletas-publicas/nuevas-estaciones-bicicletas-publicas.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Secretaría de Transporte y Obras Públicas (GCBA)",
        "fuente": "Buenos Aires Data",
    },
    "ciclovias": {
        "url": f"{CDN}/transporte-y-obras-publicas/ciclovias/ciclovias.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Secretaría de Transporte y Obras Públicas (GCBA)",
        "fuente": "Buenos Aires Data",
    },
    "espacios_verdes": {
        "url": f"{BASE}/dataset/espacios-verdes/resource/df878bd5-5759-4af3-badc-2a4c1ae0ebf8/download",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Ministerio de Espacio Público e Higiene Urbana (GCBA)",
        "fuente": "Buenos Aires Data",
    },
    "hospitales": {
        "url": f"{CDN}/ministerio-de-salud/hospitales/hospitales.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Ministerio de Salud (GCBA)",
        "fuente": "Buenos Aires Data",
    },
    "comunas": {
        "url": f"{CDN}/ministerio-de-educacion/comunas/comunas.geojson",
        "formato": "geojson",
        "licencia": "CC-BY",
        "organismo": "GCBA",
        "fuente": "Buenos Aires Data",
    },
}
