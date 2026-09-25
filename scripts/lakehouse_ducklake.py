#!/usr/bin/env python3
"""
Tramo LAKEHOUSE — Herramienta A: DuckLake.  (documentada; `pip install duckdb`, ext ducklake)

DuckLake (DuckDB Labs, versión estable 13 abr 2026) guarda el CATÁLOGO en una base SQL
y los DATOS en Parquet. Time travel vía snapshots.

Requiere DuckDB con la extensión ducklake. Uso:
    python scripts/lakehouse_ducklake.py
"""
from __future__ import annotations
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "lago" / "silver"
LH = ROOT / "lakehouse"


def main() -> int:
    try:
        import duckdb
    except ImportError:
        print("DuckDB no instalado. `pip install duckdb`.", file=sys.stderr)
        return 1
    LH.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL ducklake; LOAD ducklake;")
    # catálogo en SQLite, datos Parquet en lakehouse/ducklake_data
    con.execute(f"""
        ATTACH 'ducklake:{LH / 'catalog.ducklake'}' AS lh
        (DATA_PATH '{LH / 'ducklake_data'}');
    """)
    src = SILVER / "ecobici.csv"

    # Versión 1: primeras 100
    con.execute("CREATE OR REPLACE TABLE lh.ecobici AS "
                f"SELECT * FROM read_csv_auto('{src}') LIMIT 100")
    print("v1:", con.sql("SELECT COUNT(*) FROM lh.ecobici").fetchone()[0], "estaciones")

    # Versión 2: agregamos 5 (filas 101..105)
    con.execute(f"""
        INSERT INTO lh.ecobici
        SELECT * FROM read_csv_auto('{src}') LIMIT 5 OFFSET 100
    """)
    print("v2:", con.sql("SELECT COUNT(*) FROM lh.ecobici").fetchone()[0], "estaciones")

    # time travel: listar snapshots y consultar la versión anterior
    print("\nSnapshots:")
    print(con.sql("SELECT * FROM lh.snapshots()"))
    print("\nConsulta de la versión 1 (time travel):")
    print(con.sql("SELECT COUNT(*) FROM lh.ecobici AT (VERSION => 1)"))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
