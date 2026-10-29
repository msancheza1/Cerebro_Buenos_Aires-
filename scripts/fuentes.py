#!/usr/bin/env python3
"""Registro central y contratos mínimos de las fuentes configuradas de BA Data.

Las URLs no se consideran verificadas hasta que la ingesta descarga el recurso y valida
su contenido. Si BA Data cambia una ruta o esquema, la corrida oficial falla cerrada en
vez de publicar datos incompatibles.
"""
from __future__ import annotations

BASE = "https://data.buenosaires.gob.ar"

FUENTES = {
    "poblacion": {
        "url": "https://www.estadisticaciudad.gob.ar/eyc/wp-content/uploads/2022/12/PB2_22nb.xls",
        "ficha": "https://www.estadisticaciudad.gob.ar/eyc/banco-datos/poblacion-total-por-sexo-registrado-al-nacer-superficie-y-densidad-poblacional-segun-comuna-ciudad-de-buenos-aires-anos-2010-2022/",
        "formato": "xls", "licencia": "No verificada",
        "organismo": "IDECBA (GCBA), sobre la base de INDEC, Censo 2022",
        "fuente": "Instituto de Estadística y Censos de la Ciudad Autónoma de Buenos Aires",
        "anio_poblacion": 2022,
    },
    "ecobici": {
        "url": "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/transporte-y-obras-publicas/estaciones-bicicletas-publicas/nuevas-estaciones-bicicletas-publicas.csv",
        "formato": "csv",
        "licencia": "CC-BY-2.5-AR",
        "organismo": "Secretaría de Transporte y Obras Públicas (GCBA)",
        "fuente": "Buenos Aires Data",
        "columnas_requeridas": ["id", "nombre", "latitud", "longitud"],
    },
    "ciclovias": {
        "url": "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/transporte-y-obras-publicas/ciclovias/ciclovias.csv",
        "formato": "csv",
        "licencia": "CC-BY-2.5-AR",
        "organismo": "Secretaría de Transporte y Obras Públicas (GCBA)",
        "fuente": "Buenos Aires Data",
        "columnas_requeridas": ["id", "nombre", "comuna", "longitud_m", "tipo"],
    },
    "espacios_verdes": {
        "url": "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/secretaria-de-desarrollo-urbano/espacios-verdes/espacio_verde_publico.geojson",
        "formato": "geojson", "licencia": "CC-BY-2.5-AR",
        "organismo": "GCBA, DG Gobernanza de Datos Abiertos",
        "fuente": "Buenos Aires Data",
    },
    "hospitales": {
        "url": "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-salud/hospitales/hospitales.geojson",
        "formato": "geojson", "licencia": "CC-BY-2.5-AR",
        "organismo": "Ministerio de Salud (GCBA)", "fuente": "Buenos Aires Data",
    },
    "comunas": {
        "url": "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/comunas/comunas.geojson",
        "formato": "geojson",
        "licencia": "CC-BY-2.5-AR",
        "organismo": "GCBA",
        "fuente": "Buenos Aires Data",
    },
}
