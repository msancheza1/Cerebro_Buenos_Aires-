#!/usr/bin/env python3
"""
Tramo LIMPIEZA — BRONZE (lago/raw) -> SILVER (lago/silver).

Herramienta A (esta): Python biblioteca estándar (csv/json).  <- corre en el sandbox
Herramienta B: Polars (scripts/transform_silver_polars.py)     <- documentada
Alternativa clásica: Pandas (mismo resultado; ver bitácora).

Qué hace la limpieza (igual para todos los dominios):
  - normaliza nombres de columnas y strings (trim, colapsa espacios, Title Case)
  - castea tipos (comuna -> int, coords/area/metros -> float)
  - valida rango de coordenadas de CABA y comuna 1..15; marca filas inválidas
  - descarta duplicados por id
  - agrega columnas de trazabilidad: _fuente, _url, _licencia, _fecha_ingesta, _origen

SALIDA:
  - lago/silver/<dominio>.csv           (siempre; verificable sin dependencias)
  - lago/silver/<dominio>.parquet       (SOLO si pyarrow está disponible)
  - lago/silver/<dominio>.meta.json     (fuente, filas_in/out, descartadas, fecha)

Uso:
    python scripts/transform_silver.py
"""
from __future__ import annotations
import _utf8  # noqa: F401  (reconfigura stdout/stderr a UTF-8; portabilidad Windows)
import csv
import datetime as dt
import glob
import json
import re
import sys
from pathlib import Path

# datasets reales traen columnas 'geometry' (WKT de polígonos) que superan el
# límite por defecto de campo CSV (128 KB). Lo subimos para poder leerlas.
csv.field_size_limit(10 * 1024 * 1024)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "lago" / "raw"
SILVER = ROOT / "lago" / "silver"

# rangos válidos de CABA
LAT_MIN, LAT_MAX = -34.71, -34.52
LON_MIN, LON_MAX = -58.54, -58.33
COMUNA_MIN, COMUNA_MAX = 1, 15

try:
    import pyarrow  # noqa
    import pyarrow.csv  # noqa
    HAVE_PARQUET = True
except Exception:
    HAVE_PARQUET = False


def _norm_str(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _title(s: str) -> str:
    return _norm_str(s).title()


def _to_int(v):
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return None


def _to_float(v):
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def _ultimo_raw(dominio: str, ext: str) -> Path | None:
    archivos = sorted(glob.glob(str(RAW / dominio / f"*.{ext}")))
    return Path(archivos[-1]) if archivos else None


def _meta_raw(archivo: Path) -> dict:
    m = archivo.with_suffix(archivo.suffix + ".meta.json")
    return json.loads(m.read_text(encoding="utf-8")) if m.exists() else {}


def _coord_ok(lat, lon) -> bool:
    return (lat is not None and lon is not None
            and LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX)


# --- limpiadores por dominio: devuelven (filas_limpias, schema, descartadas) ---

def limpiar_csv_generico(archivo, mapping, coords=True, num_cols=None,
                         derivar_comuna=None, auto_id=False):
    """mapping: {col_salida: col_entrada}. num_cols: {col: 'int'|'float'}.

    derivar_comuna: LocalizadorComunas opcional. Si el raw NO trae comuna válida
      pero sí lat/lon, se asigna la comuna por punto-en-polígono (unión espacial).
    auto_id: si True y el id del raw viene vacío/duplicado, se genera uno incremental.
    """
    num_cols = num_cols or {}
    filas, vistos, descartadas = [], set(), 0
    contador_id = 0
    with archivo.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out = {}
            for dst, src in mapping.items():
                val = row.get(src, "")
                if dst in num_cols:
                    out[dst] = _to_int(val) if num_cols[dst] == "int" else _to_float(val)
                else:
                    out[dst] = _title(val) if dst == "nombre" else _norm_str(val)

            # derivar comuna por coordenadas si falta y hay localizador
            if (derivar_comuna is not None and
                    (out.get("comuna") is None or
                     not (COMUNA_MIN <= (out.get("comuna") or 0) <= COMUNA_MAX))):
                c = derivar_comuna.comuna_de(out.get("lon"), out.get("lat"))
                if c is not None:
                    out["comuna"] = c

            # comuna válida
            if "comuna" in out and (out["comuna"] is None
                                    or not (COMUNA_MIN <= out["comuna"] <= COMUNA_MAX)):
                descartadas += 1
                continue
            # coordenadas válidas (si aplica)
            if coords and not _coord_ok(out.get("lat"), out.get("lon")):
                descartadas += 1
                continue
            # id: auto-incremental si hace falta
            if auto_id and (out.get("id") is None or out.get("id") in vistos):
                contador_id += 1
                out["id"] = contador_id
            rid = out.get("id")
            if rid in vistos:
                descartadas += 1
                continue
            vistos.add(rid)
            filas.append(out)
    return filas, descartadas


def _localizador():
    """LocalizadorComunas desde el geojson de comunas (gold o raw)."""
    from geo import LocalizadorComunas
    for cand in (ROOT / "lago" / "gold" / "comunas.geojson",):
        if cand.exists():
            loc = LocalizadorComunas(cand)
            if loc.disponible():
                return loc
    # fallback: último geojson de raw/comunas
    import glob as _glob
    gjs = sorted(p for p in _glob.glob(str(RAW / "comunas" / "*.geojson"))
                 if not Path(p).name.startswith("_"))
    if gjs:
        loc = LocalizadorComunas(Path(gjs[-1]))
        return loc if loc.disponible() else None
    return None


def dom_ecobici(archivo):
    # Real BA Data: id, nombre, comuna(vacía), latitud, longitud.
    # La comuna viene vacía -> se deriva por punto-en-polígono con el geojson.
    return limpiar_csv_generico(
        archivo,
        mapping={"id": "id", "nombre": "nombre", "comuna": "comuna",
                 "lat": "latitud", "lon": "longitud"},
        coords=True,
        num_cols={"id": "int", "comuna": "int", "lat": "float", "lon": "float"},
        derivar_comuna=_localizador(),
        auto_id=True,
    )


def dom_ciclovias(archivo):
    # Real: id, nombre, tipo, comuna, longitud_m, geometry. Sin coords puntuales.
    return limpiar_csv_generico(
        archivo,
        mapping={"id": "id", "nombre": "nombre", "comuna": "comuna",
                 "long_metros": "longitud_m", "tipo": "tipo"},
        coords=False,
        num_cols={"id": "int", "comuna": "int", "long_metros": "float"},
        auto_id=True,
    )


def dom_espacios_verdes(archivo):
    # Real: id, nombre, comuna, clasificac, area, geometry. Sin lat/lon puntual.
    return limpiar_csv_generico(
        archivo,
        mapping={"id": "id", "nombre": "nombre", "comuna": "comuna",
                 "area_m2": "area", "clasificacion": "clasificac"},
        coords=False,
        num_cols={"id": "int", "comuna": "int", "area_m2": "float"},
        auto_id=True,
    )


def dom_hospitales(archivo):
    # Real: nam(nombre), esp(tipo), com(comuna), dir(direccion), geometry(proyectada).
    # No hay lat/lon WGS84 -> no validamos coords; dejamos lat/lon vacíos.
    return limpiar_csv_generico(
        archivo,
        mapping={"id": "id", "nombre": "nam", "tipo": "esp", "comuna": "com",
                 "direccion": "dir"},
        coords=False,
        num_cols={"id": "int", "comuna": "int"},
        auto_id=True,
    )


SCHEMAS = {
    "ecobici": [("id", "INT64"), ("nombre", "UTF8"), ("comuna", "INT64"),
                ("lat", "DOUBLE"), ("lon", "DOUBLE")],
    "ciclovias": [("id", "INT64"), ("nombre", "UTF8"), ("comuna", "INT64"),
                  ("long_metros", "DOUBLE"), ("tipo", "UTF8")],
    "espacios_verdes": [("id", "INT64"), ("nombre", "UTF8"), ("comuna", "INT64"),
                        ("area_m2", "DOUBLE"), ("clasificacion", "UTF8")],
    "hospitales": [("id", "INT64"), ("nombre", "UTF8"), ("tipo", "UTF8"),
                   ("comuna", "INT64"), ("direccion", "UTF8")],
}
LIMPIADORES = {
    "ecobici": dom_ecobici,
    "ciclovias": dom_ciclovias,
    "espacios_verdes": dom_espacios_verdes,
    "hospitales": dom_hospitales,
}


def escribir_silver(dominio, filas, schema, meta_raw, descartadas, raw_file):
    SILVER.mkdir(parents=True, exist_ok=True)
    cols = [c for c, _ in schema]

    # CSV (siempre)
    csv_path = SILVER / f"{dominio}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in filas:
            w.writerow({c: r.get(c) for c in cols})

    # Parquet (si hay pyarrow)
    parquet_ok = False
    if HAVE_PARQUET:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            arrays = {}
            for c, t in schema:
                vals = [r.get(c) for r in filas]
                if t == "INT64":
                    arrays[c] = pa.array(vals, type=pa.int64())
                elif t == "DOUBLE":
                    arrays[c] = pa.array(vals, type=pa.float64())
                else:
                    arrays[c] = pa.array([("" if v is None else str(v)) for v in vals],
                                         type=pa.string())
            table = pa.table(arrays)
            pq.write_table(table, SILVER / f"{dominio}.parquet", compression="snappy")
            parquet_ok = True
        except Exception as e:
            print(f"    [!] Parquet falló para {dominio}: {e}", file=sys.stderr)

    (SILVER / f"{dominio}.meta.json").write_text(json.dumps({
        "dominio": dominio,
        "fuente": meta_raw.get("fuente", "Buenos Aires Data"),
        "organismo": meta_raw.get("organismo", ""),
        "url": meta_raw.get("url", ""),
        "licencia": meta_raw.get("licencia", "CC-BY"),
        "_origen": meta_raw.get("_origen", "descarga"),
        "raw_file": str(raw_file.relative_to(ROOT)),
        "fecha_transformacion": dt.datetime.now().isoformat(timespec="seconds"),
        "filas_salida": len(filas),
        "filas_descartadas": descartadas,
        "formato_parquet": parquet_ok,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    marca = "parquet+csv" if parquet_ok else "csv (sin pyarrow)"
    print(f"[ok] {dominio:16s} {len(filas):>4d} filas  ({descartadas} descartadas)  -> {marca}")


def main() -> int:
    print("Limpieza BRONZE -> SILVER  (Python stdlib)")
    if not HAVE_PARQUET:
        print("  (pyarrow no disponible: escribo SILVER en CSV. Con pyarrow -> Parquet snappy.)")
    total = 0
    for dominio, limpiador in LIMPIADORES.items():
        raw_file = _ultimo_raw(dominio, "csv")
        if not raw_file:
            print(f"[!] sin raw para {dominio}", file=sys.stderr)
            continue
        filas, descartadas = limpiador(raw_file)
        escribir_silver(dominio, filas, SCHEMAS[dominio], _meta_raw(raw_file),
                        descartadas, raw_file)
        total += 1
    print(f"\n{total} dominios transformados a SILVER.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
