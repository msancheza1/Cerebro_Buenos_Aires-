#!/usr/bin/env python3
"""Descarga un lote BRONZE completo y lo promueve de forma atómica por recurso.

La ingesta falla cerrada: si una fuente no se descarga o no cumple el contrato mínimo,
ningún recurso del lote se promueve a ``lago/raw``. Nunca continúa con datos antiguos o
de demostración. Se puede comparar urllib (predeterminado) con curl usando ``--curl``.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from fuentes import FUENTES
from pipeline_common import (RAW, REQUIRED_DOMAINS, ROOT, atomic_write_bytes,
                             atomic_write_text, display_path, sha256_bytes)


def bajar_urllib(url: str, attempts: int = 3) -> tuple[bytes, dict[str, str]]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "cerebro-ba/2.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read(), {
                    "content_type": response.headers.get("Content-Type", ""),
                    "etag": response.headers.get("ETag", ""),
                    "source_updated_at": response.headers.get("Last-Modified", ""),
                    "final_url": response.geturl(),
                }
        except Exception as error:  # urllib expone varias subclases según el fallo de red
            last_error = error
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))
    assert last_error is not None
    raise last_error


def bajar_curl(url: str) -> tuple[bytes, dict[str, str]]:
    marker = b"\n__CEREBRO_EFFECTIVE_URL__:"
    result = subprocess.run(
        ["curl", "-sSL", "--fail", "--retry", "2", "--retry-all-errors",
         "-A", "cerebro-ba/2.0", "--write-out",
         "\\n__CEREBRO_EFFECTIVE_URL__:%{url_effective}", url],
        capture_output=True,
        check=True,
    )
    if marker not in result.stdout:
        raise ValueError("curl no informó la URL efectiva")
    content, effective_url = result.stdout.rsplit(marker, 1)
    return content, {"content_type": "", "etag": "", "source_updated_at": "",
                     "final_url": effective_url.decode("utf-8")}


def validar_url_oficial(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "data.buenosaires.gob.ar"
                                         or host.endswith(".buenosaires.gob.ar")):
        raise ValueError(f"redirección fuera de la allowlist oficial: {url}")


def validar_contenido(dominio: str, meta: dict, contenido: bytes) -> None:
    if len(contenido) < 20:
        raise ValueError("respuesta vacía o demasiado pequeña")
    formato = meta["formato"]
    if formato == "csv":
        try:
            text = contenido.decode("utf-8-sig")
            reader = csv.reader(io.StringIO(text))
            header = next(reader)
        except (UnicodeDecodeError, StopIteration, csv.Error) as error:
            raise ValueError(f"CSV ilegible: {error}") from error
        missing = sorted(set(meta.get("columnas_requeridas", ())) - set(header))
        if missing:
            raise ValueError(f"contrato de columnas incompatible; faltan {missing}")
        if next(reader, None) is None:
            raise ValueError("CSV sin filas de datos")
    elif formato == "geojson":
        try:
            document = json.loads(contenido)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"GeoJSON ilegible: {error}") from error
        if document.get("type") != "FeatureCollection" or not document.get("features"):
            raise ValueError("GeoJSON sin FeatureCollection o sin features")
    else:
        raise ValueError(f"formato no soportado: {formato}")


def preparar_recurso(dominio: str, meta: dict, usar_curl: bool, staging: Path,
                      run_id: str) -> tuple[Path, Path, int, float]:
    started = time.perf_counter()
    contenido, response_meta = bajar_curl(meta["url"]) if usar_curl else bajar_urllib(meta["url"])
    validar_url_oficial(response_meta["final_url"])
    validar_contenido(dominio, meta, contenido)
    elapsed_ms = (time.perf_counter() - started) * 1000

    extension = meta["formato"]
    data_path = staging / dominio / f"{run_id}.{extension}"
    sidecar_path = data_path.with_suffix(data_path.suffix + ".meta.json")
    atomic_write_bytes(data_path, contenido)
    metadata = {
        "dominio": dominio,
        "fuente": meta["fuente"],
        "organismo": meta["organismo"],
        "url": meta["url"],
        "final_url": response_meta["final_url"],
        "licencia": meta["licencia"],
        "formato": extension,
        "fecha_ingesta": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source_updated_at": response_meta["source_updated_at"] or None,
        "etag": response_meta["etag"] or None,
        "content_type": response_meta["content_type"] or None,
        "herramienta": "curl" if usar_curl else "urllib",
        "_origen": "descarga_oficial",
        "run_id": run_id,
        "bytes": len(contenido),
        "sha256": sha256_bytes(contenido),
    }
    atomic_write_text(sidecar_path, json.dumps(metadata, ensure_ascii=False, indent=2))
    return data_path, sidecar_path, len(contenido), elapsed_ms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingesta segura de recursos BA Data")
    parser.add_argument("dominios", nargs="*", metavar="DOMINIO",
                        help="dominios a descargar; por defecto, los usados por GOLD")
    parser.add_argument("--curl", action="store_true", help="usar curl en vez de urllib")
    args = parser.parse_args()
    unknown = sorted(set(args.dominios) - set(FUENTES))
    if unknown:
        parser.error(f"dominios desconocidos: {', '.join(unknown)}")
    return args


def main() -> int:
    args = parse_args()
    dominios = tuple(args.dominios) if args.dominios else REQUIRED_DOMAINS
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    staging_parent = RAW.parent / ".ingest-staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    prepared: list[tuple[str, Path, Path, int, float]] = []

    print(f"Ingesta BRONZE · lote {run_id} · {'curl' if args.curl else 'urllib'}")
    staging = Path(tempfile.mkdtemp(prefix=f"{run_id}-", dir=staging_parent))
    try:
        for dominio in dominios:
            data, sidecar, size, elapsed = preparar_recurso(
                dominio, FUENTES[dominio], args.curl, staging, run_id
            )
            prepared.append((dominio, data, sidecar, size, elapsed))
            print(f"[validado] {dominio:16s} {size:>9,d} B  {elapsed:7.1f} ms")

        manifest = {
            "run_id": run_id,
            "complete": True,
            "domains": list(dominios),
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
        atomic_write_text(staging / "manifest.json",
                          json.dumps(manifest, ensure_ascii=False, indent=2))
        runs = RAW / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        final_run = runs / run_id
        if final_run.exists():
            raise FileExistsError(f"el lote {run_id} ya existe")
        os.replace(staging, final_run)
    except Exception as error:
        print(f"[FALLO] lote {run_id} cancelado: {error}")
        print("Ningún recurso incompleto se usará para construir SILVER.")
        return 1
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print(f"[ok] lote completo: {len(prepared)}/{len(dominios)} recursos promovidos a "
          f"{display_path(final_run)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
