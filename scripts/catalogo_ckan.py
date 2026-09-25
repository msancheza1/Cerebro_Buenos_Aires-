#!/usr/bin/env python3
"""
Tramo CATÁLOGO — Herramienta B: descubrimiento automático vía API CKAN de BA Data.

Buenos Aires Data corre sobre CKAN, por lo que expone una API estándar:
  https://data.buenosaires.gob.ar/api/3/action/package_search?q=<tema>&rows=<n>

Este script consulta la API por cada tema del MVP y arma un catálogo candidato,
para compararlo con el catálogo hecho a mano (catalogo/catalogo.csv, Herramienta A).

Requiere internet. Si no hay conexión, imprime el motivo y no rompe el pipeline.

Uso:
    python scripts/catalogo_ckan.py            # imprime datasets encontrados por tema
    python scripts/catalogo_ckan.py --save     # además escribe catalogo/catalogo_ckan.csv
"""
from __future__ import annotations
import csv
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

CKAN = "https://data.buenosaires.gob.ar/api/3/action/package_search"
TEMAS = {
    "movilidad": "ecobici bicicletas ciclovias",
    "ambiente": "espacios verdes parques",
    "salud": "hospitales centros de salud",
    "urbanismo": "comunas barrios",
}
ROOT = Path(__file__).resolve().parents[1]


def buscar(query: str, rows: int = 10) -> list[dict]:
    url = f"{CKAN}?{urllib.parse.urlencode({'q': query, 'rows': rows})}"
    req = urllib.request.Request(url, headers={"User-Agent": "cerebro-ba/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if not data.get("success"):
        return []
    out = []
    for pkg in data["result"]["results"]:
        formatos = sorted({r.get("format", "").upper() for r in pkg.get("resources", []) if r.get("format")})
        out.append({
            "id": pkg.get("name", ""),
            "dataset": pkg.get("title", ""),
            "organismo": (pkg.get("organization") or {}).get("title", ""),
            "formatos": ",".join(formatos),
            "actualizacion": pkg.get("frequency", "") or pkg.get("update_frequency", ""),
            "url": f"https://data.buenosaires.gob.ar/dataset/{pkg.get('name','')}",
        })
    return out


def main() -> int:
    save = "--save" in sys.argv
    filas = []
    for tema, q in TEMAS.items():
        try:
            resultados = buscar(q)
        except Exception as e:  # sin internet / API suspendida
            print(f"[!] No se pudo consultar CKAN para '{tema}': {e}", file=sys.stderr)
            print("    (El sandbox del taller no tiene internet; corré esto con conexión.)",
                  file=sys.stderr)
            return 1
        print(f"\n=== TEMA: {tema} ({len(resultados)} datasets) ===")
        for r in resultados:
            print(f"  - {r['dataset']}  [{r['formatos']}]  {r['url']}")
            r["tema"] = tema
            filas.append(r)

    if save and filas:
        dest = ROOT / "catalogo" / "catalogo_ckan.csv"
        with dest.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["tema", "id", "dataset", "organismo",
                                              "formatos", "actualizacion", "url"])
            w.writeheader()
            w.writerows(filas)
        print(f"\n[ok] Catálogo CKAN guardado en {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
