#!/usr/bin/env python3
"""Verifica SILVER y bloquea la publicación completa si un dominio falla."""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

from pipeline_common import REQUIRED_DOMAINS, SILVER, atomic_write_text, sha256_file

LAT_MIN, LAT_MAX = -34.71, -34.52
LON_MIN, LON_MAX = -58.54, -58.33
MAX_REJECTION_RATE = 0.10


def leer(dominio: str) -> list[dict]:
    path = SILVER / f"{dominio}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _num(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def reglas_comunes(filas):
    violations = []
    ids = [row.get("id") for row in filas]
    if any(identifier in (None, "") for identifier in ids):
        violations.append(("id_no_nulo", sum(1 for identifier in ids if identifier in (None, ""))))
    if len(ids) != len(set(ids)):
        violations.append(("id_unico", len(ids) - len(set(ids))))
    outside = sum(1 for row in filas if _num(row.get("comuna")) is None
                  or not (1 <= _num(row.get("comuna")) <= 15))
    if outside:
        violations.append(("comuna_1_15", outside))
    return violations


def reglas_coords(filas):
    def invalid(row):
        lat, lon = _num(row.get("lat")), _num(row.get("lon"))
        return (lat is None or lon is None or not (LAT_MIN <= lat <= LAT_MAX)
                or not (LON_MIN <= lon <= LON_MAX))
    count = sum(1 for row in filas if invalid(row))
    return [("coords_caba", count)] if count else []


def regla_positivo(filas, column):
    count = sum(1 for row in filas if (_num(row.get(column)) or 0) <= 0)
    return [(f"{column}_positivo", count)] if count else []


def regla_no_vacio(filas, column):
    count = sum(1 for row in filas if not (row.get(column) or "").strip())
    return [(f"{column}_no_vacio", count)] if count else []


CHECKS = {
    "ecobici": lambda rows: reglas_comunes(rows) + reglas_coords(rows)
    + regla_positivo(rows, "anclajes_totales"),
    "ciclovias": lambda rows: reglas_comunes(rows) + regla_positivo(rows, "long_metros"),
    "espacios_verdes": lambda rows: reglas_comunes(rows) + reglas_coords(rows)
    + regla_positivo(rows, "area_m2"),
    "hospitales": lambda rows: reglas_comunes(rows) + reglas_coords(rows)
    + regla_no_vacio(rows, "nombre"),
}


def _metadata_violations(dominio: str, csv_path: Path) -> tuple[list[tuple[str, int]], dict]:
    meta_path = SILVER / f"{dominio}.meta.json"
    if not meta_path.exists():
        return [("metadata_ausente", 1)], {}
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [("metadata_invalida", 1)], {}

    violations = []
    if metadata.get("silver_sha256") != sha256_file(csv_path):
        violations.append(("silver_sha256_no_coincide", 1))
    input_rows = int(metadata.get("filas_entrada") or 0)
    discarded = int(metadata.get("filas_descartadas") or 0)
    rejection_rate = discarded / input_rows if input_rows else 1.0
    if rejection_rate > MAX_REJECTION_RATE:
        violations.append(("tasa_rechazo_mayor_10pct", discarded))
    if metadata.get("_origen") not in {"semilla_demo", "descarga_oficial"}:
        violations.append(("procedencia_desconocida", 1))
    return violations, metadata


def main() -> int:
    print("VERIFICACIÓN ATÓMICA de SILVER")
    print("=" * 64)
    report = {}
    origins, run_ids = set(), set()
    has_failure = False

    for domain in REQUIRED_DOMAINS:
        csv_path = SILVER / f"{domain}.csv"
        rows = leer(domain)
        violations: list[tuple[str, int]] = []
        metadata = {}
        if not rows:
            violations.append(("sin_datos", 1))
        elif not csv_path.exists():
            violations.append(("archivo_ausente", 1))
        else:
            violations.extend(CHECKS[domain](rows))
            meta_violations, metadata = _metadata_violations(domain, csv_path)
            violations.extend(meta_violations)

        if metadata:
            origins.add(metadata.get("_origen"))
            run_ids.add(metadata.get("run_id"))
        publishable = not violations
        has_failure = has_failure or not publishable
        report[domain] = {
            "publicable": publishable,
            "filas": len(rows),
            "sha256": sha256_file(csv_path) if csv_path.exists() else None,
            "meta_sha256": sha256_file(SILVER / f"{domain}.meta.json")
            if (SILVER / f"{domain}.meta.json").exists() else None,
            "run_id": metadata.get("run_id"),
            "_origen": metadata.get("_origen"),
            "violaciones": violations,
        }
        status = "✓ OK" if publishable else "✗ FALLA"
        print(f"[{status:>7s}] {domain:16s} {len(rows):>4d} filas"
              + ("" if publishable else f" · {violations}"))

    provenance = "unknown"
    if len(origins) == 1:
        provenance = "demo" if origins == {"semilla_demo"} else "official"
    elif len(origins) > 1:
        provenance = "mixed"
        has_failure = True
    if len(run_ids) != 1:
        has_failure = True

    quality_status = "failed" if has_failure else "verified"
    verification = {
        "fecha": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "herramienta": "reglas_propias_stdlib",
        "quality_status": quality_status,
        "provenance_status": provenance,
        "run_id": next(iter(run_ids)) if len(run_ids) == 1 else None,
        "resultado": report,
    }
    SILVER.mkdir(parents=True, exist_ok=True)
    atomic_write_text(SILVER / "_verificacion.json",
                      json.dumps(verification, ensure_ascii=False, indent=2))

    print("=" * 64)
    if has_failure:
        print("PUBLICACIÓN BLOQUEADA: el lote completo debe pasar y compartir procedencia/run_id.")
        return 1
    print(f"Lote habilitado para GOLD · calidad=verified · procedencia={provenance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
