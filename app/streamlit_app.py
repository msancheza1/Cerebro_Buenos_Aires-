#!/usr/bin/env python3
"""
Tramo VISTAS — Herramienta B: Streamlit.  (requiere `pip install streamlit pandas`)

Dashboard interactivo sobre lago/gold/. Mismos indicadores que el HTML estático,
con selector de comuna y ranking. Incluye el bloque de fuente/vigencia/estado.

Uso:
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations
import json
import os
from pathlib import Path

try:
    import pandas as pd
    import streamlit as st
except ImportError as e:  # pragma: no cover
    raise SystemExit("Falta streamlit/pandas: pip install streamlit pandas") from e

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_GOLD = ROOT / "lago" / "gold"
DEMO_GOLD = ROOT / "build" / "demo" / "gold"
default_gold = OFFICIAL_GOLD if (OFFICIAL_GOLD / "_meta.json").exists() else DEMO_GOLD
GOLD = Path(os.environ.get("CEREBRO_GOLD_DIR", default_gold)).resolve()

st.set_page_config(page_title="Cerebro Buenos Aires", page_icon="🧠", layout="wide")

df = pd.read_csv(GOLD / "indicadores_por_comuna.csv")
meta = json.loads((GOLD / "_meta.json").read_text(encoding="utf-8"))
indicadores = meta["indicadores"]

ETQ = {
    "estaciones_ecobici": "Estaciones Ecobici",
    "km_ciclovias": "Km de ciclovías",
    "espacios_verdes": "Espacios verdes",
    "m2_espacios_verdes": "m² de espacios verdes",
    "hospitales": "Hospitales",
}

st.title("🧠 Cerebro Buenos Aires")
st.caption("Infraestructura y servicios urbanos por comuna · réplica del ejemplo Cerebro Lima")

if meta.get("provenance_status") == "demo":
    st.warning("DEMO · NO OFICIAL: estas cifras fueron generadas para probar el pipeline; "
               "no describen Buenos Aires.")

# tarjetas de totales
cols = st.columns(len(indicadores))
for c, k in zip(cols, indicadores):
    decimals = 1 if k in {"km_ciclovias", "m2_espacios_verdes"} else 0
    c.metric(ETQ.get(k, k), f"{df[k].sum():,.{decimals}f}")

st.subheader("Indicador por comuna")
ind = st.selectbox("Elegí un indicador", indicadores, format_func=lambda k: ETQ.get(k, k))
st.bar_chart(df.set_index("comuna")[ind])

st.subheader("Explorar una comuna")
com = st.selectbox("Comuna", df["comuna"].tolist())
fila = df[df["comuna"] == com].iloc[0]
cc = st.columns(len(indicadores))
for c, k in zip(cc, indicadores):
    decimals = 1 if k in {"km_ciclovias", "m2_espacios_verdes"} else 0
    c.metric(ETQ.get(k, k), f"{fila[k]:,.{decimals}f}")

st.subheader("Tabla completa")
st.dataframe(df.rename(columns=ETQ), use_container_width=True)

with st.expander("Fuente · vigencia · estado", expanded=True):
    for d, m in meta.get("fuentes", {}).items():
        st.markdown(f"- **{d}**: {m.get('fuente','')} — {m.get('organismo','')} "
                    f"([dataset]({m.get('url','#')}), licencia {m.get('licencia','')})")
    st.markdown(f"**Última construcción (gold):** {meta.get('generado','')}")
    st.markdown(f"**Motor:** {meta.get('motor','sqlite')}")
    st.markdown(f"**Calidad:** {meta.get('quality_status','unknown')}")
    st.markdown(f"**Procedencia:** {meta.get('provenance_status','unknown')}")
    if meta.get("datos_oficiales"):
        st.success("Datos oficiales descargados y lote verificado")
    else:
        st.warning("Demo verificada técnicamente; cifras no oficiales")
