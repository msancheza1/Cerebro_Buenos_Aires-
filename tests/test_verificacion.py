#!/usr/bin/env python3
"""
Tests de las reglas de verificación (stdlib, sin dependencias).

Demuestran que "si falla, no se publica": construimos casos con datos malos y
comprobamos que las reglas los detectan. Correr con:  python tests/test_verificacion.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify  # noqa: E402


def _casos():
    return {
        "comuna fuera de rango se detecta": (
            verify.reglas_comunes([{"id": 1, "comuna": 99}]),
            "comuna_1_15",
        ),
        "id duplicado se detecta": (
            verify.reglas_comunes([{"id": 1, "comuna": 1}, {"id": 1, "comuna": 2}]),
            "id_unico",
        ),
        "coord fuera de CABA se detecta": (
            verify.reglas_coords([{"lat": 0.0, "lon": 0.0}]),
            "coords_caba",
        ),
        "anclajes <= 0 se detecta": (
            verify.regla_positivo([{"anclajes_totales": 0}], "anclajes_totales"),
            "anclajes_totales_positivo",
        ),
        "nombre vacio se detecta": (
            verify.regla_no_vacio([{"nombre": "  "}], "nombre"),
            "nombre_no_vacio",
        ),
        "fila valida NO genera violacion": (
            verify.reglas_comunes([{"id": 5, "comuna": 7}])
            + verify.reglas_coords([{"lat": -34.60, "lon": -58.40}]),
            None,
        ),
    }


def main() -> int:
    fallos = 0
    for nombre, (viol, esperado) in _casos().items():
        codigos = [c for c, _ in viol]
        if esperado is None:
            ok = len(viol) == 0
        else:
            ok = esperado in codigos
        print(f"[{'PASS' if ok else 'FAIL'}] {nombre}")
        if not ok:
            print(f"       esperado={esperado!r}  obtenido={codigos!r}")
            fallos += 1
    print(f"\n{len(_casos()) - fallos}/{len(_casos())} tests OK")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
