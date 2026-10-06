#!/usr/bin/env python3
"""
Prepara el GeoJSON de comunas de CABA con geometría REAL (polígonos oficiales).

Descarga/lee el GeoJSON oficial de Buenos Aires Data y lo simplifica (reduce
vértices con el algoritmo de Ramer–Douglas–Peucker, sin dependencias) para que
el mapa coroplético del dashboard tenga la forma auténtica de Buenos Aires sin
inflar el HTML. Mantiene las propiedades `comuna` y `barrios`.

Salida: lago/raw/comunas/<HOY>.geojson  (el pipeline lo copia a gold y lo usa el mapa)

Uso:
    python scripts/prep_comunas.py                # usa el oficial ya descargado
    python scripts/prep_comunas.py --descargar    # lo baja de BA Data primero
"""
from __future__ import annotations
import _utf8  # noqa: F401
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_COMUNAS = ROOT / "lago" / "raw" / "comunas"
OFICIAL = RAW_COMUNAS / "_oficial.geojson"
URL = ("https://cdn.buenosaires.gob.ar/datosabiertos/datasets/"
       "ministerio-de-educacion/comunas/comunas.geojson")

# tolerancia de simplificación en grados (~5e-5° ≈ 5 m). Más bajo = más fiel al contorno real.
TOLERANCIA = 0.00005


def _descargar() -> None:
    RAW_COMUNAS.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "cerebro-ba/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        OFICIAL.write_bytes(resp.read())
    print(f"[ok] descargado -> {OFICIAL.relative_to(ROOT)}")


def _dist_punto_segmento(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def _rdp(pts, tol):
    """Ramer–Douglas–Peucker: simplifica una polilínea conservando la forma."""
    if len(pts) < 3:
        return pts
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        d = _dist_punto_segmento(pts[i], pts[0], pts[-1])
        if d > dmax:
            dmax, idx = d, i
    if dmax > tol:
        izq = _rdp(pts[:idx + 1], tol)
        der = _rdp(pts[idx:], tol)
        return izq[:-1] + der
    return [pts[0], pts[-1]]


def _simplificar_anillo(anillo):
    r = _rdp([tuple(p) for p in anillo], TOLERANCIA)
    if r[0] != r[-1]:                      # cerrar el anillo
        r = r + [r[0]]
    return [[round(x, 6), round(y, 6)] for x, y in r]


def _simplificar_geom(geom):
    t = geom.get("type")
    c = geom.get("coordinates", [])
    if t == "Polygon":
        return {"type": "Polygon", "coordinates": [_simplificar_anillo(c[0])]}
    if t == "MultiPolygon":
        # conserva solo el anillo exterior de cada polígono
        polys = [[_simplificar_anillo(poly[0])] for poly in c if poly]
        return {"type": "MultiPolygon", "coordinates": polys}
    return geom


def main() -> int:
    if "--descargar" in sys.argv or not OFICIAL.exists():
        print("Descargando GeoJSON oficial de comunas (BA Data)…")
        try:
            _descargar()
        except Exception as e:
            print(f"[!] No se pudo descargar ({e}). "
                  f"Dejá el archivo en {OFICIAL.relative_to(ROOT)} y reintentá.",
                  file=sys.stderr)
            return 1

    gj = json.loads(OFICIAL.read_text(encoding="utf-8"))
    v_in = v_out = 0
    feats = []
    for f in gj.get("features", []):
        props = f.get("properties", {})
        comuna = props.get("comuna")
        geom = f.get("geometry", {})
        # contar vértices antes
        def _nv(g):
            c = g.get("coordinates", [])
            if g.get("type") == "Polygon":
                return sum(len(r) for r in c)
            if g.get("type") == "MultiPolygon":
                return sum(len(r) for poly in c for r in poly)
            return 0
        v_in += _nv(geom)
        geom_s = _simplificar_geom(geom)
        v_out += _nv(geom_s)
        feats.append({
            "type": "Feature",
            "properties": {"comuna": int(comuna) if comuna is not None else None,
                           "nombre": f"Comuna {comuna}",
                           "barrios": props.get("barrios", "")},
            "geometry": geom_s,
        })

    feats.sort(key=lambda x: x["properties"]["comuna"] or 0)
    salida = {
        "type": "FeatureCollection",
        "_origen": "BA Data (oficial, simplificado RDP)",
        "_fuente_url": URL,
        "features": feats,
    }
    hoy = dt.date.today().isoformat()
    destino = RAW_COMUNAS / f"{hoy}.geojson"
    destino.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")

    # sidecar de metadatos para trazabilidad
    (destino.with_suffix(destino.suffix + ".meta.json")).write_text(json.dumps({
        "dominio": "comunas", "fuente": "Buenos Aires Data",
        "organismo": "GCBA", "url": URL, "licencia": "CC-BY",
        "formato": "geojson", "fecha_ingesta": dt.datetime.now().isoformat(timespec="seconds"),
        "herramienta": "prep_comunas (RDP)", "_origen": "oficial",
        "vertices_in": v_in, "vertices_out": v_out,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ok] comunas reales -> {destino.relative_to(ROOT)}")
    print(f"     vértices: {v_in:,} -> {v_out:,} ({100*v_out/v_in:.1f}% conservado)")
    print(f"     tamaño: {destino.stat().st_size/1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
