#!/usr/bin/env python3
"""
Utilidad de portabilidad: fuerza la salida de consola a UTF-8.

Problema: en Windows la consola suele usar cp1252. Los scripts imprimen
caracteres Unicode (✓, ✗, ·, —, m², 🧠) y Python lanza UnicodeEncodeError,
abortando el pipeline. En Linux/macOS el default ya es UTF-8, así que esto
es inofensivo.

Uso (como primera importación propia del script):
    from _utf8 import *          # noqa: F401,F403
o bien:
    import _utf8                 # noqa: F401

Importarlo ya ejecuta la reconfiguración (efecto de import).
"""
from __future__ import annotations
import sys


def forzar_utf8() -> None:
    """Reconfigura stdout/stderr a UTF-8 si la plataforma lo permite."""
    for stream in (sys.stdout, sys.stderr):
        # reconfigure existe en Python 3.7+ para TextIOWrapper
        reconfig = getattr(stream, "reconfigure", None)
        if reconfig is not None:
            try:
                reconfig(encoding="utf-8")
            except (ValueError, OSError):
                # stream redirigido a algo que no admite reconfigure; ignorar
                pass


# Efecto de importación: al importar este módulo, la salida queda en UTF-8.
forzar_utf8()
