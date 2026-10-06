#!/usr/bin/env python3
"""
Tramo GOLD — SILVER -> indicadores por comuna (lago/gold).

Solo publica dominios marcados "publicable": true en lago/silver/_verificacion.json.
"Si falla, no se publica."

Motor de consulta (dos herramientas, requisito del taller):
  A) SQLite (biblioteca estándar de Python)  -> corre en el sandbox
  B) DuckDB (scripts/query_duckdb.py)         -> documentada (mismas queries)
Decisión en la bitácora: DuckDB para analítica sobre Parquet; SQLite como plan B
sin dependencias (el que corre aquí).

Construye:
  - lago/gold/indicadores_por_comuna.csv   (una fila por comuna con todos los indicadores)
  - lago/gold/<indicador>.csv              (uno por indicador, para el dashboard)
  - lago/gold/_meta.json                   (fuentes + fecha + estado verificado)
  - lago/gold/cerebro.sqlite               (base consultable)

Uso:
    python scripts/build_gold.py
"""
from __future__ import annotations
import _utf8  # noqa: F401  (reconfigura stdout/stderr a UTF-8; portabilidad Windows)
import csv
import datetime as dt
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "lago" / "silver"
GOLD = ROOT / "lago" / "gold"
COMUNAS = list(range(1, 16))


def _verificacion() -> dict:
    p = SILVER / "_verificacion.json"
    if not p.exists():
        print("[!] No existe _verificacion.json. Corré scripts/verify.py primero.", file=sys.stderr)
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("resultado", {})


def _publicable(dominio: str, verif: dict) -> bool:
    return verif.get(dominio, {}).get("publicable", False)


def _cargar_silver(con: sqlite3.Connection, dominio: str):
    p = SILVER / f"{dominio}.csv"
    with p.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        cols = next(reader)
        rows = list(reader)
    con.execute(f"DROP TABLE IF EXISTS {dominio}")
    con.execute(f"CREATE TABLE {dominio} ({', '.join(c + ' TEXT' for c in cols)})")
    ph = ", ".join("?" for _ in cols)
    con.executemany(f"INSERT INTO {dominio} VALUES ({ph})", rows)
    con.commit()


def _fuentes_meta(dominios) -> dict:
    out = {}
    for d in dominios:
        mp = SILVER / f"{d}.meta.json"
        if mp.exists():
            m = json.loads(mp.read_text(encoding="utf-8"))
            out[d] = {"fuente": m.get("fuente"), "organismo": m.get("organismo"),
                      "url": m.get("url"), "licencia": m.get("licencia"),
                      "_origen": m.get("_origen"),
                      "fecha_dato": m.get("fecha_transformacion")}
    return out


def _sha256_archivo(p: Path) -> str | None:
    """SHA256 del contenido de un archivo (para linaje reproducible)."""
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def _linaje(dominios) -> dict:
    """De qué archivo RAW (+ sha256) salió cada dominio y cuántas filas sobrevivieron.

    Encadena GOLD <- SILVER.meta.json <- RAW (archivo + hash). Permite rastrear
    cualquier indicador hasta el byte exacto del dato de origen.
    """
    out = {}
    for d in dominios:
        mp = SILVER / f"{d}.meta.json"
        if not mp.exists():
            continue
        m = json.loads(mp.read_text(encoding="utf-8"))
        raw_rel = m.get("raw_file", "")
        raw_abs = (ROOT / raw_rel) if raw_rel else None
        sha = _sha256_archivo(raw_abs) if raw_abs else None
        # si la ingesta dejó un sidecar con sha256, lo preferimos como referencia cruzada
        sha_ingesta = None
        if raw_abs:
            side = raw_abs.with_suffix(raw_abs.suffix + ".meta.json")
            if side.exists():
                sha_ingesta = json.loads(side.read_text(encoding="utf-8")).get("sha256")
        out[d] = {
            "raw_file": raw_rel,
            "raw_sha256": sha,
            "raw_sha256_ingesta": sha_ingesta,
            "sha256_coincide": (sha is not None and sha == sha_ingesta) if sha_ingesta else None,
            "filas_descartadas": m.get("filas_descartadas"),
            "filas_salida": m.get("filas_salida"),
            "fecha_transformacion": m.get("fecha_transformacion"),
        }
    return out


def main() -> int:
    GOLD.mkdir(parents=True, exist_ok=True)
    verif = _verificacion()

    publicables = {d: _publicable(d, verif) for d in
                   ["ecobici", "ciclovias", "espacios_verdes", "hospitales"]}
    print("GOLD — dominios publicables:", publicables)

    con = sqlite3.connect(GOLD / "cerebro.sqlite")
    con.execute("PRAGMA journal_mode=WAL")

    for d, ok in publicables.items():
        if ok:
            _cargar_silver(con, d)

    # tabla base de comunas 1..15
    con.execute("DROP TABLE IF EXISTS comunas")
    con.execute("CREATE TABLE comunas (comuna INTEGER)")
    con.executemany("INSERT INTO comunas VALUES (?)", [(c,) for c in COMUNAS])
    con.commit()

    # ---- indicadores por comuna (SQL). Solo si el dominio es publicable ----
    indicadores = {}  # nombre_col -> {comuna: valor}

    def agg(dominio, expr, alias):
        if not publicables.get(dominio):
            return
        q = f"""
            SELECT CAST(comuna AS INTEGER) AS comuna, {expr} AS val
            FROM {dominio} GROUP BY CAST(comuna AS INTEGER)
        """
        res = {int(r[0]): r[1] for r in con.execute(q) if r[0] is not None}
        indicadores[alias] = res

    agg("ecobici", "COUNT(*)", "estaciones_ecobici")
    agg("ciclovias", "ROUND(SUM(CAST(long_metros AS REAL))/1000.0, 2)", "km_ciclovias")
    agg("espacios_verdes", "COUNT(*)", "espacios_verdes")
    agg("espacios_verdes", "ROUND(SUM(CAST(area_m2 AS REAL)), 1)", "m2_espacios_verdes")
    agg("hospitales", "COUNT(*)", "hospitales")

    # ---- tabla ancha por comuna ----
    cols_ind = list(indicadores.keys())
    filas = []
    for c in COMUNAS:
        fila = {"comuna": c}
        for col in cols_ind:
            fila[col] = indicadores[col].get(c, 0)
        filas.append(fila)

    ancha = GOLD / "indicadores_por_comuna.csv"
    with ancha.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["comuna"] + cols_ind)
        w.writeheader()
        w.writerows(filas)

    # ---- un CSV por indicador (para el dashboard) ----
    for col in cols_ind:
        p = GOLD / f"{col}.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["comuna", col])
            for c in COMUNAS:
                w.writerow([c, indicadores[col].get(c, 0)])

    # ---- meta gold: fuentes + fecha + estado verificado + LINAJE ----
    dominios_ok = [d for d, ok in publicables.items() if ok]
    # de qué dominio sale cada indicador (para linaje a nivel indicador)
    indicador_dominio = {
        "estaciones_ecobici": "ecobici",
        "km_ciclovias": "ciclovias",
        "espacios_verdes": "espacios_verdes",
        "m2_espacios_verdes": "espacios_verdes",
        "hospitales": "hospitales",
    }
    (GOLD / "_meta.json").write_text(json.dumps({
        "generado": dt.datetime.now().isoformat(timespec="seconds"),
        "motor": "sqlite",
        "estado": "verificado",
        "indicadores": cols_ind,
        "indicador_dominio": {k: v for k, v in indicador_dominio.items() if k in cols_ind},
        "publicables": publicables,
        "fuentes": _fuentes_meta(dominios_ok),
        "linaje": _linaje(dominios_ok),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    con.close()
    print(f"[ok] {len(cols_ind)} indicadores por comuna -> {ancha.relative_to(ROOT)}")
    print(f"     indicadores: {cols_ind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
