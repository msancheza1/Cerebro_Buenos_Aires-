#!/usr/bin/env python3
"""
Tramo INGESTA — baja los datos crudos a lago/raw/ (BRONZE).

Dos herramientas probadas (requisito del taller "dos herramientas por tramo"):
  A) urllib (biblioteca estándar de Python)   -> por defecto
  B) curl (proceso externo)                    -> con --curl

Ambas bajan EXACTAMENTE el mismo recurso. La bitácora compara tiempos y comodidad.

El dato crudo se guarda tal cual salió (no se transforma) más un sidecar de metadatos
<archivo>.meta.json con: fuente, url, licencia, organismo, fecha de ingesta y sha256.
Eso garantiza que en SILVER/GOLD cada cifra pueda rastrearse hasta su origen.

Uso:
    python scripts/ingest_all.py              # todas las fuentes con urllib
    python scripts/ingest_all.py --curl       # idem con curl
    python scripts/ingest_all.py ecobici      # solo una fuente
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from fuentes import FUENTES

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "lago" / "raw"
HOY = dt.date.today().isoformat()


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def bajar_urllib(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "cerebro-ba/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def bajar_curl(url: str) -> bytes:
    out = subprocess.run(
        ["curl", "-sSL", "--fail", "-A", "cerebro-ba/1.0", url],
        capture_output=True, check=True,
    )
    return out.stdout


def ingestar(dominio: str, meta: dict, usar_curl: bool) -> bool:
    destino_dir = RAW / dominio
    destino_dir.mkdir(parents=True, exist_ok=True)
    archivo = destino_dir / f"{HOY}.{meta['formato']}"
    t0 = time.perf_counter()
    try:
        contenido = bajar_curl(meta["url"]) if usar_curl else bajar_urllib(meta["url"])
    except Exception as e:
        print(f"[!] {dominio}: no se pudo descargar ({e.__class__.__name__}: {e})",
              file=sys.stderr)
        return False
    dt_ms = (time.perf_counter() - t0) * 1000
    archivo.write_bytes(contenido)
    sidecar = archivo.with_suffix(archivo.suffix + ".meta.json")
    sidecar.write_text(json.dumps({
        "dominio": dominio,
        "fuente": meta["fuente"],
        "organismo": meta["organismo"],
        "url": meta["url"],
        "licencia": meta["licencia"],
        "formato": meta["formato"],
        "fecha_ingesta": dt.datetime.now().isoformat(timespec="seconds"),
        "herramienta": "curl" if usar_curl else "urllib",
        "bytes": len(contenido),
        "sha256": _sha256(contenido),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {dominio:16s} {len(contenido):>9,d} B  {dt_ms:7.1f} ms  -> {archivo.relative_to(ROOT)}")
    return True


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    usar_curl = "--curl" in sys.argv
    dominios = args if args else list(FUENTES)
    print(f"Ingesta BRONZE — herramienta: {'curl' if usar_curl else 'urllib'} — {HOY}")
    ok = sum(ingestar(d, FUENTES[d], usar_curl) for d in dominios if d in FUENTES)
    total = len([d for d in dominios if d in FUENTES])
    print(f"\n{ok}/{total} fuentes ingestadas.")
    if ok < total:
        print("Faltaron fuentes (probablemente sin internet en este entorno).\n"
              "Los datos semilla en lago/raw/ permiten seguir el pipeline igual.",
              file=sys.stderr)
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
