#!/usr/bin/env python3
"""
Tramo GOBERNANZA — Perfilado y completitud de la capa SILVER.

Va más allá del pass/fail de verify.py: describe el ESTADO de los datos columna
por columna. Es el "profiling" clásico de un programa de calidad de datos.

Por cada columna de cada dominio calcula:
  - total de filas
  - no_nulos / nulos / % completitud
  - valores distintos (cardinalidad)
  - numéricas: min, max, media, desvío
  - detección simple de outliers por regla de rango del diccionario
    (coords fuera de CABA, comuna fuera de 1..15) → se reportan como "fuera_rango"

Salida:
  - imprime una tabla por dominio
  - escribe lago/silver/_perfilado.json  (consumible por el dashboard)

Uso:
    python scripts/profile_silver.py
"""
from __future__ import annotations
import _utf8  # noqa: F401  (reconfigura stdout/stderr a UTF-8; portabilidad Windows)
import csv
import datetime as dt
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "lago" / "silver"
CATALOGO = ROOT / "catalogo"

# rangos para outliers (coinciden con verify.py / diccionario.py)
LAT_MIN, LAT_MAX = -34.71, -34.52
LON_MIN, LON_MAX = -58.54, -58.33
COMUNA_MIN, COMUNA_MAX = 1, 15

RANGOS = {
    "lat": (LAT_MIN, LAT_MAX),
    "lon": (LON_MIN, LON_MAX),
    "comuna": (COMUNA_MIN, COMUNA_MAX),
}


def _cargar_diccionario() -> dict:
    p = CATALOGO / "diccionario_datos.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _leer(dominio: str) -> tuple[list[str], list[dict]]:
    p = SILVER / f"{dominio}.csv"
    if not p.exists():
        return [], []
    with p.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        filas = list(reader)
        cols = reader.fieldnames or []
    return cols, filas


def _num(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _es_vacio(v) -> bool:
    return v is None or str(v).strip() == ""


def perfilar_columna(col: str, valores: list, tipo: str) -> dict:
    total = len(valores)
    no_vacios = [v for v in valores if not _es_vacio(v)]
    n_no_nulos = len(no_vacios)
    n_nulos = total - n_no_nulos
    completitud = round(100.0 * n_no_nulos / total, 1) if total else 0.0
    distintos = len(set(str(v).strip() for v in no_vacios))

    perfil = {
        "tipo": tipo,
        "total": total,
        "no_nulos": n_no_nulos,
        "nulos": n_nulos,
        "completitud_pct": completitud,
        "distintos": distintos,
    }

    # estadísticos numéricos
    if tipo in ("entero", "decimal"):
        nums = [n for n in (_num(v) for v in no_vacios) if n is not None]
        if nums:
            media = sum(nums) / len(nums)
            if len(nums) > 1:
                var = sum((x - media) ** 2 for x in nums) / (len(nums) - 1)
                desvio = math.sqrt(var)
            else:
                desvio = 0.0
            perfil.update({
                "min": round(min(nums), 4),
                "max": round(max(nums), 4),
                "media": round(media, 4),
                "desvio": round(desvio, 4),
            })

    # outliers por rango conocido
    if col in RANGOS:
        lo, hi = RANGOS[col]
        fuera = sum(1 for v in no_vacios
                    if (_num(v) is None) or not (lo <= _num(v) <= hi))
        perfil["fuera_rango"] = fuera

    return perfil


def perfilar_dominio(dominio: str, dicc: dict) -> dict:
    cols, filas = _leer(dominio)
    if not filas:
        return {"filas": 0, "columnas": {}}
    tipos = {c: m["tipo"] for c, m in dicc.get(dominio, {}).get("columnas", {}).items()}
    perfil_cols = {}
    for c in cols:
        valores = [f.get(c) for f in filas]
        perfil_cols[c] = perfilar_columna(c, valores, tipos.get(c, "texto"))
    return {"filas": len(filas), "columnas": perfil_cols}


def _imprimir(dominio: str, info: dict) -> None:
    print(f"\n### {dominio}  ({info['filas']} filas)")
    enc = f"  {'columna':18s} {'tipo':8s} {'compl%':>7s} {'nulos':>6s} {'distintos':>10s} {'fuera_rango':>12s}"
    print(enc)
    print("  " + "-" * (len(enc) - 2))
    for col, p in info["columnas"].items():
        fr = p.get("fuera_rango", "")
        print(f"  {col:18s} {p['tipo']:8s} {p['completitud_pct']:>7.1f} "
              f"{p['nulos']:>6d} {p['distintos']:>10d} {str(fr):>12s}")


def main() -> int:
    dicc = _cargar_diccionario()
    if not dicc:
        print("[!] No existe catalogo/diccionario_datos.json. "
              "Corré scripts/diccionario.py primero.")
    print("PERFILADO de SILVER  (completitud · cardinalidad · rangos)")
    print("=" * 60)

    resultado = {}
    for dominio in ("ecobici", "ciclovias", "espacios_verdes", "hospitales"):
        info = perfilar_dominio(dominio, dicc)
        resultado[dominio] = info
        if info["filas"]:
            _imprimir(dominio, info)
        else:
            print(f"\n### {dominio}  — SIN DATOS")

    (SILVER / "_perfilado.json").write_text(json.dumps({
        "fecha": dt.datetime.now().isoformat(timespec="seconds"),
        "resultado": resultado,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("Perfilado -> lago/silver/_perfilado.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
