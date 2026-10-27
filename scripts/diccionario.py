#!/usr/bin/env python3
"""
Tramo GOBERNANZA — Diccionario de datos formal por dominio.

Un buen programa de gobernanza necesita un diccionario de datos: qué significa
cada columna, su tipo, su unidad y qué regla de calidad debe cumplir. Este
archivo es la FUENTE ÚNICA DE VERDAD de los metadatos de columnas del proyecto.

Genera dos salidas en catalogo/:
  - diccionario_datos.json   (consumible por otros scripts: dashboard, perfilado)
  - diccionario_datos.md     (legible por humanos: tablas por dominio)

Los tipos y columnas coinciden con los SCHEMAS de transform_silver.py y las
reglas de verify.py (si cambian allí, actualizá acá para que no haya deriva).

Uso:
    python scripts/diccionario.py
"""
from __future__ import annotations
import _utf8  # noqa: F401  (reconfigura stdout/stderr a UTF-8; portabilidad Windows)
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGO = ROOT / "catalogo"

# dominio -> metadatos (descripción del dataset + columnas)
# Cada columna: tipo lógico, unidad, descripción, regla de calidad, PII (sí/no).
DICCIONARIO = {
    "ecobici": {
        "descripcion": "Estaciones de bicicletas públicas (Ecobici) de la Ciudad de Buenos Aires.",
        "grano": "una fila = una estación de Ecobici",
        "clave": "id",
        "columnas": {
            "id":               {"tipo": "entero",  "unidad": "-",       "pii": False, "descripcion": "Identificador único de la estación.",                 "regla": "no nulo y único"},
            "nombre":           {"tipo": "texto",   "unidad": "-",       "pii": False, "descripcion": "Nombre de la estación (normalizado a Title Case).",   "regla": "normalizado; sin validación de no vacío en verify.py"},
            "comuna":           {"tipo": "entero",  "unidad": "comuna",  "pii": False, "descripcion": "Comuna de CABA derivada por punto-en-polígono a partir de lat/lon.",          "regla": "entero en 1..15"},
            "lat":              {"tipo": "decimal", "unidad": "grados",  "pii": False, "descripcion": "Latitud (WGS84).",                                    "regla": "entre -34.71 y -34.52 (bounding box CABA)"},
            "lon":              {"tipo": "decimal", "unidad": "grados",  "pii": False, "descripcion": "Longitud (WGS84).",                                   "regla": "entre -58.54 y -58.33 (bounding box CABA)"},
        },
    },
    "ciclovias": {
        "descripcion": "Red de ciclovías de la Ciudad de Buenos Aires (geometrías de línea).",
        "grano": "una fila = un tramo de ciclovía",
        "clave": "id",
        "columnas": {
            "id":          {"tipo": "entero",  "unidad": "-",      "pii": False, "descripcion": "Identificador único del tramo.",            "regla": "no nulo y único"},
            "nombre":      {"tipo": "texto",   "unidad": "-",      "pii": False, "descripcion": "Nombre o calle del tramo de ciclovía.",     "regla": "normalizado; sin validación de no vacío en verify.py"},
            "comuna":      {"tipo": "entero",  "unidad": "comuna", "pii": False, "descripcion": "Comuna de CABA del tramo.",                 "regla": "entero en 1..15"},
            "long_metros": {"tipo": "decimal", "unidad": "metros", "pii": False, "descripcion": "Longitud del tramo en metros.",            "regla": "> 0"},
            "tipo":        {"tipo": "texto",   "unidad": "-",      "pii": False, "descripcion": "Tipo de infraestructura ciclista.",         "regla": "libre"},
        },
    },
    "espacios_verdes": {
        "descripcion": "Espacios verdes públicos (plazas, parques) de la Ciudad de Buenos Aires.",
        "grano": "una fila = un espacio verde",
        "clave": "id",
        "columnas": {
            "id":            {"tipo": "entero",  "unidad": "-",      "pii": False, "descripcion": "Identificador único del espacio verde.",    "regla": "no nulo y único"},
            "nombre":        {"tipo": "texto",   "unidad": "-",      "pii": False, "descripcion": "Nombre del espacio verde.",                 "regla": "normalizado; sin validación de no vacío en verify.py"},
            "comuna":        {"tipo": "entero",  "unidad": "comuna", "pii": False, "descripcion": "Comuna de CABA del espacio verde.",         "regla": "entero en 1..15"},
            "area_m2":       {"tipo": "decimal", "unidad": "m²",     "pii": False, "descripcion": "Superficie del espacio verde en metros cuadrados.", "regla": "> 0"},
            "clasificacion": {"tipo": "texto",   "unidad": "-",      "pii": False, "descripcion": "Clasificación del espacio (plaza, parque, etc.).",  "regla": "libre"},
        },
    },
    "hospitales": {
        "descripcion": "Hospitales de la Ciudad de Buenos Aires; no incluye un dominio independiente de CeSAC.",
        "grano": "una fila = un establecimiento de salud",
        "clave": "id",
        "columnas": {
            "id":        {"tipo": "entero",  "unidad": "-",      "pii": False, "descripcion": "Identificador único del establecimiento.",   "regla": "no nulo y único"},
            "nombre":    {"tipo": "texto",   "unidad": "-",      "pii": False, "descripcion": "Nombre del hospital.",     "regla": "no vacío"},
            "tipo":      {"tipo": "texto",   "unidad": "-",      "pii": False, "descripcion": "Especialidad o tipo informado por la fuente (esp).", "regla": "libre"},
            "comuna":    {"tipo": "entero",  "unidad": "comuna", "pii": False, "descripcion": "Comuna de CABA del establecimiento.",        "regla": "entero en 1..15"},
            "direccion": {"tipo": "texto",   "unidad": "-",      "pii": False, "descripcion": "Dirección postal del establecimiento.",      "regla": "libre"},
        },
    },
}


def generar_json() -> Path:
    CATALOGO.mkdir(parents=True, exist_ok=True)
    destino = CATALOGO / "diccionario_datos.json"
    destino.write_text(json.dumps(DICCIONARIO, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return destino


def generar_md() -> Path:
    CATALOGO.mkdir(parents=True, exist_ok=True)
    destino = CATALOGO / "diccionario_datos.md"
    lineas = [
        "# Diccionario de datos — Cerebro Buenos Aires",
        "",
        "Metadatos formales de cada dominio de la capa **SILVER**. Fuente única de verdad: "
        "`scripts/diccionario.py`. Los tipos coinciden con `transform_silver.py` y las "
        "reglas con `verify.py`. Esquema vigente contrastado con los CSV de SILVER "
        "y la ingesta del **2026-10-06**. La procedencia se guarda en archivos "
        "`*.meta.json`, no en columnas adicionales. Los ID pueden ser generados "
        "por la transformación cuando faltan o se repiten en RAW.",
        "",
    ]
    for dominio, info in DICCIONARIO.items():
        lineas += [
            f"## {dominio}",
            "",
            f"{info['descripcion']}",
            "",
            f"- **Grano:** {info['grano']}",
            f"- **Clave primaria:** `{info['clave']}`",
            "",
            "| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |",
            "|---------|------|--------|-----|-------------|------------------|",
        ]
        for col, m in info["columnas"].items():
            pii = "sí" if m["pii"] else "no"
            lineas.append(
                f"| `{col}` | {m['tipo']} | {m['unidad']} | {pii} | {m['descripcion']} | {m['regla']} |"
            )
        lineas.append("")
    destino.write_text("\n".join(lineas), encoding="utf-8")
    return destino


def main() -> int:
    pj = generar_json()
    pm = generar_md()
    n_dom = len(DICCIONARIO)
    n_col = sum(len(d["columnas"]) for d in DICCIONARIO.values())
    print("Diccionario de datos generado")
    print("=" * 56)
    print(f"  dominios : {n_dom}")
    print(f"  columnas : {n_col}")
    print(f"  JSON  -> {pj.relative_to(ROOT)}")
    print(f"  MD    -> {pm.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
