#!/usr/bin/env python3
"""
Tramo LIMPIEZA — Herramienta B: Polars.  (documentada; requiere `pip install polars pyarrow`)

Hace EXACTAMENTE la misma limpieza de ecobici que transform_silver.py, pero con Polars,
para comparar sobre los mismos datos (requisito del taller). Ver bitácora para tiempos.

Ventaja de Polars vs stdlib: expresiones vectorizadas, lazy, y escritura Parquet nativa.
Ventaja de stdlib: cero dependencias, corre en cualquier lado (por eso es la elegida aquí).

Uso:
    python scripts/transform_silver_polars.py
"""
from __future__ import annotations
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "lago" / "raw"
SILVER = ROOT / "lago" / "silver"
LAT_MIN, LAT_MAX = -34.71, -34.52
LON_MIN, LON_MAX = -58.54, -58.33


def main() -> int:
    try:
        import polars as pl
    except ImportError:
        print("Polars no está instalado. `pip install polars pyarrow` para usar esta variante.",
              file=sys.stderr)
        return 1

    raw = sorted(glob.glob(str(RAW / "ecobici" / "*.csv")))[-1]
    df = (
        pl.read_csv(raw, infer_schema_length=1000)
        .rename({"long": "lon"})
        .with_columns([
            pl.col("nombre").str.strip_chars().str.replace_all(r"\s+", " "),
            pl.col("comuna").cast(pl.Int64, strict=False),
            pl.col("lat").cast(pl.Float64, strict=False),
            pl.col("lon").cast(pl.Float64, strict=False),
        ])
        .filter(
            pl.col("comuna").is_between(1, 15)
            & pl.col("lat").is_between(LAT_MIN, LAT_MAX)
            & pl.col("lon").is_between(LON_MIN, LON_MAX)
        )
        .unique(subset=["id"])
    )
    SILVER.mkdir(parents=True, exist_ok=True)
    df.write_parquet(SILVER / "ecobici_polars.parquet")
    print(f"[ok] Polars: {df.height} filas -> lago/silver/ecobici_polars.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
