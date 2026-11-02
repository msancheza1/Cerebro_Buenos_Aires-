#!/usr/bin/env python3
"""
Tramo VISTAS — Herramienta A: dashboard HTML estático autocontenido.

Lee la capa GOLD configurada y genera un HTML autocontenido en el directorio APP
configurado (sin servidor ni dependencias). Incluye selector interactivo entre
Totales absolutos y Tasas por habitante (Censo 2022), unidades explícitas,
año censal de población (2022), fuente, ingesta, calidad y procedencia.

Herramienta B: app/streamlit_app.py (interactivo; requiere streamlit).
Decisión en la bitácora: HTML estático para publicar sin infra (elegido para el entregable);
Streamlit para exploración interactiva local.

Uso:
    python scripts/build_dashboard.py
"""
from __future__ import annotations
import csv
import datetime as dt
import html as html_lib
import json
from urllib.parse import urlparse

from pipeline_common import APP, GOLD, atomic_write_text, display_path


def _safe_url(value: str) -> str:
    parsed = urlparse(value or "")
    return value if parsed.scheme == "https" and parsed.netloc else "#"


def _cargar():
    with (GOLD / "indicadores_por_comuna.csv").open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    meta = json.loads((GOLD / "_meta.json").read_text(encoding="utf-8"))
    return filas, meta


def _num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (ValueError, TypeError):
        return 0


def _es(value, decimals: int = 0) -> str:
    """Formato numérico en español: punto para miles y coma decimal (3.121.707 / 14,58)."""
    text = f"{float(value):,.{decimals}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def main() -> int:
    APP.mkdir(parents=True, exist_ok=True)
    filas, meta = _cargar()
    indicadores = meta["indicadores"]
    indicadores_tasas = meta.get(
        "indicadores_normalizados",
        [
            "estaciones_ecobici_por_10000_hab",
            "km_ciclovias_por_10000_hab",
            "espacios_verdes_por_10000_hab",
            "m2_verdes_por_hab",
            "hospitales_por_10000_hab",
        ],
    )
    normalizacion = meta.get("normalizacion", {})

    # Población censal total y año censal
    poblacion_total = sum(int(_num(r.get("poblacion", 0))) for r in filas)
    poblacion_es = _es(poblacion_total)
    anios_pob = {int(_num(r.get("anio_poblacion", 2022))) for r in filas if r.get("anio_poblacion")}
    anio_poblacion = sorted(anios_pob)[0] if anios_pob else 2022

    # Totales y máximos por indicador bruto (para barras de totales)
    total = {k: sum(_num(r[k]) for r in filas) for k in indicadores}
    maxv = {k: max((_num(r[k]) for r in filas), default=1) or 1 for k in indicadores}

    # Tasas agregadas de CABA y máximos por indicador normalizado (para barras de tasas)
    factores_tasa = {
        "estaciones_ecobici_por_10000_hab": ("estaciones_ecobici", 10000),
        "km_ciclovias_por_10000_hab": ("km_ciclovias", 10000),
        "espacios_verdes_por_10000_hab": ("espacios_verdes", 10000),
        "m2_verdes_por_hab": ("m2_espacios_verdes", 1),
        "hospitales_por_10000_hab": ("hospitales", 10000),
    }
    tasa_ciudad = {}
    for k in indicadores_tasas:
        num_col, factor = factores_tasa.get(k, (None, 1))
        if num_col and poblacion_total > 0:
            tasa_ciudad[k] = (total.get(num_col, 0) / poblacion_total) * factor
        else:
            tasa_ciudad[k] = 0.0
    maxv_tasa = {
        k: max((_num(r.get(k, 0)) for r in filas), default=1) or 1
        for k in indicadores_tasas
    }

    etiquetas = {
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

    unidades = {
        "estaciones_ecobici": "estaciones",
        "km_ciclovias": "km",
        "espacios_verdes": "espacios públicos",
        "m2_espacios_verdes": "m² (EPSG:9498)",
        "hospitales": "establecimientos",
        "estaciones_ecobici_por_10000_hab": normalizacion.get(
            "estaciones_ecobici_por_10000_hab", {}
        ).get("unidad", "estaciones / 10.000 habitantes"),
        "km_ciclovias_por_10000_hab": normalizacion.get(
            "km_ciclovias_por_10000_hab", {}
        ).get("unidad", "km / 10.000 habitantes"),
        "espacios_verdes_por_10000_hab": normalizacion.get(
            "espacios_verdes_por_10000_hab", {}
        ).get("unidad", "espacios / 10.000 habitantes"),
        "m2_verdes_por_hab": normalizacion.get("m2_verdes_por_hab", {}).get(
            "unidad", "m² / habitante"
        ),
        "hospitales_por_10000_hab": normalizacion.get(
            "hospitales_por_10000_hab", {}
        ).get("unidad", "hospitales / 10.000 habitantes"),
    }

    def format_value(indicator, value):
        if indicator in indicadores_tasas:
            return _es(value, 2)
        decimals = 2 if indicator == "km_ciclovias" else (
            1 if indicator == "m2_espacios_verdes" else 0
        )
        return _es(value, decimals)

    provenance = meta.get("provenance_status", "unknown")
    origen_demo = provenance == "demo"
    if meta.get("quality_status") != "verified":
        raise ValueError("GOLD no tiene quality_status=verified")

    def tarjetas_totales():
        out = [f"""
            <div class="card">
              <div class="card-val">{poblacion_es}</div>
              <div class="card-lbl">Población CABA</div>
              <div class="card-unit">habitantes · Censo {anio_poblacion}</div>
            </div>"""]
        for k in indicadores:
            out.append(f"""
            <div class="card">
              <div class="card-val">{format_value(k, total[k])}</div>
              <div class="card-lbl">{html_lib.escape(etiquetas.get(k, k))}</div>
              <div class="card-unit">{html_lib.escape(unidades.get(k, ""))}</div>
            </div>""")
        return "".join(out)

    def tarjetas_tasas():
        out = [f"""
            <div class="card">
              <div class="card-val">{poblacion_es}</div>
              <div class="card-lbl">Denominador poblacional</div>
              <div class="card-unit">habitantes · Censo {anio_poblacion}</div>
            </div>"""]
        for k in indicadores_tasas:
            out.append(f"""
            <div class="card">
              <div class="card-val">{format_value(k, tasa_ciudad[k])}</div>
              <div class="card-lbl">{html_lib.escape(etiquetas.get(k, k))}</div>
              <div class="card-unit">{html_lib.escape(unidades.get(k, ""))} · Censo {anio_poblacion}</div>
            </div>""")
        return "".join(out)

    def filas_tabla(cols):
        out = []
        for r in filas:
            pob = _es(int(_num(r.get('poblacion', 0))))
            celdas = "".join(f"<td>{format_value(k, r.get(k, 0))}</td>" for k in cols)
            out.append(
                f"<tr><td class='com'>Comuna {r['comuna']}</td>"
                f"<td>{pob}</td>{celdas}</tr>"
            )
        return "".join(out)

    def barras(indicador, max_dict):
        rows = sorted(filas, key=lambda r: _num(r.get(indicador, 0)), reverse=True)
        out = []
        for r in rows:
            v = _num(r.get(indicador, 0))
            pct = 100 * v / max_dict[indicador]
            out.append(f"""
            <div class="bar-row">
              <span class="bar-lbl">Comuna {r['comuna']}</span>
              <span class="bar-track"><span class="bar-fill" style="width:{pct:.1f}%"></span></span>
              <span class="bar-val">{format_value(indicador, v)}</span>
            </div>""")
        return "".join(out)

    fuentes = meta.get("fuentes", {})
    fuentes_html = "".join(
        f"<li><b>{html_lib.escape(str(domain))}</b>: {html_lib.escape(str(source.get('fuente', '')))} — "
        f"{html_lib.escape(str(source.get('organismo', '')))} "
        f"(<a href='{html_lib.escape(_safe_url(str(source.get('url', ''))), quote=True)}' "
        f"rel='noreferrer'>dataset</a>, licencia {html_lib.escape(str(source.get('licencia', '')))})"
        + (f" · año censal {int(source['anio_poblacion'])}" if source.get("anio_poblacion") else "")
        + f" · ingesta {html_lib.escape(str(source.get('fecha_ingesta', 'sin fecha')))}</li>"
        for domain, source in fuentes.items()
    )
    graficos_totales_html = "".join(
        f"<h2>{html_lib.escape(etiquetas.get(indicator, indicator))} por comuna "
        f"<span class='unit-badge'>{html_lib.escape(unidades.get(indicator, ''))}</span></h2>"
        f"<div>{barras(indicator, maxv)}</div>"
        for indicator in indicadores
    )
    graficos_tasas_html = "".join(
        f"<h2>{html_lib.escape(etiquetas.get(indicator, indicator))} por comuna "
        f"<span class='unit-badge'>{html_lib.escape(unidades.get(indicator, ''))} · Censo {anio_poblacion}</span></h2>"
        f"<div>{barras(indicator, maxv_tasa)}</div>"
        for indicator in indicadores_tasas
    )

    headers_totales = "".join(
        f"<th>{html_lib.escape(etiquetas.get(k, k))}<br><small class='th-unit'>{html_lib.escape(unidades.get(k, ''))}</small></th>"
        for k in indicadores
    )
    headers_tasas = "".join(
        f"<th>{html_lib.escape(etiquetas.get(k, k))}<br><small class='th-unit'>{html_lib.escape(unidades.get(k, ''))}</small></th>"
        for k in indicadores_tasas
    )

    generado = meta.get("generado", dt.datetime.now().isoformat(timespec="seconds"))

    aviso_demo = ""
    if origen_demo:
        aviso_demo = ("<div class='aviso'><strong>DEMO · NO OFICIAL.</strong> "
                      "Estas cifras fueron generadas para probar el pipeline y no describen "
                      "Buenos Aires. Las fuentes enlazadas son referencias de procedencia, "
                      "no el origen de observaciones descargadas.</div>")

    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cerebro Buenos Aires</title>
<style>
  :root {{ --bg:#0e1116; --card:#161b22; --line:#30363d; --fg:#e6edf3;
           --acc:#4cc9f0; --acc2:#80ffdb; --muted:#8b949e; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
          font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }}
  header {{ padding:32px 24px 16px; border-bottom:1px solid var(--line); }}
  h1 {{ margin:0; font-size:28px; letter-spacing:.5px; }}
  h1 .brain {{ color:var(--acc); }}
  .sub {{ color:var(--muted); margin-top:6px; }}
  main {{ max-width:1040px; margin:0 auto; padding:24px; }}
  .aviso {{ background:#3d2b00; border:1px solid #7a5b00; color:#ffd166;
            padding:12px 14px; border-radius:8px; margin-bottom:20px; font-size:14px; }}
  .toolbar {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between;
              gap:12px; background:var(--card); border:1px solid var(--line);
              border-radius:12px; padding:12px 16px; margin-bottom:22px; }}
  .toolbar-info {{ font-size:13px; color:var(--muted); }}
  .toolbar-info b {{ color:var(--acc2); }}
  .mode-switch {{ display:inline-flex; background:#0d1117; border:1px solid var(--line);
                  border-radius:8px; padding:3px; gap:4px; }}
  .mode-btn {{ appearance:none; border:0; background:transparent; color:var(--muted);
               font-size:13px; font-weight:600; padding:8px 14px; border-radius:6px;
               cursor:pointer; transition:all .15s ease; }}
  .mode-btn:hover {{ color:var(--fg); }}
  .mode-btn.active {{ background:var(--acc); color:#09131c; }}
  .view-panel {{ display:none; }}
  .view-panel.active {{ display:block; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(155px,1fr));
            gap:14px; margin-bottom:28px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
           padding:16px 12px; text-align:center; }}
  .card-val {{ font-size:26px; font-weight:700; color:var(--acc2); }}
  .card-lbl {{ color:var(--fg); font-size:13px; font-weight:600; margin-top:6px; }}
  .card-unit {{ color:var(--muted); font-size:11px; margin-top:3px; }}
  h2 {{ font-size:18px; border-left:3px solid var(--acc); padding-left:10px; margin-top:32px;
        display:flex; flex-wrap:wrap; align-items: baseline; gap:8px; }}
  .unit-badge {{ font-size:12px; font-weight:500; color:var(--acc); background:#112233;
                 border:1px solid #1f4260; padding:2px 8px; border-radius:999px; }}
  .table-wrap {{ overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
  th,td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:right; vertical-align:bottom; }}
  th {{ color:var(--muted); font-weight:600; }}
  .th-unit {{ font-weight:400; font-size:11px; color:#6e7681; }}
  td.com, th:first-child {{ text-align:left; white-space:nowrap; }}
  .bar-row {{ display:grid; grid-template-columns:90px 1fr 78px; align-items:center;
              gap:10px; margin:6px 0; font-size:13px; }}
  .bar-track {{ background:#21262d; border-radius:6px; height:14px; overflow:hidden; }}
  .bar-fill {{ display:block; height:100%;
               background:linear-gradient(90deg,var(--acc),var(--acc2)); }}
  .bar-val {{ text-align:right; color:var(--muted); font-variant-numeric:tabular-nums; }}
  .ficha {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
            padding:18px; margin-top:32px; font-size:14px; }}
  .ficha b {{ color:var(--acc2); }}
  .estado {{ display:inline-block; padding:2px 10px; border-radius:20px; font-size:13px; }}
  .estado.demo {{ background:#7a4b00; color:#fff3cd; }}
  .estado.official {{ background:#0f5132; color:#d1fae5; }}
  a {{ color:var(--acc); }}
  footer {{ color:var(--muted); font-size:12px; text-align:center; padding:24px; }}
</style>
</head>
<body>
<header>
  <h1><span class="brain">🧠</span> Cerebro Buenos Aires</h1>
  <div class="sub">Infraestructura y servicios urbanos por comuna · Totales y tasas normalizadas por habitante (Censo {anio_poblacion})</div>
</header>
<main>
  {aviso_demo}

  <div class="toolbar" role="region" aria-label="Selector de modo de indicadores">
    <div class="toolbar-info">
      <b>Denominador poblacional:</b> Censo {anio_poblacion} ({poblacion_es} habitantes en 15 comunas)
    </div>
    <div class="mode-switch" role="tablist" aria-label="Modo de visualización">
      <button type="button" id="btn-totales" class="mode-btn active" role="tab" aria-selected="true" onclick="setMode('totales')">
        Totales absolutos
      </button>
      <button type="button" id="btn-tasas" class="mode-btn" role="tab" aria-selected="false" onclick="setMode('tasas')">
        Tasas por habitante (Censo {anio_poblacion})
      </button>
    </div>
  </div>

  <div id="panel-totales" class="view-panel active">
    <section class="cards">{tarjetas_totales()}</section>

    {graficos_totales_html}

    <h2>Tabla de totales por comuna <span class="unit-badge">unidades absolutas · Censo {anio_poblacion}</span></h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Comuna</th>
            <th>Población<br><small class="th-unit">hab. (Censo {anio_poblacion})</small></th>
            {headers_totales}
          </tr>
        </thead>
        <tbody>{filas_tabla(indicadores)}</tbody>
      </table>
    </div>
  </div>

  <div id="panel-tasas" class="view-panel">
    <section class="cards">{tarjetas_tasas()}</section>

    {graficos_tasas_html}

    <h2>Tabla de tasas por habitante por comuna <span class="unit-badge">normalizado · Censo {anio_poblacion}</span></h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Comuna</th>
            <th>Población<br><small class="th-unit">hab. (Censo {anio_poblacion})</small></th>
            {headers_tasas}
          </tr>
        </thead>
        <tbody>{filas_tabla(indicadores_tasas)}</tbody>
      </table>
    </div>
  </div>

  <div class="ficha">
    <div><b>Fuentes</b><ul>{fuentes_html}</ul></div>
    <div><b>Denominador demográfico:</b> {poblacion_es} habitantes (año censal {anio_poblacion})</div>
    <div><b>Última construcción (gold):</b> {generado}</div>
    <div><b>Motor de consulta:</b> {meta.get('motor','sqlite')}</div>
    <div><b>Calidad:</b> <span class="estado {'demo' if origen_demo else 'official'}">✓ verificada</span></div>
    <div style="margin-top:8px"><b>Procedencia:</b> <span class="estado {'demo' if origen_demo else 'official'}">{html_lib.escape(provenance)}</span></div>
    <div style="margin-top:8px; color:var(--muted)">
      La verificación confirma estructura y reglas de calidad. No convierte una semilla
      de demostración en una estadística oficial.
    </div>
  </div>
</main>
<footer>Cerebro Buenos Aires · {'DEMO NO OFICIAL · fuentes de referencia: BA Data' if origen_demo else f'datos oficiales descargados de BA Data e IDECBA (Censo {anio_poblacion})'}</footer>
<script>
function setMode(mode) {{
  var isTasas = (mode === 'tasas');
  document.getElementById('panel-totales').classList.toggle('active', !isTasas);
  document.getElementById('panel-tasas').classList.toggle('active', isTasas);
  var btnTot = document.getElementById('btn-totales');
  var btnTas = document.getElementById('btn-tasas');
  btnTot.classList.toggle('active', !isTasas);
  btnTas.classList.toggle('active', isTasas);
  btnTot.setAttribute('aria-selected', !isTasas ? 'true' : 'false');
  btnTas.setAttribute('aria-selected', isTasas ? 'true' : 'false');
}}
</script>
</body>
</html>"""

    output = APP / "index.html"
    atomic_write_text(output, html)
    print(f"[ok] Dashboard -> {display_path(output)}  ({len(html):,} bytes)")
    print("     Totales: " + ", ".join(
        f"{etiquetas.get(k, k)}={format_value(k, total[k])}" for k in indicadores
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
