#!/usr/bin/env python3
"""
Tramo LAKEHOUSE — demostración de VERSIONADO + VIAJE EN EL TIEMPO (time travel).

El taller pide comparar DOS herramientas de tabla abierta: DuckLake e Iceberg.
Ambas requieren dependencias que no están en este sandbox (ver scripts hermanos
lakehouse_ducklake.py y lakehouse_iceberg.py, listos para correr con internet).

Para que el CONCEPTO se pueda VER corrido aquí y ahora, reproducimos el mecanismo
esencial de un lakehouse —snapshots inmutables + consulta por versión— con SQLite,
que sí está disponible. Es el "lakehouse de bolsillo" del que habla el ejemplo Lima.

Escenario (igual al del profesor):
    Versión 1: N estaciones Ecobici
       ↓ actualización (se agregan estaciones nuevas)
    Versión 2: N+k estaciones
    → consultamos la versión anterior (time travel) y comparamos.

Uso:
    python scripts/lakehouse_timetravel.py
"""
from __future__ import annotations
import csv
import datetime as dt
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "lago" / "silver"
LH = ROOT / "lakehouse"
DB = LH / "ecobici_versionada.sqlite"


def _leer_ecobici():
    with (SILVER / "ecobici.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _crear(con):
    con.executescript("""
        DROP TABLE IF EXISTS snapshots;
        DROP TABLE IF EXISTS ecobici_versionada;
        CREATE TABLE snapshots (
            version   INTEGER PRIMARY KEY,
            creado_en TEXT,
            filas     INTEGER,
            comentario TEXT
        );
        CREATE TABLE ecobici_versionada (
            version INTEGER,
            id      INTEGER,
            nombre  TEXT,
            comuna  INTEGER,
            lat     REAL,
            lon     REAL
        );
    """)


def _insertar_version(con, version, filas, comentario):
    con.execute("INSERT INTO snapshots VALUES (?,?,?,?)",
                (version, dt.datetime.now().isoformat(timespec="seconds"),
                 len(filas), comentario))
    con.executemany(
        "INSERT INTO ecobici_versionada VALUES (?,?,?,?,?,?)",
        [(version, int(r["id"]), r["nombre"], int(r["comuna"]),
          float(r["lat"]), float(r["lon"])) for r in filas])
    con.commit()


def _contar(con, version):
    return con.execute(
        "SELECT COUNT(*) FROM ecobici_versionada WHERE version=?", (version,)
    ).fetchone()[0]


def main() -> int:
    LH.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    _crear(con)

    base = _leer_ecobici()

    # ---- Versión 1: los primeros 100 registros ----
    v1 = base[:100]
    _insertar_version(con, 1, v1, "carga inicial")
    print(f"Versión 1 creada: {len(v1)} estaciones  (snapshot inmutable)")

    # ---- Versión 2: agregamos 5 estaciones nuevas (101..105) ----
    v2 = base[:105]
    _insertar_version(con, 2, v2, "se agregan 5 estaciones nuevas")
    print(f"Versión 2 creada: {len(v2)} estaciones")

    # ---- VIAJE EN EL TIEMPO: consultamos cada versión ----
    print("\n--- Time travel ---")
    print(f"  SELECT en versión 1  -> {_contar(con, 1)} estaciones")
    print(f"  SELECT en versión 2  -> {_contar(con, 2)} estaciones")
    print(f"  diferencia (v2 - v1) -> {_contar(con, 2) - _contar(con, 1)} estaciones nuevas")

    print("\n--- Snapshots registrados ---")
    for row in con.execute("SELECT version, creado_en, filas, comentario FROM snapshots"):
        print(f"  v{row[0]}  {row[1]}  {row[2]} filas  · {row[3]}")

    # qué estaciones aparecen sólo en v2 (equivalente a un diff entre snapshots)
    nuevas = con.execute("""
        SELECT id, nombre FROM ecobici_versionada WHERE version=2
        EXCEPT
        SELECT id, nombre FROM ecobici_versionada WHERE version=1
        ORDER BY id
    """).fetchall()
    print(f"\n--- Estaciones nuevas en v2 (diff) --- ({len(nuevas)})")
    for id_, nombre in nuevas:
        print(f"  #{id_}  {nombre}")

    con.close()
    print(f"\n[ok] Lakehouse de bolsillo en {DB.relative_to(ROOT)}")
    print("     Concepto idéntico a DuckLake/Iceberg: snapshots + consulta por versión.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
