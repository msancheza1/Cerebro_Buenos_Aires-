#!/usr/bin/env python3
"""
Tramo VERIFICACIÓN — Herramienta B: Pandera.  (documentada; `pip install pandera pandas`)

Mismas reglas que verify.py pero declaradas como esquema Pandera sobre el dominio
ecobici, para comparar sobre los mismos datos (requisito del taller).

Por qué Pandera y no Great Expectations (bitácora):
  - Pandera: esquema como código, liviano, se integra en el script de pipeline y en tests.
  - Great Expectations: más potente (data docs, checkpoints) pero pesado de configurar
    para un MVP de 4 datasets; overkill acá.

Uso:
    python scripts/verify_pandera.py
"""
from __future__ import annotations
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "lago" / "silver"


def main() -> int:
    try:
        import pandas as pd
        import pandera as pa
        from pandera import Column, Check, DataFrameSchema
    except ImportError:
        print("Pandera/pandas no instalados. `pip install pandera pandas`.", file=sys.stderr)
        return 1

    esquema = DataFrameSchema({
        "id": Column(int, unique=True, nullable=False),
        "nombre": Column(str, Check.str_length(min_value=1)),
        "comuna": Column(int, Check.in_range(1, 15)),
        "lat": Column(float, Check.in_range(-34.71, -34.52)),
        "lon": Column(float, Check.in_range(-58.54, -58.33)),
        "anclajes_totales": Column(int, Check.greater_than(0)),
    })

    df = pd.read_csv(SILVER / "ecobici.csv")
    try:
        esquema.validate(df, lazy=True)
        print(f"[✓ OK] ecobici: {len(df)} filas pasan el esquema Pandera.")
        return 0
    except pa.errors.SchemaErrors as e:
        print("[✗ FALLA] ecobici no pasa Pandera:")
        print(e.failure_cases.head(20).to_string())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
