#!/usr/bin/env python3
"""
Tramo VISTAS — Herramienta A: dashboard HTML estático autocontenido.

Lee la capa GOLD configurada y genera un HTML autocontenido en el directorio APP
configurado (sin servidor ni dependencias). Incluye fuente, ingesta, calidad y procedencia.

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


def main() -> int:
    APP.mkdir(parents=True, exist_ok=True)
    filas, meta = _cargar()
    indicadores = meta["indicadores"]

    # totales y máximos por indicador (para barras)
    total = {k: sum(_num(r[k]) for r in filas) for k in indicadores}
    maxv = {k: max((_num(r[k]) for r in filas), default=1) or 1 for k in indicadores}

    etiquetas = {
        "estaciones_ecobici": "Estaciones Ecobici",
        "km_ciclovias": "Km de ciclovías",
        "espacios_verdes": "Espacios verdes",
        "m2_espacios_verdes": "m² de espacios verdes",
        "hospitales": "Hospitales",
    }

    def format_value(indicator, value):
        decimals = 2 if indicator == "km_ciclovias" else (
            1 if indicator == "m2_espacios_verdes" else 0
        )
        return f"{float(value):,.{decimals}f}"

    provenance = meta.get("provenance_status", "unknown")
    origen_demo = provenance == "demo"
    if meta.get("quality_status") != "verified":
        raise ValueError("GOLD no tiene quality_status=verified")

    def tarjetas_totales():
        out = []
        for k in indicadores:
            out.append(f"""
            <div class="card">
              <div class="card-val">{format_value(k, total[k])}</div>
              <div class="card-lbl">{etiquetas.get(k, k)}</div>
            </div>""")
        return "".join(out)

    def filas_tabla():
        out = []
        for r in filas:
            celdas = "".join(f"<td>{format_value(k, r[k])}</td>" for k in indicadores)
            out.append(f"<tr><td class='com'>Comuna {r['comuna']}</td>{celdas}</tr>")
        return "".join(out)

    def barras(indicador):
        rows = sorted(filas, key=lambda r: _num(r[indicador]), reverse=True)
        out = []
        for r in rows:
            v = _num(r[indicador])
            pct = 100 * v / maxv[indicador]
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
        f"rel='noreferrer'>dataset</a>, licencia {html_lib.escape(str(source.get('licencia', '')))}) "
        f"· ingesta {html_lib.escape(str(source.get('fecha_ingesta', 'sin fecha')))}</li>"
        for domain, source in fuentes.items()
    )
    graficos_html = "".join(
        f"<h2>{html_lib.escape(etiquetas.get(indicator, indicator))} por comuna</h2>"
        f"<div>{barras(indicator)}</div>"
        for indicator in indicadores
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
  main {{ max-width:1000px; margin:0 auto; padding:24px; }}
  .aviso {{ background:#3d2b00; border:1px solid #7a5b00; color:#ffd166;
            padding:12px 14px; border-radius:8px; margin-bottom:20px; font-size:14px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
            gap:14px; margin-bottom:28px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
           padding:18px; text-align:center; }}
  .card-val {{ font-size:30px; font-weight:700; color:var(--acc2); }}
  .card-lbl {{ color:var(--muted); font-size:13px; margin-top:4px; }}
  h2 {{ font-size:18px; border-left:3px solid var(--acc); padding-left:10px; margin-top:32px; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th,td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:right; }}
  th {{ color:var(--muted); font-weight:600; }}
  td.com, th:first-child {{ text-align:left; }}
  .bar-row {{ display:grid; grid-template-columns:90px 1fr 60px; align-items:center;
              gap:10px; margin:6px 0; font-size:13px; }}
  .bar-track {{ background:#21262d; border-radius:6px; height:14px; overflow:hidden; }}
  .bar-fill {{ display:block; height:100%;
               background:linear-gradient(90deg,var(--acc),var(--acc2)); }}
  .bar-val {{ text-align:right; color:var(--muted); }}
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
  <div class="sub">Infraestructura y servicios urbanos por comuna · réplica del ejemplo Cerebro Lima</div>
</header>
<main>
  {aviso_demo}
  <section class="cards">{tarjetas_totales()}</section>

  {graficos_html}

  <h2>Tabla de indicadores por comuna</h2>
  <table>
    <thead><tr><th>Comuna</th>{''.join(f'<th>{etiquetas.get(k,k)}</th>' for k in indicadores)}</tr></thead>
    <tbody>{filas_tabla()}</tbody>
  </table>

  <div class="ficha">
    <div><b>Fuentes</b><ul>{fuentes_html}</ul></div>
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
<footer>Cerebro Buenos Aires · {'DEMO NO OFICIAL · fuentes de referencia: BA Data' if origen_demo else 'datos descargados de BA Data'}</footer>
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
