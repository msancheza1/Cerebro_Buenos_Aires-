#!/usr/bin/env python3
"""Utilidades compartidas para rutas, hashes y escrituras seguras del pipeline."""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configured_path(variable: str, default: str) -> Path:
    """Obtiene una ruta absoluta desde una variable de entorno o un valor del repo."""
    value = os.environ.get(variable)
    return Path(value).resolve() if value else (ROOT / default).resolve()


RAW = configured_path("CEREBRO_RAW_DIR", "lago/raw")
SILVER = configured_path("CEREBRO_SILVER_DIR", "lago/silver")
GOLD = configured_path("CEREBRO_GOLD_DIR", "lago/gold")
APP = configured_path("CEREBRO_APP_DIR", "app")
MODE = os.environ.get("CEREBRO_MODE", "official")
REQUIRED_DOMAINS = ("ecobici", "ciclovias", "espacios_verdes", "hospitales")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Escribe un archivo completo sin exponer contenido parcial."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def atomic_write_text(path: Path, content: str) -> None:
    atomic_write_bytes(path, content.encode("utf-8"))


def display_path(path: Path) -> str:
    """Presenta rutas internas de forma relativa y rutas externas de forma absoluta."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def replace_directory(staging: Path, destination: Path) -> None:
    """Promueve una salida completa; restaura la anterior si falla el intercambio."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = destination.with_name(f".{destination.name}.backup-{os.getpid()}")
    if backup.exists():
        # El commit ya ocurrió: la limpieza no debe convertir un éxito en fallo.
        shutil.rmtree(backup, ignore_errors=True)
    had_previous = destination.exists()
    if had_previous:
        os.replace(destination, backup)
    try:
        os.replace(staging, destination)
    except Exception:
        if had_previous and backup.exists():
            os.replace(backup, destination)
        raise
    if backup.exists():
        # El commit ya ocurrió: la limpieza no debe convertir un éxito en fallo.
        shutil.rmtree(backup, ignore_errors=True)
