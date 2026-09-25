#!/usr/bin/env python3
"""
Tramo LAKEHOUSE — Herramienta B: Apache Iceberg (local, sin servicios).
(documentada; `pip install pyiceberg pyarrow`)

Iceberg es el formato de tabla abierto que los grandes adoptaron como común
(ver bitácora / línea de tiempo). Acá lo usamos con un catálogo SQLite local y
almacenamiento en el filesystem, para ver snapshots y time travel sin nube.

Requiere pyiceberg + pyarrow. Uso:
    python scripts/lakehouse_iceberg.py
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "lago" / "silver"
LH = ROOT / "lakehouse" / "iceberg_warehouse"


def main() -> int:
    try:
        import pyarrow.csv as pacsv
        from pyiceberg.catalog.sql import SqlCatalog
    except ImportError:
        print("pyiceberg/pyarrow no instalados. `pip install pyiceberg pyarrow`.",
              file=sys.stderr)
        return 1

    LH.mkdir(parents=True, exist_ok=True)
    catalog = SqlCatalog("local", **{
        "uri": f"sqlite:///{LH / 'catalog.db'}",
        "warehouse": f"file://{LH}",
    })
    catalog.create_namespace_if_not_exists("cerebro")

    tabla = pacsv.read_csv(SILVER / "ecobici.csv")

    # Versión 1: primeras 100 filas
    t = catalog.create_table_if_not_exists("cerebro.ecobici", schema=tabla.schema)
    t.overwrite(tabla.slice(0, 100))
    print("v1:", t.scan().to_arrow().num_rows, "estaciones")
    snap_v1 = t.current_snapshot().snapshot_id

    # Versión 2: agregamos 5 filas
    t.append(tabla.slice(100, 5))
    print("v2:", t.scan().to_arrow().num_rows, "estaciones")

    # time travel a la versión 1
    filas_v1 = t.scan(snapshot_id=snap_v1).to_arrow().num_rows
    print(f"\nTime travel a snapshot v1 ({snap_v1}): {filas_v1} estaciones")
    print("Snapshots:")
    for s in t.snapshots():
        print(f"  {s.snapshot_id}  {s.timestamp_ms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
