"""
Tramo VISTAS — Herramienta B: dashboard interactivo con Streamlit.

Ejecutar (requiere `pip install streamlit`):
    streamlit run app/streamlit_app.py

Lee la capa GOLD configurada y ofrece selector interactivo entre Totales absolutos y
Tasas por habitante (Censo 2022), unidades explícitas y filtro de indicador + tabla +
bloque de procedencia/verificación. La variante A (elegida para publicar sin servidor)
es `scripts/build_dashboard.py` -> `<CEREBRO_APP_DIR>/index.html`.
"""
from __future__ import annotations
import csv
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
GOLD = Path(os.environ.get("CEREBRO_GOLD_DIR", ROOT / "lago" / "gold")).resolve()

ETIQUETAS = {
    "estaciones_ecobici": "Estaciones Ecobici",
    "km_ciclovias": "Km de ciclovías",
    "espacios_verdes": "Espacios verdes",
    "m2_espacios_verdes": "m² de espacios verdes",
    "hospitales": "Hospitales",
    "estaciones_ecobici_por_10000_hab": "Ecobici por 10.000 hab.",
    "km_ciclovias_por_10000_hab": "Ciclovías por 10.000 hab.",
    "espacios_verdes_por_10000_hab": "Espacios verdes por 10.000 hab.",
    "m2_verdes_por_hab": "Superficie verde por habitante",
    "hospitales_por_10000_hab": "Hospitales por 10.000 hab.",
}

UNIDADES_DEFAULT = {
    "estaciones_ecobici": "estaciones",
    "km_ciclovias": "km",
    "espacios_verdes": "espacios públicos",
    "m2_espacios_verdes": "m² (EPSG:9498)",
    "hospitales": "establecimientos",
    "estaciones_ecobici_por_10000_hab": "estaciones / 10.000 habitantes",
    "km_ciclovias_por_10000_hab": "km / 10.000 habitantes",
    "espacios_verdes_por_10000_hab": "espacios / 10.000 habitantes",
    "m2_verdes_por_hab": "m² / habitante",
    "hospitales_por_10000_hab": "hospitales / 10.000 habitantes",
}

FACTORES_TASA = {
    "estaciones_ecobici_por_10000_hab": ("estaciones_ecobici", 10000),
    "km_ciclovias_por_10000_hab": ("km_ciclovias", 10000),
    "espacios_verdes_por_10000_hab": ("espacios_verdes", 10000),
    "m2_verdes_por_hab": ("m2_espacios_verdes", 1),
    "hospitales_por_10000_hab": ("hospitales", 10000),
}


def safe_url(value: str) -> str:
    parsed = urlparse(value or "")
    return value if parsed.scheme == "https" and parsed.netloc else "#"


def format_metric(indicator: str, value: float, is_rate: bool) -> str:
    if is_rate:
        return f"{value:,.2f}"
    decimals = 2 if indicator == "km_ciclovias" else (
        1 if indicator == "m2_espacios_verdes" else 0
    )
    return f"{value:,.{decimals}f}"


st.set_page_config(page_title="Cerebro Buenos Aires", page_icon="🧠", layout="wide")
st.title("🧠 Cerebro Buenos Aires")
st.caption("Infraestructura y servicios urbanos por comuna · Totales y tasas por habitante (Censo 2022)")

with (GOLD / "indicadores_por_comuna.csv").open(encoding="utf-8") as f:
    filas = list(csv.DictReader(f))
meta = json.loads((GOLD / "_meta.json").read_text(encoding="utf-8"))
if meta.get("quality_status") != "verified":
    st.error("La capa GOLD no tiene verificación válida; no se publica el dashboard.")
    st.stop()

provenance = meta.get("provenance_status", "unknown")
if provenance == "demo":
    st.warning("DEMO · NO OFICIAL: cifras generadas para probar el pipeline; no describen Buenos Aires.")

indicadores_totales = meta["indicadores"]
indicadores_tasas = meta.get(
    "indicadores_normalizados",
    list(FACTORES_TASA.keys()),
)
normalizacion = meta.get("normalizacion", {})

for r in filas:
    r["comuna"] = int(r["comuna"])
    r["poblacion"] = int(float(r.get("poblacion", 0)))
    r["anio_poblacion"] = int(float(r.get("anio_poblacion", 2022)))
    for k in indicadores_totales + indicadores_tasas:
        if k in r:
            v = float(r[k])
            r[k] = int(v) if v.is_integer() and k not in indicadores_tasas else v

poblacion_total = sum(r["poblacion"] for r in filas)
anio_poblacion = filas[0]["anio_poblacion"] if filas else 2022

modo = st.radio(
    "Modo de visualización",
    options=["Totales absolutos", f"Tasas por habitante (Censo {anio_poblacion})"],
    horizontal=True,
)
es_tasa = modo.startswith("Tasas")
indicadores_activos = indicadores_tasas if es_tasa else indicadores_totales


def unidad_de(k: str) -> str:
    if k in normalizacion and "unidad" in normalizacion[k]:
        return normalizacion[k]["unidad"]
    return UNIDADES_DEFAULT.get(k, "")


cols = st.columns(len(indicadores_activos) + 1)
cols[0].metric(
    f"Población CABA (Censo {anio_poblacion})",
    f"{poblacion_total:,}",
    help="Habitantes censados en las 15 comunas (IDECBA / INDEC Censo 2022)",
)

totales_brutos = {k: sum(float(r[k]) for r in filas) for k in indicadores_totales}
for col, k in zip(cols[1:], indicadores_activos):
    if es_tasa:
        num_col, factor = FACTORES_TASA[k]
        val = (totales_brutos[num_col] / poblacion_total) * factor if poblacion_total else 0.0
    else:
        val = totales_brutos[k]
    col.metric(
        f"{ETIQUETAS.get(k, k)} ({unidad_de(k)})",
        format_metric(k, val, es_tasa),
    )

ind = st.selectbox(
    "Indicador a comparar por comuna",
    indicadores_activos,
    format_func=lambda k: f"{ETIQUETAS.get(k, k)} [{unidad_de(k)}]",
)
st.subheader(
    f"{ETIQUETAS.get(ind, ind)} por comuna · Unidad: {unidad_de(ind)}"
    + (f" · Censo {anio_poblacion}" if es_tasa else "")
)
st.bar_chart({f"Comuna {r['comuna']:02d}": r[ind] for r in filas})

st.subheader(
    f"Tabla por comuna ({'Tasas normalizadas · Censo ' + str(anio_poblacion) if es_tasa else 'Totales absolutos'})"
)
columnas_tabla = ["comuna", "poblacion", "anio_poblacion", *indicadores_activos]
st.dataframe(
    [{c: r[c] for c in columnas_tabla} for r in filas],
    use_container_width=True,
)

st.markdown("---")
st.markdown(
    f"**Denominador poblacional:** `{poblacion_total:,}` habitantes (Censo `{anio_poblacion}`) · "
    f"**Última construcción (gold):** `{meta['generado']}` · "
    f"**Calidad:** ✓ `{meta['quality_status']}` · **Procedencia:** `{provenance}`"
)
for dom, f in meta["fuentes"].items():
    anio_str = f" · año censal {f['anio_poblacion']}" if f.get("anio_poblacion") else ""
    st.caption(
        f"**{dom}**: {f['fuente']} — {f['organismo']} ({f['licencia']}){anio_str} · "
        f"ingesta {f.get('fecha_ingesta', 'sin fecha')} · [dataset]({safe_url(str(f.get('url', '')))})"
    )
