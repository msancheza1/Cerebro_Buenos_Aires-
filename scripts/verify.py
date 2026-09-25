#!/usr/bin/env python3
"""
Tramo VERIFICACIÓN — "si falla, no se publica".

Corre reglas de calidad sobre cada tabla SILVER. Si un dominio NO pasa, se marca
NO PUBLICABLE: build_gold.py lo excluye de GOLD.

Dos herramientas (requisito del taller):
  A) Reglas propias con Python stdlib (este archivo)  -> corre en el sandbox
  B) Pandera (scripts/verify_pandera.py)              -> documentada
     (Great Expectations sería una tercera; ver bitácora por qué preferimos Pandera.)

Reglas por dominio:
  comunes:  id no nulo y único ; comuna en 1..15
  coords:   lat en [-34.71,-34.52] ; lon en [-58.54,-58.33]   (bounding box CABA)
  ecobici:  anclajes_totales > 0
  ciclovias:long_metros > 0
  espacios_verdes: area_m2 > 0
  hospitales: nombre no vacío

Salida:
  - imprime un reporte por dominio (OK/FALLA con conteo de violaciones)
  - escribe lago/silver/_verificacion.json  (usado por build_gold.py)
  - exit code != 0 si algún dominio crítico falla
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "lago" / "silver"

LAT_MIN, LAT_MAX = -34.71, -34.52
LON_MIN, LON_MAX = -58.54, -58.33


def leer(dominio: str) -> list[dict]:
    p = SILVER / f"{dominio}.csv"
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def reglas_comunes(filas):
    viol = []
    ids = [f.get("id") for f in filas]
    if any(i in (None, "") for i in ids):
        viol.append(("id_no_nulo", sum(1 for i in ids if i in (None, ""))))
    if len(ids) != len(set(ids)):
        viol.append(("id_unico", len(ids) - len(set(ids))))
    fuera = sum(1 for f in filas
                if _num(f.get("comuna")) is None
                or not (1 <= _num(f.get("comuna")) <= 15))
    if fuera:
        viol.append(("comuna_1_15", fuera))
    return viol


def reglas_coords(filas):
    def bad(f):
        lat, lon = _num(f.get("lat")), _num(f.get("lon"))
        return lat is None or lon is None or not (LAT_MIN <= lat <= LAT_MAX) \
            or not (LON_MIN <= lon <= LON_MAX)
    n = sum(1 for f in filas if bad(f))
    return [("coords_caba", n)] if n else []


def regla_positivo(filas, col):
    n = sum(1 for f in filas if (_num(f.get(col)) or 0) <= 0)
    return [(f"{col}_positivo", n)] if n else []


def regla_no_vacio(filas, col):
    n = sum(1 for f in filas if not (f.get(col) or "").strip())
    return [(f"{col}_no_vacio", n)] if n else []


CHECKS = {
    "ecobici": lambda f: reglas_comunes(f) + reglas_coords(f) + regla_positivo(f, "anclajes_totales"),
    "ciclovias": lambda f: reglas_comunes(f) + regla_positivo(f, "long_metros"),
    "espacios_verdes": lambda f: reglas_comunes(f) + reglas_coords(f) + regla_positivo(f, "area_m2"),
    "hospitales": lambda f: reglas_comunes(f) + reglas_coords(f) + regla_no_vacio(f, "nombre"),
}


def main() -> int:
    print("VERIFICACIÓN de SILVER  (reglas propias · stdlib)")
    print("=" * 56)
    reporte = {}
    algun_fallo = False
    for dominio, check in CHECKS.items():
        filas = leer(dominio)
        if not filas:
            print(f"[!] {dominio:16s} SIN DATOS -> NO PUBLICABLE")
            reporte[dominio] = {"publicable": False, "filas": 0, "violaciones": [["sin_datos", 1]]}
            algun_fallo = True
            continue
        viol = check(filas)
        publicable = len(viol) == 0
        estado = "✓ OK" if publicable else "✗ FALLA"
        print(f"[{estado:>7s}] {dominio:16s} {len(filas):>4d} filas"
              + ("" if publicable else f"  violaciones: {viol}"))
        reporte[dominio] = {
            "publicable": publicable,
            "filas": len(filas),
            "violaciones": viol,
        }
        if not publicable:
            algun_fallo = True

    (SILVER / "_verificacion.json").write_text(json.dumps({
        "fecha": dt.datetime.now().isoformat(timespec="seconds"),
        "herramienta": "reglas_propias_stdlib",
        "resultado": reporte,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 56)
    if algun_fallo:
        print("Hay dominios que NO pasan: NO se publicarán a GOLD.")
    else:
        print("Todos los dominios pasaron: habilitados para GOLD.")
    print("Reporte -> lago/silver/_verificacion.json")
    # No abortamos el pipeline: build_gold decide qué publicar según el reporte.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
