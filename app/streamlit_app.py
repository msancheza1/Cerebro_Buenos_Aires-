#!/usr/bin/env python3
"""
Tramo VISTAS — Herramienta B: Streamlit.  (requiere `pip install streamlit pandas`)

Dashboard interactivo sobre lago/gold/. Fase 3: añade mapa por comuna (centroides
del geojson), descarga de CSV, filtros/ranking y comparador. Mantiene el bloque
obligatorio de fuente / vigencia / estado verificado.

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


def _centroides() -> dict:
    """{comuna: (lat, lon)} desde gold/comunas.geojson (Point o polígono)."""
    p = GOLD / "comunas.geojson"
    if not p.exists():
        return {}
    gj = json.loads(p.read_text(encoding="utf-8"))

    def planas(geom):
        t, c = geom.get("type"), geom.get("coordinates", [])
        if t == "Point":
            return [c]
        if t == "Polygon":
            return [pt for ring in c for pt in ring]
        if t == "MultiPolygon":
            return [pt for poly in c for ring in poly for pt in ring]
        return []

    out = {}
    for feat in gj.get("features", []):
        com = feat.get("properties", {}).get("comuna")
        pts = planas(feat.get("geometry", {}))
        if com is None or not pts:
            continue
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        out[int(com)] = (lat, lon)
    return out


st.title("🧠 Cerebro Buenos Aires")
st.caption("Infraestructura y servicios urbanos por comuna · réplica del ejemplo Cerebro Lima")

if any(f.get("_origen") == "semilla_demo" for f in meta.get("fuentes", {}).values()):
    st.warning("Datos SEMILLA (demo): estructura real de BA Data pero NO oficiales. "
               "Corré scripts/ingest_all.py con internet para reemplazarlos.")

# tarjetas de totales
cols = st.columns(len(indicadores))
for c, k in zip(cols, indicadores):
    c.metric(ETQ.get(k, k), f"{df[k].sum():,.0f}")

# ---- selector de indicador global ----
st.subheader("Indicador por comuna")
ind = st.selectbox("Elegí un indicador", indicadores, format_func=lambda k: ETQ.get(k, k))

col_izq, col_der = st.columns([3, 2])
with col_izq:
    st.bar_chart(df.set_index("comuna")[ind])
with col_der:
    st.markdown("**Ranking**")
    rank = df[["comuna", ind]].sort_values(ind, ascending=False).reset_index(drop=True)
    rank.index += 1
    st.dataframe(rank.rename(columns={ind: ETQ.get(ind, ind)}), use_container_width=True)

# ---- mapa por comuna (centroides + tamaño proporcional) ----
cent = _centroides()
if cent:
    st.subheader("Mapa por comuna")
    mapdf = df[["comuna", ind]].copy()
    mapdf["lat"] = mapdf["comuna"].map(lambda c: cent.get(int(c), (None, None))[0])
    mapdf["lon"] = mapdf["comuna"].map(lambda c: cent.get(int(c), (None, None))[1])
    mapdf = mapdf.dropna(subset=["lat", "lon"])
    vmax = mapdf[ind].max() or 1
    mapdf["size"] = 80 + (mapdf[ind] / vmax) * 600
    st.map(mapdf, latitude="lat", longitude="lon", size="size", color="#4cc9f0")
    st.caption("Burbuja proporcional al valor del indicador (centroides de comuna).")

# ---- comparador de comunas ----
st.subheader("Comparador de comunas")
cc1, cc2 = st.columns(2)
comunas = df["comuna"].tolist()
with cc1:
    a = st.selectbox("Comuna A", comunas, index=0, key="cmpA")
with cc2:
    b = st.selectbox("Comuna B", comunas, index=1 if len(comunas) > 1 else 0, key="cmpB")
fa = df[df["comuna"] == a].iloc[0]
fb = df[df["comuna"] == b].iloc[0]
comp = pd.DataFrame({
    "Indicador": [ETQ.get(k, k) for k in indicadores],
    f"Comuna {a}": [fa[k] for k in indicadores],
    f"Comuna {b}": [fb[k] for k in indicadores],
})
comp["Diferencia (A - B)"] = comp[f"Comuna {a}"] - comp[f"Comuna {b}"]
st.dataframe(comp, use_container_width=True, hide_index=True)

# ---- tabla completa + descarga ----
st.subheader("Tabla completa")
tabla = df.rename(columns=ETQ)
st.dataframe(tabla, use_container_width=True)
st.download_button(
    "⬇️ Descargar indicadores (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="indicadores_por_comuna.csv",
    mime="text/csv",
)

# ---- fuente / vigencia / estado ----
with st.expander("Fuente · vigencia · estado", expanded=True):
    for d, m in meta.get("fuentes", {}).items():
        st.markdown(f"- **{d}**: {m.get('fuente','')} — {m.get('organismo','')} "
                    f"([dataset]({m.get('url','#')}), licencia {m.get('licencia','')})")
    st.markdown(f"**Última construcción (gold):** {meta.get('generado','')}")
    st.markdown(f"**Motor:** {meta.get('motor','sqlite')}")
    st.success(f"Estado: ✓ {meta.get('estado','verificado')}")
    st.caption("Cero cifras sin fuente, sin vigencia ni fecha de prueba.")

# ---- linaje (si está en el meta) ----
linaje = meta.get("linaje", {})
if linaje:
    with st.expander("Linaje de datos (raw + SHA-256)"):
        lin = pd.DataFrame([
            {"dominio": d, "raw_file": l.get("raw_file"),
             "sha256": (l.get("raw_sha256") or "")[:16] + "…",
             "filas": l.get("filas_salida"),
             "descartadas": l.get("filas_descartadas")}
            for d, l in linaje.items()
        ])
        st.dataframe(lin, use_container_width=True, hide_index=True)
