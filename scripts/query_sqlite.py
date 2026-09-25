#!/usr/bin/env python3
"""
Tramo CONSULTA — Herramienta A: SQLite (stdlib).  Corre en el sandbox.

Responde las preguntas del sistema de información sobre lago/gold/cerebro.sqlite.
La variante DuckDB (misma intención, sobre Parquet) está en scripts/query_duckdb.py.

Uso:
    python scripts/query_sqlite.py
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "lago" / "gold" / "cerebro.sqlite"


def tabla(con, titulo, sql):
    print(f"\n### {titulo}")
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    print("  " + " | ".join(cols))
    for row in cur.fetchall():
        print("  " + " | ".join(str(x) for x in row))


def main() -> int:
    con = sqlite3.connect(DB)
    tabla(con, "Comunas con más estaciones Ecobici (top 5)",
          """SELECT CAST(comuna AS INT) comuna, COUNT(*) estaciones
             FROM ecobici GROUP BY comuna ORDER BY estaciones DESC LIMIT 5""")

    tabla(con, "Comuna con más espacios verdes (top 5)",
          """SELECT CAST(comuna AS INT) comuna, COUNT(*) espacios,
                    ROUND(SUM(CAST(area_m2 AS REAL))/10000.0, 1) hectareas
             FROM espacios_verdes GROUP BY comuna
             ORDER BY espacios DESC LIMIT 5""")

    tabla(con, "Hospitales por comuna (con al menos 1)",
          """SELECT CAST(comuna AS INT) comuna, COUNT(*) hospitales
             FROM hospitales GROUP BY comuna
             HAVING hospitales > 0 ORDER BY hospitales DESC""")

    tabla(con, "Km de ciclovías por comuna (top 5)",
          """SELECT CAST(comuna AS INT) comuna,
                    ROUND(SUM(CAST(long_metros AS REAL))/1000.0, 2) km
             FROM ciclovias GROUP BY comuna ORDER BY km DESC LIMIT 5""")

    # cruce: infraestructura total combinada por comuna
    tabla(con, "Índice simple de infraestructura por comuna (top 5)",
          """
          WITH e AS (SELECT CAST(comuna AS INT) c, COUNT(*) n FROM ecobici GROUP BY 1),
               v AS (SELECT CAST(comuna AS INT) c, COUNT(*) n FROM espacios_verdes GROUP BY 1),
               h AS (SELECT CAST(comuna AS INT) c, COUNT(*) n FROM hospitales GROUP BY 1)
          SELECT com.comuna,
                 COALESCE(e.n,0) ecobici,
                 COALESCE(v.n,0) verdes,
                 COALESCE(h.n,0) hosp,
                 COALESCE(e.n,0)+COALESCE(v.n,0)+COALESCE(h.n,0) total
          FROM comunas com
          LEFT JOIN e ON e.c=com.comuna
          LEFT JOIN v ON v.c=com.comuna
          LEFT JOIN h ON h.c=com.comuna
          ORDER BY total DESC LIMIT 5
          """)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
