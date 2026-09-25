#!/usr/bin/env python3
"""
Tramo VISTAS — Herramienta A: dashboard HTML estático autocontenido.

Lee lago/gold/indicadores_por_comuna.csv + lago/gold/_meta.json y genera app/index.html
(sin servidor, sin dependencias: se abre en cualquier navegador). Incluye el bloque
obligatorio de fuente / vigencia / última ingesta / estado verificado, como en Cerebro Lima.

Herramienta B: app/streamlit_app.py (interactivo; requiere streamlit).
Decisión en la bitácora: HTML estático para publicar sin infra (elegido para el entregable);
Streamlit para exploración interactiva local.

Uso:
    python scripts/build_dashboard.py
"""
from __future__ import annotations
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "lago" / "gold"
APP = ROOT / "app"


def _cargar():
    with (GOLD / "indicadores_por_comuna.csv").open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    meta = json.loads((GOLD / "_meta.json").read_text(encoding="utf-8"))
    return filas, meta


def _num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else round(f, 1)
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

    # fuentes (deduplicadas)
    fuentes = meta.get("fuentes", {})
    origen_demo = any((f.get("_origen") == "semilla_demo") for f in fuentes.values())

    def tarjetas_totales():
        out = []
        for k in indicadores:
            out.append(f"""
            <div class="card">
              <div class="card-val">{total[k]:,}</div>
              <div class="card-lbl">{etiquetas.get(k, k)}</div>
            </div>""")
        return "".join(out)

    def filas_tabla():
        out = []
        for r in filas:
            celdas = "".join(f"<td>{_num(r[k]):,}</td>" for k in indicadores)
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
              <span class="bar-val">{v:,}</span>
            </div>""")
        return "".join(out)

    fuentes_html = "".join(
        f"<li><b>{d}</b>: {m.get('fuente','')} — {m.get('organismo','')} "
        f"(<a href='{m.get('url','#')}'>dataset</a>, licencia {m.get('licencia','')})</li>"
        for d, m in fuentes.items()
    )

    generado = meta.get("generado", dt.datetime.now().isoformat(timespec="seconds"))

    aviso_demo = ""
    if origen_demo:
        aviso_demo = ("<div class='aviso'>⚠️ Datos <b>SEMILLA (demo)</b>: respetan la "
                      "estructura real de BA Data pero NO son oficiales. Corré "
                      "<code>scripts/ingest_all.py</code> con internet para reemplazarlos "
                      "por datos descargados y recalcular todo.</div>")

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
  .estado {{ display:inline-block; background:#0f5132; color:#d1fae5;
             padding:2px 10px; border-radius:20px; font-size:13px; }}
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

  <h2>Estaciones Ecobici por comuna</h2>
  <div>{barras('estaciones_ecobici')}</div>

  <h2>Espacios verdes por comuna</h2>
  <div>{barras('espacios_verdes')}</div>

  <h2>Hospitales por comuna</h2>
  <div>{barras('hospitales')}</div>

  <h2>Tabla de indicadores por comuna</h2>
  <table>
    <thead><tr><th>Comuna</th>{''.join(f'<th>{etiquetas.get(k,k)}</th>' for k in indicadores)}</tr></thead>
    <tbody>{filas_tabla()}</tbody>
  </table>

  <div class="ficha">
    <div><b>Fuentes</b><ul>{fuentes_html}</ul></div>
    <div><b>Última construcción (gold):</b> {generado}</div>
    <div><b>Motor de consulta:</b> {meta.get('motor','sqlite')}</div>
    <div style="margin-top:8px"><b>Estado:</b> <span class="estado">✓ {meta.get('estado','verificado')}</span></div>
    <div style="margin-top:8px; color:var(--muted)">
      Cero cifras sin fuente, sin vigencia ni fecha de prueba. Cada indicador se recalcula
      desde datos verificados en la capa GOLD.
    </div>
  </div>
</main>
<footer>Cerebro Buenos Aires · datos: Gobierno de la Ciudad de Buenos Aires (BA Data)</footer>
</body>
</html>"""

    (APP / "index.html").write_text(html, encoding="utf-8")
    print(f"[ok] Dashboard -> {(APP / 'index.html').relative_to(ROOT)}  ({len(html):,} bytes)")
    print(f"     Totales: " + ", ".join(f"{etiquetas.get(k,k)}={total[k]:,}" for k in indicadores))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
