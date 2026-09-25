#!/usr/bin/env python3
"""
Tramo CONSULTA — Herramienta B: DuckDB.  (documentada; `pip install duckdb`)

Misma intención que query_sqlite.py, pero DuckDB lee Parquet directamente desde el lago
(lago/silver/*.parquet) sin cargar a una base, tal como plantea el ejemplo Cerebro Lima:
"una carpeta de JSON y Parquet con DuckDB encima".

Requiere que SILVER tenga .parquet (se genera cuando pyarrow está disponible en
transform_silver.py). Si solo hay CSV, DuckDB también lee CSV con read_csv_auto.

Uso:
    python scripts/query_duckdb.py
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "lago" / "silver"


def main() -> int:
    try:
        import duckdb
    except ImportError:
        print("DuckDB no instalado. `pip install duckdb`.", file=sys.stderr)
        return 1

    con = duckdb.connect()
    # DuckDB elige parquet si existe, si no CSV:
    def src(dominio):
        pq = SILVER / f"{dominio}.parquet"
        return f"read_parquet('{pq}')" if pq.exists() else \
               f"read_csv_auto('{SILVER / (dominio + '.csv')}')"

    print("### Comunas con más estaciones Ecobici (top 5) — DuckDB sobre Parquet")
    print(con.sql(f"""
        SELECT comuna, COUNT(*) AS estaciones
        FROM {src('ecobici')}
        GROUP BY comuna ORDER BY estaciones DESC LIMIT 5
    """))

    print("### Índice de infraestructura por comuna (top 5) — DuckDB")
    print(con.sql(f"""
        WITH e AS (SELECT comuna, COUNT(*) n FROM {src('ecobici')} GROUP BY comuna),
             v AS (SELECT comuna, COUNT(*) n FROM {src('espacios_verdes')} GROUP BY comuna),
             h AS (SELECT comuna, COUNT(*) n FROM {src('hospitales')} GROUP BY comuna)
        SELECT e.comuna,
               e.n AS ecobici, COALESCE(v.n,0) AS verdes, COALESCE(h.n,0) AS hosp,
               e.n + COALESCE(v.n,0) + COALESCE(h.n,0) AS total
        FROM e LEFT JOIN v USING(comuna) LEFT JOIN h USING(comuna)
        ORDER BY total DESC LIMIT 5
    """))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
