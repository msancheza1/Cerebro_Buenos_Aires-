#!/usr/bin/env python3
"""Construye GOLD sólo desde un lote SILVER completo, vigente y verificado."""
from __future__ import annotations

import csv
import datetime as dt
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from pipeline_common import GOLD, REQUIRED_DOMAINS, ROOT, SILVER, atomic_write_text, replace_directory, sha256_file

COMUNAS = tuple(range(1, 16))


def _verification() -> dict:
    path = SILVER / "_verificacion.json"
    if not path.exists():
        raise ValueError("falta _verificacion.json; ejecutá verify.py")
    verification = json.loads(path.read_text(encoding="utf-8"))
    if verification.get("quality_status") != "verified":
        raise ValueError("la verificación no habilitó este lote")
    results = verification.get("resultado", {})
    if set(results) != set(REQUIRED_DOMAINS):
        raise ValueError("el reporte no contiene exactamente todos los dominios requeridos")
    for domain in REQUIRED_DOMAINS:
        result = results[domain]
        silver_path = SILVER / f"{domain}.csv"
        if not result.get("publicable"):
            raise ValueError(f"{domain} no es publicable")
        meta_path = SILVER / f"{domain}.meta.json"
        if not silver_path.exists() or result.get("sha256") != sha256_file(silver_path):
            raise ValueError(f"{domain} cambió después de ser verificado")
        if not meta_path.exists() or result.get("meta_sha256") != sha256_file(meta_path):
            raise ValueError(f"la procedencia de {domain} cambió después de ser verificada")
    return verification


def _load_silver(connection: sqlite3.Connection, domain: str) -> None:
    if domain not in REQUIRED_DOMAINS:
        raise ValueError(f"dominio SQL no permitido: {domain}")
    path = SILVER / f"{domain}.csv"
    with path.open(encoding="utf-8") as stream:
        reader = csv.reader(stream)
        columns = next(reader)
        rows = list(reader)
    connection.execute(f"CREATE TABLE {domain} ({', '.join(column + ' TEXT' for column in columns)})")
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(f"INSERT INTO {domain} VALUES ({placeholders})", rows)


def _sources_meta(domains) -> dict:
    sources = {}
    for domain in domains:
        metadata = json.loads((SILVER / f"{domain}.meta.json").read_text(encoding="utf-8"))
        sources[domain] = {
            "fuente": metadata["fuente"],
            "organismo": metadata["organismo"],
            "url": metadata["url"],
            "licencia": metadata["licencia"],
            "_origen": metadata["_origen"],
            "run_id": metadata["run_id"],
            "raw_sha256": metadata["raw_sha256"],
            "fecha_ingesta": metadata["fecha_ingesta"],
            "source_updated_at": metadata.get("source_updated_at"),
        }
    return sources


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_into(output: Path, verification: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output / "cerebro.sqlite")
    try:
        for domain in REQUIRED_DOMAINS:
            _load_silver(connection, domain)
        connection.execute("CREATE TABLE comunas (comuna INTEGER PRIMARY KEY)")
        connection.executemany("INSERT INTO comunas VALUES (?)", [(value,) for value in COMUNAS])
        connection.commit()

        indicators = {}

        def aggregate(domain, expression, alias):
            query = (f"SELECT CAST(comuna AS INTEGER), {expression} FROM {domain} "
                     "GROUP BY CAST(comuna AS INTEGER)")
            indicators[alias] = {int(row[0]): row[1] for row in connection.execute(query)}

        aggregate("ecobici", "COUNT(*)", "estaciones_ecobici")
        aggregate("ciclovias", "ROUND(SUM(CAST(long_metros AS REAL))/1000.0, 2)", "km_ciclovias")
        aggregate("espacios_verdes", "COUNT(*)", "espacios_verdes")
        aggregate("espacios_verdes", "ROUND(SUM(CAST(area_m2 AS REAL)), 1)", "m2_espacios_verdes")
        aggregate("hospitales", "COUNT(*)", "hospitales")

        indicator_names = list(indicators)
        rows = [
            {"comuna": comuna, **{name: indicators[name].get(comuna, 0) for name in indicator_names}}
            for comuna in COMUNAS
        ]
        _write_csv(output / "indicadores_por_comuna.csv", ["comuna", *indicator_names], rows)
        for name in indicator_names:
            _write_csv(output / f"{name}.csv", ["comuna", name],
                       [{"comuna": comuna, name: indicators[name].get(comuna, 0)} for comuna in COMUNAS])

        provenance = verification["provenance_status"]
        metadata = {
            "generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "motor": "sqlite",
            "quality_status": "verified",
            "provenance_status": provenance,
            "datos_oficiales": provenance == "official",
            "estado": "verificado" if provenance == "official" else "demo_no_oficial",
            "run_id": verification["run_id"],
            "indicadores": indicator_names,
            "publicables": {domain: True for domain in REQUIRED_DOMAINS},
            "fuentes": _sources_meta(REQUIRED_DOMAINS),
        }
        atomic_write_text(output / "_meta.json", json.dumps(metadata, ensure_ascii=False, indent=2))
    finally:
        connection.close()


def main() -> int:
    try:
        verification = _verification()
    except (ValueError, json.JSONDecodeError) as error:
        print(f"[FALLO] GOLD no publicado: {error}")
        return 1

    GOLD.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".gold-staging-", dir=GOLD.parent))
    try:
        build_into(staging, verification)
        replace_directory(staging, GOLD)
    except Exception as error:
        shutil.rmtree(staging, ignore_errors=True)
        print(f"[FALLO] GOLD anterior conservado: {error}")
        return 1

    metadata = json.loads((GOLD / "_meta.json").read_text(encoding="utf-8"))
    print(f"[ok] GOLD atómico: {len(metadata['indicadores'])} indicadores × {len(COMUNAS)} comunas")
    print(f"     calidad={metadata['quality_status']} · procedencia={metadata['provenance_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
