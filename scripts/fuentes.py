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

# dominio -> {url, formato, licencia, organismo}
FUENTES = {
    "ecobici": {
        "url": f"{BASE}/api/datasets/estaciones-bicicletas-publicas/estaciones-bicicletas-publicas.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Secretaría de Transporte y Obras Públicas (GCBA)",
        "fuente": "Buenos Aires Data",
    },
    "ciclovias": {
        "url": f"{BASE}/api/datasets/ciclovias/ciclovias.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Secretaría de Transporte y Obras Públicas (GCBA)",
        "fuente": "Buenos Aires Data",
    },
    "espacios_verdes": {
        "url": f"{BASE}/api/datasets/espacios-verdes/espacios-verdes.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Ministerio de Espacio Público e Higiene Urbana (GCBA)",
        "fuente": "Buenos Aires Data",
    },
    "hospitales": {
        "url": f"{BASE}/api/datasets/hospitales/hospitales.csv",
        "formato": "csv",
        "licencia": "CC-BY",
        "organismo": "Ministerio de Salud (GCBA)",
        "fuente": "Buenos Aires Data",
    },
    "comunas": {
        "url": f"{BASE}/api/datasets/comunas/comunas.geojson",
        "formato": "geojson",
        "licencia": "CC-BY",
        "organismo": "GCBA",
        "fuente": "Buenos Aires Data",
    },
}
