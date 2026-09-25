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
from pathlib import Path

try:
    import pandas as pd
    import streamlit as st
except ImportError as e:  # pragma: no cover
    raise SystemExit("Falta streamlit/pandas: pip install streamlit pandas") from e

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "lago" / "gold"

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

if any(f.get("_origen") == "semilla_demo" for f in meta.get("fuentes", {}).values()):
    st.warning("Datos SEMILLA (demo): estructura real de BA Data pero NO oficiales. "
               "Corré scripts/ingest_all.py con internet para reemplazarlos.")

# tarjetas de totales
cols = st.columns(len(indicadores))
for c, k in zip(cols, indicadores):
    c.metric(ETQ.get(k, k), f"{df[k].sum():,.0f}")

st.subheader("Indicador por comuna")
ind = st.selectbox("Elegí un indicador", indicadores, format_func=lambda k: ETQ.get(k, k))
st.bar_chart(df.set_index("comuna")[ind])

st.subheader("Explorar una comuna")
com = st.selectbox("Comuna", df["comuna"].tolist())
fila = df[df["comuna"] == com].iloc[0]
cc = st.columns(len(indicadores))
for c, k in zip(cc, indicadores):
    c.metric(ETQ.get(k, k), f"{fila[k]:,.0f}")

st.subheader("Tabla completa")
st.dataframe(df.rename(columns=ETQ), use_container_width=True)

with st.expander("Fuente · vigencia · estado", expanded=True):
    for d, m in meta.get("fuentes", {}).items():
        st.markdown(f"- **{d}**: {m.get('fuente','')} — {m.get('organismo','')} "
                    f"([dataset]({m.get('url','#')}), licencia {m.get('licencia','')})")
    st.markdown(f"**Última construcción (gold):** {meta.get('generado','')}")
    st.markdown(f"**Motor:** {meta.get('motor','sqlite')}")
    st.success(f"Estado: ✓ {meta.get('estado','verificado')}")
    st.caption("Cero cifras sin fuente, sin vigencia ni fecha de prueba.")
