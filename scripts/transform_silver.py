#!/usr/bin/env python3
"""Limpia un lote BRONZE trazable y reemplaza SILVER como una unidad.

Los sidecars son obligatorios y su SHA-256 debe coincidir con el archivo. Una fuente
faltante, un contrato de columnas incompatible o una procedencia inválida cancela toda
la transformación; no se reutilizan salidas SILVER antiguas.
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import json
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from pipeline_common import RAW, REQUIRED_DOMAINS, ROOT, SILVER, atomic_write_text, replace_directory, sha256_file

LAT_MIN, LAT_MAX = -34.71, -34.52
LON_MIN, LON_MAX = -58.54, -58.33
COMUNA_MIN, COMUNA_MAX = 1, 15
REQUIRED_META = {"dominio", "fuente", "organismo", "url", "licencia", "formato",
                 "fecha_ingesta", "_origen", "run_id", "sha256"}

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAVE_PARQUET = True
except ImportError:
    HAVE_PARQUET = False


def _norm_str(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _title(value: str) -> str:
    return _norm_str(value).title()


def _to_int(value):
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def _to_float(value):
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def _ultimo_raw(dominio: str, extension: str = "csv") -> Path:
    runs_dir = RAW / "runs"
    if runs_dir.exists():
        for run_dir in sorted((path for path in runs_dir.iterdir() if path.is_dir()), reverse=True):
            manifest_path = run_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("complete") and set(REQUIRED_DOMAINS).issubset(manifest.get("domains", [])):
                candidate = run_dir / dominio / f"{manifest['run_id']}.{extension}"
                if candidate.exists():
                    return candidate
    archivos = sorted(glob.glob(str(RAW / dominio / f"*.{extension}")))
    if not archivos:
        raise FileNotFoundError(f"no hay BRONZE {extension} para {dominio} en {RAW}")
    return Path(archivos[-1])


def _meta_raw(archivo: Path, dominio: str) -> dict:
    sidecar = archivo.with_suffix(archivo.suffix + ".meta.json")
    if not sidecar.exists():
        raise ValueError(f"falta sidecar obligatorio: {sidecar}")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    missing = sorted(REQUIRED_META - set(metadata))
    if missing:
        raise ValueError(f"sidecar incompleto de {dominio}; faltan {missing}")
    if metadata["dominio"] != dominio or metadata["formato"] != archivo.suffix.lstrip("."):
        raise ValueError(f"sidecar no corresponde al archivo {archivo.name}")
    actual_hash = sha256_file(archivo)
    if metadata["sha256"] != actual_hash:
        raise ValueError(f"SHA-256 no coincide para {archivo.name}")
    return metadata


def _coord_ok(lat, lon) -> bool:
    return (lat is not None and lon is not None
            and LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX)


def limpiar_csv_generico(archivo: Path, mapping: dict[str, str], coords: bool = True,
                         num_cols: dict[str, str] | None = None):
    num_cols = num_cols or {}
    filas: list[dict] = []
    vistos = set()
    rechazos: Counter[str] = Counter()
    input_rows = 0

    with archivo.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = sorted(set(mapping.values()) - set(reader.fieldnames or ()))
        if missing:
            raise ValueError(f"{archivo.name}: faltan columnas requeridas {missing}")
        for row in reader:
            input_rows += 1
            out = {}
            for destination, source in mapping.items():
                value = row.get(source, "")
                if destination in num_cols:
                    out[destination] = (_to_int(value) if num_cols[destination] == "int"
                                        else _to_float(value))
                else:
                    out[destination] = _title(value) if destination == "nombre" else _norm_str(value)

            if out.get("id") is None:
                rechazos["id_invalido"] += 1
                continue
            if out.get("comuna") is None or not (COMUNA_MIN <= out["comuna"] <= COMUNA_MAX):
                rechazos["comuna_fuera_de_rango"] += 1
                continue
            if coords and not _coord_ok(out.get("lat"), out.get("lon")):
                rechazos["coordenadas_fuera_de_caba"] += 1
                continue
            if out["id"] in vistos:
                rechazos["id_duplicado"] += 1
                continue
            vistos.add(out["id"])
            filas.append(out)
    return filas, dict(rechazos), input_rows


def dom_ecobici(archivo):
    return limpiar_csv_generico(
        archivo,
        {"id": "id", "nombre": "nombre", "comuna": "comuna", "lat": "lat",
         "lon": "long", "anclajes_totales": "anclajes_totales"},
        num_cols={"id": "int", "comuna": "int", "lat": "float", "lon": "float",
                  "anclajes_totales": "int"},
    )


def dom_ciclovias(archivo):
    return limpiar_csv_generico(
        archivo,
        {"id": "id", "nombre": "nombre", "comuna": "comuna",
         "long_metros": "long_metros", "tipo": "tipo"},
        coords=False,
        num_cols={"id": "int", "comuna": "int", "long_metros": "float"},
    )


def dom_espacios_verdes(archivo):
    return limpiar_csv_generico(
        archivo,
        {"id": "id", "nombre": "nombre", "comuna": "comuna", "area_m2": "area_m2",
         "clasificacion": "clasificacion", "lat": "lat", "lon": "lon"},
        num_cols={"id": "int", "comuna": "int", "area_m2": "float",
                  "lat": "float", "lon": "float"},
    )


def dom_hospitales(archivo):
    return limpiar_csv_generico(
        archivo,
        {"id": "id", "nombre": "nombre", "tipo": "tipo", "comuna": "comuna",
         "direccion": "direccion", "lat": "lat", "lon": "lon"},
        num_cols={"id": "int", "comuna": "int", "lat": "float", "lon": "float"},
    )


SCHEMAS = {
    "ecobici": [("id", "INT64"), ("nombre", "UTF8"), ("comuna", "INT64"),
                ("lat", "DOUBLE"), ("lon", "DOUBLE"), ("anclajes_totales", "INT64")],
    "ciclovias": [("id", "INT64"), ("nombre", "UTF8"), ("comuna", "INT64"),
                  ("long_metros", "DOUBLE"), ("tipo", "UTF8")],
    "espacios_verdes": [("id", "INT64"), ("nombre", "UTF8"), ("comuna", "INT64"),
                        ("area_m2", "DOUBLE"), ("clasificacion", "UTF8"),
                        ("lat", "DOUBLE"), ("lon", "DOUBLE")],
    "hospitales": [("id", "INT64"), ("nombre", "UTF8"), ("tipo", "UTF8"),
                   ("comuna", "INT64"), ("direccion", "UTF8"),
                   ("lat", "DOUBLE"), ("lon", "DOUBLE")],
}
LIMPIADORES = {
    "ecobici": dom_ecobici,
    "ciclovias": dom_ciclovias,
    "espacios_verdes": dom_espacios_verdes,
    "hospitales": dom_hospitales,
}


def escribir_silver(output: Path, dominio: str, filas: list[dict], schema,
                     metadata: dict, rechazos: dict[str, int], input_rows: int,
                     raw_file: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    columns = [column for column, _ in schema]
    csv_path = output / f"{dominio}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({column: row.get(column) for column in columns} for row in filas)

    parquet_ok = False
    if HAVE_PARQUET:
        arrays = {}
        for column, data_type in schema:
            values = [row.get(column) for row in filas]
            arrow_type = pa.int64() if data_type == "INT64" else (
                pa.float64() if data_type == "DOUBLE" else pa.string()
            )
            arrays[column] = pa.array(values, type=arrow_type)
        pq.write_table(pa.table(arrays), output / f"{dominio}.parquet", compression="snappy")
        parquet_ok = True

    discarded = sum(rechazos.values())
    silver_meta = {
        "dominio": dominio,
        "fuente": metadata["fuente"],
        "organismo": metadata["organismo"],
        "url": metadata["url"],
        "licencia": metadata["licencia"],
        "_origen": metadata["_origen"],
        "run_id": metadata["run_id"],
        "raw_file": str(raw_file),
        "raw_sha256": metadata["sha256"],
        "fecha_ingesta": metadata["fecha_ingesta"],
        "source_updated_at": metadata.get("source_updated_at"),
        "fecha_transformacion": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "filas_entrada": input_rows,
        "filas_salida": len(filas),
        "filas_descartadas": discarded,
        "rechazos_por_regla": rechazos,
        "silver_sha256": sha256_file(csv_path),
        "formato_parquet": parquet_ok,
    }
    atomic_write_text(output / f"{dominio}.meta.json",
                      json.dumps(silver_meta, ensure_ascii=False, indent=2))
    print(f"[ok] {dominio:16s} {len(filas):>4d}/{input_rows} filas; "
          f"{discarded} en cuarentena lógica")


def main() -> int:
    print(f"Limpieza BRONZE -> SILVER · {RAW} -> {SILVER}")
    SILVER.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".silver-staging-", dir=SILVER.parent))
    try:
        inputs = {}
        for dominio in REQUIRED_DOMAINS:
            raw_file = _ultimo_raw(dominio)
            inputs[dominio] = (raw_file, _meta_raw(raw_file, dominio))
        run_ids = {metadata["run_id"] for _, metadata in inputs.values()}
        origins = {metadata["_origen"] for _, metadata in inputs.values()}
        if len(run_ids) != 1 or len(origins) != 1:
            raise ValueError("BRONZE mezcla corridas o procedencias")

        for dominio in REQUIRED_DOMAINS:
            raw_file, metadata = inputs[dominio]
            filas, rechazos, input_rows = LIMPIADORES[dominio](raw_file)
            if not filas:
                raise ValueError(f"{dominio}: ninguna fila válida")
            escribir_silver(staging, dominio, filas, SCHEMAS[dominio], metadata,
                            rechazos, input_rows, raw_file)
        replace_directory(staging, SILVER)
    except Exception as error:
        shutil.rmtree(staging, ignore_errors=True)
        print(f"[FALLO] SILVER no fue reemplazado: {error}")
        return 1

    output_format = "Parquet + CSV" if HAVE_PARQUET else "CSV (pyarrow no disponible)"
    print(f"[ok] lote SILVER completo: {len(REQUIRED_DOMAINS)} dominios · {output_format}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
