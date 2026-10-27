#!/usr/bin/env python3
"""
Utilidades geoespaciales mínimas (sin dependencias): asignar comuna a un punto.

Varios datasets reales de BA Data traen lat/lon pero NO el número de comuna
(p.ej. estaciones Ecobici). Con el GeoJSON oficial de comunas podemos derivarla
por "punto en polígono" (ray casting), que es exactamente lo que haría una unión
espacial en PostGIS/GeoPandas, pero con stdlib.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _anillos_por_comuna(geojson_path: Path) -> dict:
    """{comuna: [anillo_exterior, ...]} con anillos en [lon, lat]."""
    if not geojson_path.exists():
        return {}
    gj = json.loads(geojson_path.read_text(encoding="utf-8"))
    out = {}
    for feat in gj.get("features", []):
        comuna = feat.get("properties", {}).get("comuna")
        geom = feat.get("geometry", {})
        t, c = geom.get("type"), geom.get("coordinates", [])
        anillos = []
        if t == "Polygon" and c:
            anillos = [c[0]]
        elif t == "MultiPolygon" and c:
            anillos = [poly[0] for poly in c if poly]
        if comuna is not None and anillos:
            out[int(comuna)] = anillos
    return out


def _punto_en_anillo(lon: float, lat: float, anillo) -> bool:
    """Ray casting: ¿(lon,lat) dentro del anillo (lista de [lon,lat])?"""
    dentro = False
    n = len(anillo)
    j = n - 1
    for i in range(n):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if ((yi > lat) != (yj > lat)) and \
           (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            dentro = not dentro
        j = i
    return dentro


class LocalizadorComunas:
    """Asigna número de comuna (1..15) a un punto (lon, lat)."""

    def __init__(self, geojson_path: Path):
        self._por_comuna = _anillos_por_comuna(geojson_path)

    def disponible(self) -> bool:
        return bool(self._por_comuna)

    def comuna_de(self, lon, lat):
        if lon is None or lat is None:
            return None
        for comuna, anillos in self._por_comuna.items():
            if any(_punto_en_anillo(lon, lat, a) for a in anillos):
                return comuna
        return None
