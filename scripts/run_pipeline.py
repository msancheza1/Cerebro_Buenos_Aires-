#!/usr/bin/env python3
"""
Orquestador del pipeline completo de Cerebro Buenos Aires (multiplataforma).

Equivale a scripts/run_pipeline.sh pero corre en Windows, Linux y macOS sin bash.
Ejecuta cada tramo EN ORDEN y SE DETIENE en el primer fallo ("si falla, no se
publica" aplicado al pipeline entero). Usa el MISMO intérprete que lo invoca,
así que si lo corrés con el Python del .venv, todos los tramos usan ese entorno.

Uso:
    python scripts/run_pipeline.py              # datos semilla (offline)
    python scripts/run_pipeline.py --ingesta    # intenta ingesta real (necesita internet)
    python scripts/run_pipeline.py --curl       # ingesta real usando curl

Código de salida:
    0  -> todos los tramos OK
    N  -> el tramo N-ésimo falló (se detiene ahí)
"""
from __future__ import annotations
import _utf8  # noqa: F401  (reconfigura stdout/stderr a UTF-8; portabilidad Windows)
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "tests"
PY = sys.executable  # mismo intérprete (respeta el .venv activo)

LINEA = "=" * 56


def paso(numero: int, total: int, titulo: str, script: Path, *args: str) -> None:
    """Corre un tramo; si devuelve != 0, aborta todo el pipeline."""
    print(f"\n[{numero}/{total}] {titulo}")
    print("-" * 56)
    cmd = [PY, str(script), *args]
    res = subprocess.run(cmd, cwd=str(ROOT))
    if res.returncode != 0:
        print(f"\n✗ El tramo '{titulo}' falló (exit {res.returncode}). "
              f"Pipeline detenido.", file=sys.stderr)
        raise SystemExit(numero)


def main() -> int:
    ingesta = "--ingesta" in sys.argv or "--curl" in sys.argv
    usar_curl = "--curl" in sys.argv
    total = 9

    print(LINEA)
    print(" CEREBRO BUENOS AIRES · pipeline")
    print(LINEA)

    # [1] Datos de entrada: ingesta real o semilla
    if ingesta:
        print(f"\n[1/{total}] Ingesta REAL desde BA Data"
              + (" (curl)" if usar_curl else " (urllib)"))
        print("-" * 56)
        extra = ["--curl"] if usar_curl else []
        res = subprocess.run([PY, str(SCRIPTS / "ingest_all.py"), *extra], cwd=str(ROOT))
        if res.returncode != 0:
            print("  (ingesta falló o incompleta; sigo con lo que haya en lago/raw/)",
                  file=sys.stderr)
    else:
        paso(1, total, "Datos semilla (offline)", SCRIPTS / "_gen_seed.py")

    # [2] bronze -> silver
    paso(2, total, "Limpieza  bronze -> silver", SCRIPTS / "transform_silver.py")
    # [3] diccionario de datos (gobernanza)
    paso(3, total, "Diccionario de datos (gobernanza)", SCRIPTS / "diccionario.py")
    # [4] verificación de calidad
    paso(4, total, "Verificación (si falla, no se publica)", SCRIPTS / "verify.py")
    # [5] perfilado / completitud por columna
    paso(5, total, "Perfilado / completitud de SILVER", SCRIPTS / "profile_silver.py")
    # [6] tests de las reglas
    paso(6, total, "Tests de verificación", TESTS / "test_verificacion.py")
    # [7] silver -> gold (incluye linaje raw+sha256)
    paso(7, total, "Indicadores  silver -> gold (con linaje)", SCRIPTS / "build_gold.py")
    # [8] consultas de ejemplo
    paso(8, total, "Consultas de ejemplo (SQLite)", SCRIPTS / "query_sqlite.py")
    # [9] dashboard estático (regenera fecha + cifras + linaje)
    paso(9, total, "Dashboard estático", SCRIPTS / "build_dashboard.py")

    print("\n" + LINEA)
    print(" OK. Pipeline completo. Abrí app/index.html en el navegador.")
    print(LINEA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
