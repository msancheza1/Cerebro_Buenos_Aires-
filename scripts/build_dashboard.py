#!/usr/bin/env python3
"""
Tramo VISTAS — Herramienta A: dashboard HTML estático autocontenido.

Lee lago/gold/indicadores_por_comuna.csv + lago/gold/_meta.json y genera app/index.html
(sin servidor, sin dependencias, sin CDN: se abre en cualquier navegador). Incluye el
bloque obligatorio de fuente / vigencia / última ingesta / estado verificado, como en
Cerebro Lima.

Herramienta B: app/streamlit_app.py (interactivo; requiere streamlit).

Uso:
    python scripts/build_dashboard.py
"""
from __future__ import annotations
import _utf8  # noqa: F401  (reconfigura stdout/stderr a UTF-8; portabilidad Windows)
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "lago" / "gold"
APP = ROOT / "app"

# icono SVG (línea) por indicador — se inyecta en las tarjetas KPI
ICONOS = {
    "estaciones_ecobici": '<circle cx="7" cy="17" r="3"/><circle cx="17" cy="17" r="3"/><path d="M7 17l3-6h4l3 6M10 11l2-4h3"/>',
    "km_ciclovias": '<circle cx="6" cy="17" r="3"/><circle cx="18" cy="17" r="3"/><path d="M6 17l5-9 4 9M9 8h5"/>',
    "espacios_verdes": '<path d="M12 3C8 7 7 11 12 21 17 11 16 7 12 3z"/><path d="M12 10v11"/>',
    "m2_espacios_verdes": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 10h16M10 4v16"/>',
    "hospitales": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M12 8v8M8 12h8"/>',
}


def _cargar():
    with (GOLD / "indicadores_por_comuna.csv").open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    meta = json.loads((GOLD / "_meta.json").read_text(encoding="utf-8"))
    return filas, meta


def _centroides_comunas() -> dict:
    """{comuna: [lon, lat]} desde gold/comunas.geojson (Point o Polygon/MultiPolygon)."""
    p = GOLD / "comunas.geojson"
    if not p.exists():
        return {}
    gj = json.loads(p.read_text(encoding="utf-8"))

    def _coords_planas(geom):
        t = geom.get("type")
        c = geom.get("coordinates", [])
        if t == "Point":
            return [c]
        if t in ("LineString", "MultiPoint"):
            return c
        if t in ("Polygon", "MultiLineString"):
            return [pt for ring in c for pt in ring]
        if t == "MultiPolygon":
            return [pt for poly in c for ring in poly for pt in ring]
        return []

    out = {}
    for feat in gj.get("features", []):
        comuna = feat.get("properties", {}).get("comuna")
        pts = _coords_planas(feat.get("geometry", {}))
        if comuna is None or not pts:
            continue
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        out[int(comuna)] = [round(lon, 6), round(lat, 6)]
    return out


def _poligonos_comunas() -> dict:
    """{comuna: [[[lon,lat],...], ...]} anillos exteriores, SOLO si el geojson trae áreas.

    Con datos semilla (Point) devuelve {} y el dashboard usa Voronoi. Con polígonos
    reales (Polygon/MultiPolygon) devuelve TODOS los anillos exteriores de cada
    comuna (una comuna puede tener varias piezas), para pintar su forma auténtica.
    """
    p = GOLD / "comunas.geojson"
    if not p.exists():
        return {}
    gj = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for feat in gj.get("features", []):
        comuna = feat.get("properties", {}).get("comuna")
        geom = feat.get("geometry", {})
        t = geom.get("type")
        c = geom.get("coordinates", [])
        anillos = []
        if t == "Polygon" and c:
            anillos = [c[0]]
        elif t == "MultiPolygon" and c:
            anillos = [poly[0] for poly in c if poly]
        if comuna is not None and anillos:
            out[int(comuna)] = [
                [[round(x, 6), round(y, 6)] for x, y in anillo]
                for anillo in anillos
            ]
    return out


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

    total = {k: sum(_num(r[k]) for r in filas) for k in indicadores}
    maxv = {k: max((_num(r[k]) for r in filas), default=1) or 1 for k in indicadores}

    etiquetas = {
        "estaciones_ecobici": "Estaciones Ecobici",
        "km_ciclovias": "Km de ciclovías",
        "espacios_verdes": "Espacios verdes",
        "m2_espacios_verdes": "m² de espacios verdes",
        "hospitales": "Hospitales",
    }

    centroides = _centroides_comunas()
    poligonos = _poligonos_comunas()
    # geojson completo (para el mapa real con Leaflet). Puede ser None si no existe.
    geojson_path = GOLD / "comunas.geojson"
    geojson_comunas = (json.loads(geojson_path.read_text(encoding="utf-8"))
                       if geojson_path.exists() else None)
    datos_js = {
        "indicadores": indicadores,
        "etiquetas": {k: etiquetas.get(k, k) for k in indicadores},
        "maximos": {k: maxv[k] for k in indicadores},
        "centroides": centroides,
        "poligonos": poligonos,
        "geojson": geojson_comunas,          # FeatureCollection con comuna + barrios
        "comunas": [
            {"comuna": int(r["comuna"]), **{k: _num(r[k]) for k in indicadores}}
            for r in filas
        ],
    }
    datos_json = json.dumps(datos_js, ensure_ascii=False)

    fuentes = meta.get("fuentes", {})
    origen_demo = any((f.get("_origen") == "semilla_demo") for f in fuentes.values())

    # ---------- fragmentos HTML ----------
    def tarjetas_totales():
        out = []
        for k in indicadores:
            icono = ICONOS.get(k, '<circle cx="12" cy="12" r="8"/>')
            out.append(f"""
          <article class="kpi">
            <div class="kpi-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{icono}</svg></div>
            <div class="kpi-body">
              <div class="kpi-val" data-count="{total[k]}">{total[k]:,}</div>
              <div class="kpi-lbl">{etiquetas.get(k, k)}</div>
            </div>
          </article>""")
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
        f"(<a href='{m.get('url','#')}' target='_blank' rel='noopener'>dataset</a>, "
        f"licencia {m.get('licencia','')})</li>"
        for d, m in fuentes.items()
    )

    generado = meta.get("generado", dt.datetime.now().isoformat(timespec="seconds"))

    linaje = meta.get("linaje", {})
    indicador_dominio = meta.get("indicador_dominio", {})

    def _sha_corto(s):
        return (s[:12] + "…") if s else "—"

    if linaje:
        filas_linaje = "".join(
            f"<tr><td class='com'>{d}</td>"
            f"<td class='l'><code>{l.get('raw_file','')}</code></td>"
            f"<td class='l'><code title='{l.get('raw_sha256','')}'>{_sha_corto(l.get('raw_sha256'))}</code></td>"
            f"<td>{l.get('filas_salida','—')}</td>"
            f"<td>{l.get('filas_descartadas','—')}</td></tr>"
            for d, l in linaje.items()
        )
        ind_dom = "".join(
            f"<li><b>{etiquetas.get(k,k)}</b> <span class='arrow'>←</span> "
            f"<code>{v}</code></li>"
            for k, v in indicador_dominio.items()
        )
        linaje_html = f"""
    <section class="panel reveal">
      <h2><span class="h2-ico">🧬</span> Linaje de datos</h2>
      <p class="panel-note">Cada indicador se rastrea hasta el archivo crudo (BRONZE) y su
         huella SHA-256. Trazabilidad <b>GOLD ← SILVER ← RAW</b>.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Dominio</th><th class="l">Archivo RAW</th><th class="l">SHA-256 (raw)</th>
            <th>Filas publicadas</th><th>Filas descartadas</th></tr></thead>
          <tbody>{filas_linaje}</tbody>
        </table>
      </div>
      <div class="ind-dom"><b>Indicadores → origen</b><ul>{ind_dom}</ul></div>
    </section>"""
    else:
        linaje_html = ""

    aviso_demo = ""
    if origen_demo:
        aviso_demo = ("<div class='aviso reveal'><span class='aviso-ico'>⚠️</span><div>"
                      "<b>Datos SEMILLA (demo)</b> — respetan la estructura real de BA Data "
                      "pero NO son oficiales. Corré <code>scripts/ingest_all.py</code> con "
                      "internet para reemplazarlos y recalcular todo.</div></div>")

    estado = meta.get("estado", "verificado")

    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cerebro Buenos Aires · panel urbano por comuna</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
      integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<style>
{_CSS}
</style>
</head>
<body>
<div class="bg-grid" aria-hidden="true"></div>
<header class="hero">
  <div class="hero-inner">
    <div class="badge">Gobernanza de datos · CABA</div>
    <h1><span class="brain">🧠</span> Cerebro <span class="grad">Buenos Aires</span></h1>
    <p class="sub">Infraestructura y servicios urbanos por comuna. Réplica del ejemplo
       <a href="https://cerebro-lima.vercel.app/" target="_blank" rel="noopener">Cerebro Lima</a>,
       construida con arquitectura medallón (bronce → plata → oro).</p>
    <div class="chips">
      <span class="chip chip-ok">✓ {estado}</span>
      <span class="chip">{len(indicadores)} indicadores</span>
      <span class="chip">15 comunas</span>
      <span class="chip">actualizado {generado[:10]}</span>
    </div>
  </div>
</header>

<main>
  {aviso_demo}

  <section class="kpis reveal">{tarjetas_totales()}</section>

  <section class="panel reveal">
    <div class="panel-head">
      <h2><span class="h2-ico">🗺️</span> Mapa por comuna</h2>
      <div class="controls">
        <label for="mapSel">Indicador</label>
        <select id="mapSel"></select>
      </div>
    </div>
    <div id="mapLeaflet" class="map-leaflet"></div>
    <div class="map-wrap" id="mapFallback" style="display:none">
      <svg id="mapSvg" class="map-svg" viewBox="0 0 680 560" role="img"
           aria-label="Mapa de indicadores por comuna de Buenos Aires">
        <defs>
          <linearGradient id="rio" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#0b1a24"/>
            <stop offset="55%" stop-color="#0e2a3a"/>
            <stop offset="100%" stop-color="#12506b"/>
          </linearGradient>
          <filter id="sombraCiudad" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="6" stdDeviation="7" flood-color="#000" flood-opacity="0.55"/>
          </filter>
        </defs>
      </svg>
    </div>
    <div class="legend">
      <span>menos</span><span class="legend-bar"></span><span>más</span>
      <span id="mapNota" class="legend-note"></span>
    </div>
  </section>

  <section class="panel reveal">
    <div class="panel-head">
      <h2><span class="h2-ico">⚖️</span> Comparador de comunas</h2>
      <div class="controls">
        <label>A</label><select id="cmpA"></select>
        <span class="vs">vs</span>
        <label>B</label><select id="cmpB"></select>
      </div>
    </div>
    <div id="cmpBody" class="cmp-body"></div>
  </section>

  <section class="panel reveal">
    <h2><span class="h2-ico">📊</span> Rankings por comuna</h2>
    <div class="grid-3">
      <div class="rank-card">
        <h3>Estaciones Ecobici</h3>
        <div class="bars">{barras('estaciones_ecobici')}</div>
      </div>
      <div class="rank-card">
        <h3>Espacios verdes</h3>
        <div class="bars">{barras('espacios_verdes')}</div>
      </div>
      <div class="rank-card">
        <h3>Hospitales</h3>
        <div class="bars">{barras('hospitales')}</div>
      </div>
    </div>
  </section>

  <section class="panel reveal">
    <h2><span class="h2-ico">📋</span> Tabla de indicadores por comuna</h2>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Comuna</th>{''.join(f'<th>{etiquetas.get(k,k)}</th>' for k in indicadores)}</tr></thead>
        <tbody>{filas_tabla()}</tbody>
      </table>
    </div>
  </section>

  {linaje_html}

  <section class="panel reveal ficha">
    <h2><span class="h2-ico">📑</span> Fuente · vigencia · estado</h2>
    <div class="ficha-grid">
      <div>
        <b>Fuentes</b>
        <ul>{fuentes_html}</ul>
      </div>
      <div class="ficha-meta">
        <div><span class="k">Última construcción (gold)</span><span class="v">{generado}</span></div>
        <div><span class="k">Motor de consulta</span><span class="v">{meta.get('motor','sqlite')}</span></div>
        <div><span class="k">Estado</span><span class="chip chip-ok">✓ {estado}</span></div>
      </div>
    </div>
    <p class="panel-note">Cero cifras sin fuente, sin vigencia ni fecha de prueba.
       Cada indicador se recalcula desde datos verificados en la capa GOLD.</p>
  </section>
</main>

<footer>
  <span class="brain">🧠</span> Cerebro Buenos Aires · datos: Gobierno de la Ciudad de
  Buenos Aires (BA Data) · panel estático sin dependencias
</footer>

<div class="tip" id="tip"></div>
<script>
const DATA = {datos_json};
{_JS}
</script>
</body>
</html>"""

    (APP / "index.html").write_text(html, encoding="utf-8")
    print(f"[ok] Dashboard -> {(APP / 'index.html').relative_to(ROOT)}  ({len(html):,} bytes)")
    print("     Totales: " + ", ".join(f"{etiquetas.get(k,k)}={total[k]:,}" for k in indicadores))
    return 0


# ===================== CSS (rediseño visual) =====================
_CSS = r"""
  :root{
    --bg:#0a0e14; --bg2:#0e141d; --card:#141b26; --card2:#182230;
    --line:#243143; --fg:#eef3f8; --muted:#93a1b3;
    --acc:#4cc9f0; --acc2:#80ffdb; --acc3:#b388ff;
    --grad:linear-gradient(135deg,#4cc9f0,#80ffdb);
    --shadow:0 10px 30px rgba(0,0,0,.35);
    --r:16px;
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{
    margin:0; color:var(--fg); background:var(--bg);
    font-family:'Inter',system-ui,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
    line-height:1.5; -webkit-font-smoothing:antialiased;
  }
  .bg-grid{
    position:fixed; inset:0; z-index:-1; pointer-events:none;
    background:
      radial-gradient(900px 500px at 80% -10%, rgba(76,201,240,.14), transparent 60%),
      radial-gradient(700px 500px at 0% 0%, rgba(179,136,255,.10), transparent 55%),
      linear-gradient(180deg,var(--bg),var(--bg2));
  }
  a{color:var(--acc); text-decoration:none}
  a:hover{text-decoration:underline}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
       background:rgba(255,255,255,.05); padding:1px 6px; border-radius:6px; font-size:.86em}

  /* ---------- hero ---------- */
  .hero{padding:64px 24px 36px; border-bottom:1px solid var(--line);
        background:linear-gradient(180deg,rgba(76,201,240,.06),transparent)}
  .hero-inner{max-width:1120px; margin:0 auto}
  .badge{display:inline-block; font-size:12px; letter-spacing:.14em; text-transform:uppercase;
         color:var(--acc2); border:1px solid var(--line); background:rgba(128,255,218,.06);
         padding:5px 12px; border-radius:999px; margin-bottom:18px}
  h1{margin:0; font-size:clamp(30px,5vw,52px); font-weight:800; letter-spacing:-.02em; line-height:1.05}
  h1 .brain{filter:drop-shadow(0 2px 12px rgba(76,201,240,.5))}
  .grad{background:var(--grad); -webkit-background-clip:text; background-clip:text; color:transparent}
  .sub{color:var(--muted); max-width:720px; margin:14px 0 0; font-size:17px}
  .chips{display:flex; flex-wrap:wrap; gap:9px; margin-top:22px}
  .chip{font-size:13px; color:var(--fg); border:1px solid var(--line);
        background:var(--card); padding:5px 12px; border-radius:999px}
  .chip-ok{color:#07160f; background:var(--acc2); border-color:transparent; font-weight:700}

  /* ---------- layout ---------- */
  main{max-width:1120px; margin:0 auto; padding:28px 24px 10px}
  .panel{background:linear-gradient(180deg,var(--card),var(--card2));
         border:1px solid var(--line); border-radius:var(--r); padding:22px 22px 24px;
         margin:20px 0; box-shadow:var(--shadow)}
  .panel-head{display:flex; justify-content:space-between; align-items:center;
              flex-wrap:wrap; gap:12px; margin-bottom:8px}
  h2{font-size:19px; margin:0 0 10px; display:flex; align-items:center; gap:10px; font-weight:700}
  .h2-ico{font-size:20px}
  .panel-note{color:var(--muted); font-size:14px; margin:10px 0 0}

  /* ---------- aviso ---------- */
  .aviso{display:flex; gap:12px; align-items:flex-start;
         background:linear-gradient(180deg,rgba(255,196,0,.10),rgba(255,196,0,.03));
         border:1px solid #6b5200; color:#ffe08a; padding:14px 16px; border-radius:var(--r);
         margin:20px 0; font-size:14px}
  .aviso-ico{font-size:18px; line-height:1}
  .aviso b{color:#ffd166}

  /* ---------- KPIs ---------- */
  .kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:16px; margin:4px 0 6px}
  .kpi{display:flex; gap:14px; align-items:center;
       background:linear-gradient(180deg,var(--card),var(--card2));
       border:1px solid var(--line); border-radius:var(--r); padding:18px;
       box-shadow:var(--shadow); transition:transform .18s, border-color .18s}
  .kpi:hover{transform:translateY(-4px); border-color:var(--acc)}
  .kpi-ico{flex:0 0 46px; width:46px; height:46px; border-radius:12px;
           display:grid; place-items:center; color:#07160f; background:var(--grad)}
  .kpi-ico svg{width:24px; height:24px}
  .kpi-val{font-size:26px; font-weight:800; letter-spacing:-.02em;
           background:var(--grad); -webkit-background-clip:text; background-clip:text; color:transparent}
  .kpi-lbl{color:var(--muted); font-size:13px; margin-top:2px}

  /* ---------- controles ---------- */
  .controls{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
  .controls label{color:var(--muted); font-size:13px}
  select{background:var(--bg2); color:var(--fg); border:1px solid var(--line);
         border-radius:10px; padding:9px 12px; font-size:14px; cursor:pointer;
         transition:border-color .15s}
  select:hover,select:focus{border-color:var(--acc); outline:none}
  .vs{color:var(--muted); font-size:13px; font-style:italic}

  /* ---------- mapa ---------- */
  .map-leaflet{height:560px; width:100%; border-radius:12px; border:1px solid var(--line);
               overflow:hidden; z-index:0}
  .leaflet-container{background:#0b1a24; font-family:inherit}
  .leaflet-popup-content-wrapper,.leaflet-tooltip{
    background:#0a111b; color:var(--fg); border:1px solid var(--acc);
    border-radius:10px; box-shadow:var(--shadow)}
  .leaflet-tooltip{font-size:13px; padding:8px 11px}
  .leaflet-tooltip-top:before,.leaflet-tooltip-bottom:before{border-top-color:var(--acc)}
  .leaflet-control-attribution{background:rgba(10,17,27,.8)!important; color:var(--muted)!important}
  .leaflet-control-attribution a{color:var(--acc)!important}
  .leaflet-bar a{background:var(--card)!important; color:var(--fg)!important; border-color:var(--line)!important}
  .com-tip b{color:var(--acc2)}
  .com-tip .barrios{color:var(--muted); font-size:12px; margin-top:3px; max-width:220px}
  .com-tip .val{margin-top:5px; font-size:14px}
  .map-wrap{border-radius:12px; overflow:hidden; padding:0; border:1px solid var(--line);
            background:#0b1a24}
  .map-svg{width:100%; height:auto; display:block; max-height:600px; margin:0 auto}
  .map-cell{cursor:pointer; transition:fill .25s, filter .15s, opacity .15s}
  .map-cell:hover{filter:brightness(1.22) drop-shadow(0 0 12px rgba(128,255,218,.6));
                  stroke:#fff!important; stroke-width:1.8!important}
  .map-lbl{font-size:13px; font-weight:800; pointer-events:none;
           font-variant-numeric:tabular-nums; letter-spacing:.3px}
  .map-labelg{opacity:.96; transition:opacity .15s}
  .map-cell:hover + .map-labelg,.map-labelg:hover{opacity:1}
  .legend{display:flex; align-items:center; gap:9px; color:var(--muted); font-size:12px; margin-top:12px}
  .legend-bar{height:12px; width:200px; border-radius:999px;
              background:linear-gradient(90deg,#19243a,#296ea0,var(--acc),var(--acc2))}
  .legend-note{margin-left:auto; font-style:italic}

  /* ---------- comparador ---------- */
  .cmp-body{display:flex; flex-direction:column; gap:14px; margin-top:6px}
  .cmp-item{}
  .cmp-top{display:flex; justify-content:space-between; font-size:13px; color:var(--muted); margin-bottom:5px}
  .cmp-top .va{color:var(--acc)} .cmp-top .vb{color:var(--acc3)}
  .cmp-bar{display:flex; height:22px; border-radius:999px; overflow:hidden; background:var(--bg2); border:1px solid var(--line)}
  .cmp-a{background:linear-gradient(90deg,#2a6f8a,var(--acc)); height:100%}
  .cmp-b{background:linear-gradient(90deg,var(--acc3),#6a4ba8); height:100%; margin-left:auto}
  .cmp-name{font-size:13px; color:var(--fg); margin-bottom:4px; font-weight:600}

  /* ---------- rankings ---------- */
  .grid-3{display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:18px; margin-top:6px}
  .rank-card h3{margin:0 0 10px; font-size:14px; color:var(--acc2); font-weight:700}
  .bars{display:flex; flex-direction:column; gap:5px}
  .bar-row{display:grid; grid-template-columns:74px 1fr 52px; align-items:center; gap:10px; font-size:12.5px}
  .bar-lbl{color:var(--muted)}
  .bar-track{background:var(--bg2); border-radius:999px; height:12px; overflow:hidden; border:1px solid var(--line)}
  .bar-fill{display:block; height:100%; border-radius:999px;
            background:var(--grad); transition:width .9s cubic-bezier(.2,.8,.2,1)}
  .bar-val{text-align:right; color:var(--fg); font-variant-numeric:tabular-nums}

  /* ---------- tablas ---------- */
  .table-wrap{overflow-x:auto; border-radius:12px; border:1px solid var(--line)}
  table{width:100%; border-collapse:collapse; font-size:13.5px}
  thead th{position:sticky; top:0; background:var(--bg2); color:var(--muted);
           font-weight:600; text-align:right; padding:11px 12px; white-space:nowrap}
  tbody td{padding:10px 12px; text-align:right; border-top:1px solid var(--line);
           font-variant-numeric:tabular-nums}
  td.com,th:first-child{text-align:left}
  .l,td.l,th.l{text-align:left!important}
  tbody tr:nth-child(even){background:rgba(255,255,255,.015)}
  tbody tr:hover{background:rgba(76,201,240,.07)}
  .ind-dom{margin-top:16px; font-size:14px}
  .ind-dom ul{margin:8px 0 0; padding-left:18px; columns:2; color:var(--muted)}
  .ind-dom .arrow{color:var(--acc)}

  /* ---------- ficha ---------- */
  .ficha-grid{display:grid; grid-template-columns:2fr 1fr; gap:22px; margin-top:4px}
  @media (max-width:720px){.ficha-grid{grid-template-columns:1fr}}
  .ficha ul{margin:8px 0 0; padding-left:18px; font-size:14px; color:var(--muted)}
  .ficha ul b{color:var(--fg)}
  .ficha-meta{display:flex; flex-direction:column; gap:12px}
  .ficha-meta>div{display:flex; flex-direction:column; gap:3px}
  .ficha-meta .k{color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em}
  .ficha-meta .v{color:var(--fg); font-size:14px}

  /* ---------- footer / tooltip / anim ---------- */
  footer{color:var(--muted); font-size:13px; text-align:center; padding:34px 24px 44px;
         border-top:1px solid var(--line); margin-top:24px}
  .tip{position:fixed; pointer-events:none; background:#060b11; border:1px solid var(--acc);
       color:var(--fg); font-size:12.5px; padding:8px 11px; border-radius:9px; opacity:0;
       transition:opacity .12s; z-index:20; box-shadow:var(--shadow)}
  .reveal{opacity:0; transform:translateY(16px); animation:rise .6s ease forwards}
  .reveal:nth-child(2){animation-delay:.05s}
  .reveal:nth-child(3){animation-delay:.1s}
  .reveal:nth-child(4){animation-delay:.15s}
  @keyframes rise{to{opacity:1; transform:none}}
  @media (prefers-reduced-motion:reduce){.reveal{animation:none; opacity:1; transform:none}}
"""

# ===================== JS (mapa + comparador) =====================
_JS = r"""
const svgNS="http://www.w3.org/2000/svg";
const W=680,H=560,PAD=24;

// bbox dinámico: si hay polígonos reales, encuadra su extensión; si no, usa CABA
function calcBBox(){
  const poly=DATA.poligonos||{};
  if(Object.keys(poly).length){
    let minx=1e9,miny=1e9,maxx=-1e9,maxy=-1e9;
    for(const k in poly) for(const ring of poly[k]) for(const [lo,la] of ring){
      if(lo<minx)minx=lo; if(lo>maxx)maxx=lo; if(la<miny)miny=la; if(la>maxy)maxy=la;
    }
    return {minx,miny,maxx,maxy};
  }
  return {minx:-58.54,maxx:-58.33,miny:-34.71,maxy:-34.52};
}
const BB=calcBBox();
// escala uniforme para no deformar la ciudad
const sx=(W-2*PAD)/(BB.maxx-BB.minx), sy=(H-2*PAD)/(BB.maxy-BB.miny);
const S=Math.min(sx,sy);
const offx=PAD+((W-2*PAD)-S*(BB.maxx-BB.minx))/2;
const offy=PAD+((H-2*PAD)-S*(BB.maxy-BB.miny))/2;
function proj(lon,lat){
  const x=offx+(lon-BB.minx)*S;
  const y=offy+(BB.maxy-lat)*S;   // lat invertida (norte arriba)
  return [x,y];
}
function color(t){
  t=Math.max(0,Math.min(1,t));
  const stops=[[25,36,58],[41,110,160],[76,201,240],[128,255,218]];
  const s=t*(stops.length-1); const i=Math.min(Math.floor(s),stops.length-2);
  const u=s-i; const a=stops[i],b=stops[i+1];
  const c=a.map((v,k)=>Math.round(v+(b[k]-v)*u));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}
const fmt=n=>Number(n).toLocaleString('es-AR');
const valor=(comuna,ind)=>{const r=DATA.comunas.find(x=>x.comuna===comuna);return r?(r[ind]||0):0;};
// centroide de ÁREA (fórmula del polígono) del anillo más grande -> cae dentro de la forma
const centro=poly=>{
  const big=poly.reduce((a,b)=>b.length>a.length?b:a,poly[0]);
  let a=0,cx=0,cy=0;
  for(let i=0;i<big.length-1;i++){
    const [x0,y0]=big[i],[x1,y1]=big[i+1];
    const f=x0*y1-x1*y0; a+=f; cx+=(x0+x1)*f; cy+=(y0+y1)*f;
  }
  if(Math.abs(a)<1e-6){ // degenerado: promedio simple
    let sx=0,sy=0; for(const p of big){sx+=p[0];sy+=p[1];} return [sx/big.length,sy/big.length];
  }
  a*=0.5; return [cx/(6*a), cy/(6*a)];
};
// luminancia relativa de un color rgb(...) -> para decidir texto claro u oscuro
const esClaro=rgb=>{
  const m=rgb.match(/\d+/g).map(Number);
  const L=(0.299*m[0]+0.587*m[1]+0.114*m[2])/255;
  return L>0.6;
};
const pathAnillo=ring=>ring.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ')+' Z';

/* ---------- silueta/Voronoi: solo fallback sin polígonos reales ---------- */
function siluetaCABA(){
  const pts=[[0.46,0],[0.70,0.03],[0.86,0.12],[0.95,0.26],[0.98,0.42],[0.93,0.58],
    [0.86,0.72],[0.72,0.86],[0.55,0.96],[0.44,1],[0.36,0.92],[0.30,0.80],
    [0.20,0.72],[0.10,0.60],[0.05,0.46],[0.07,0.30],[0.16,0.16],[0.30,0.06]];
  return pts.map(([u,v])=>[PAD+u*(W-2*PAD),PAD+v*(H-2*PAD)]);
}
function clipHalfPlane(poly,a,b){
  const mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2,nx=b[0]-a[0],ny=b[1]-a[1];
  const inside=p=>(nx*(p[0]-mx)+ny*(p[1]-my))<=0;
  const inter=(p,q)=>{const d1=nx*(p[0]-mx)+ny*(p[1]-my),d2=nx*(q[0]-mx)+ny*(q[1]-my);const t=d1/(d1-d2);return [p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])];};
  const out=[];
  for(let i=0;i<poly.length;i++){const cur=poly[i],prev=poly[(i+poly.length-1)%poly.length];const ci=inside(cur),pi=inside(prev);
    if(ci){if(!pi)out.push(inter(prev,cur));out.push(cur);}else if(pi){out.push(inter(prev,cur));}}
  return out;
}
function celdaVoronoi(sitio,sitios,clip){let poly=clip.slice();for(const o of sitios){if(o===sitio)continue;poly=clipHalfPlane(poly,sitio,o);if(poly.length<3)break;}return poly;}
const pathDe=poly=>poly.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ')+' Z';

/* ========================= MAPA REAL (Leaflet) ========================= */
let _lmap=null, _llayer=null;
function initLeaflet(){
  if(typeof L==="undefined" || !DATA.geojson) return false;
  try{
    _lmap=L.map("mapLeaflet",{zoomControl:true,scrollWheelZoom:false,attributionControl:true})
          .setView([-34.61,-58.44],11);
    const satelite=L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {maxZoom:19, attribution:'Imágenes &copy; Esri, Maxar, Earthstar Geographics'});
    const calles=L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
      {maxZoom:19, attribution:'&copy; Esri, HERE, Garmin, OpenStreetMap contributors'});
    satelite.addTo(_lmap);
    // etiquetas de calles/lugares encima del satélite
    const refSat=L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      {maxZoom:19, opacity:0.9});
    refSat.addTo(_lmap);
    L.control.layers(
      {"Satélite":satelite, "Calles":calles},
      {},
      {position:"topright", collapsed:false}
    ).addTo(_lmap);
    return true;
  }catch(e){ return false; }
}
function estiloComuna(feature, ind){
  const c=feature.properties.comuna;
  const v=valor(c,ind), max=DATA.maximos[ind]||1, t=v/max;
  return {fillColor:color(t), fillOpacity:0.55, color:"#ffffff", weight:1.2, opacity:0.85};
}
function pintarLeaflet(ind){
  if(_llayer){ _lmap.removeLayer(_llayer); _llayer=null; }
  _llayer=L.geoJSON(DATA.geojson,{
    style:f=>estiloComuna(f,ind),
    onEachFeature:(f,layer)=>{
      const c=f.properties.comuna, v=valor(c,ind);
      const barrios=f.properties.barrios||"";
      layer.bindTooltip(
        `<div class="com-tip"><b>Comuna ${c}</b>`+
        (barrios?`<div class="barrios">${barrios}</div>`:``)+
        `<div class="val">${DATA.etiquetas[ind]}: <b>${fmt(v)}</b></div></div>`,
        {sticky:true}
      );
      layer.on("mouseover",()=>layer.setStyle({weight:3,color:"#80ffdb",fillOpacity:0.72}));
      layer.on("mouseout",()=>_llayer.resetStyle(layer));
    }
  }).addTo(_lmap);
  try{ _lmap.fitBounds(_llayer.getBounds(),{padding:[12,12]}); }catch(e){}
  document.getElementById("mapNota").textContent=
    "mapa real · satélite/calles Esri + coroplético de comunas (BA Data)";
}

function dibujarMapa(ind){
  const svg=document.getElementById("mapSvg");
  // limpiar todo menos <defs> (gradiente del río + filtro de sombra)
  [...svg.childNodes].forEach(n=>{ if(!(n.nodeName&&n.nodeName.toLowerCase()==="defs")) svg.removeChild(n); });
  const max=DATA.maximos[ind]||1; const tip=document.getElementById("tip");
  const poly=DATA.poligonos||{}; const usarPoly=Object.keys(poly).length>0;

  function pintarComuna(comuna, dPath, cx, cy, parent){
    const host = parent || svg;
    const v=valor(comuna,ind), t=v/max;
    const col=color(t);
    const cell=document.createElementNS(svgNS,"path");
    cell.setAttribute("class","map-cell"); cell.setAttribute("d",dPath);
    cell.setAttribute("fill",col);
    cell.setAttribute("stroke","rgba(5,8,12,.75)"); cell.setAttribute("stroke-width","0.8");
    cell.setAttribute("stroke-linejoin","round");
    cell.addEventListener("mousemove",e=>{
      tip.style.opacity=1; tip.style.left=(e.clientX+14)+"px"; tip.style.top=(e.clientY+14)+"px";
      tip.innerHTML=`<b>Comuna ${comuna}</b><br>${DATA.etiquetas[ind]}: <b>${fmt(v)}</b>`;
    });
    cell.addEventListener("mouseleave",()=>tip.style.opacity=0);
    host.appendChild(cell);
    // etiqueta: pill de fondo + número grande (SIEMPRE sobre el svg, sin sombra)
    const g=document.createElementNS(svgNS,"g");
    g.setAttribute("class","map-labelg"); g.setAttribute("pointer-events","none");
    const txt=String(comuna);
    const wPill=txt.length>1?26:20, hPill=18;
    const rect=document.createElementNS(svgNS,"rect");
    rect.setAttribute("x",cx-wPill/2); rect.setAttribute("y",cy-hPill/2);
    rect.setAttribute("width",wPill); rect.setAttribute("height",hPill);
    rect.setAttribute("rx",9);
    rect.setAttribute("fill", esClaro(col) ? "rgba(6,16,24,.78)" : "rgba(255,255,255,.14)");
    rect.setAttribute("stroke", esClaro(col) ? "rgba(255,255,255,.25)" : "rgba(255,255,255,.3)");
    rect.setAttribute("stroke-width","1");
    g.appendChild(rect);
    const lbl=document.createElementNS(svgNS,"text");
    lbl.setAttribute("class","map-lbl");
    lbl.setAttribute("x",cx); lbl.setAttribute("y",cy);
    lbl.setAttribute("text-anchor","middle");
    lbl.setAttribute("dominant-baseline","central");
    lbl.setAttribute("fill","#ffffff");
    lbl.textContent=txt;
    g.appendChild(lbl);
    svg.appendChild(g);
  }

  if(usarPoly){
    // --- agua de fondo (Río de la Plata al este/noreste) ---
    const agua=document.createElementNS(svgNS,"rect");
    agua.setAttribute("x",0);agua.setAttribute("y",0);
    agua.setAttribute("width",W);agua.setAttribute("height",H);
    agua.setAttribute("fill","url(#rio)");
    svg.appendChild(agua);

    // --- capa de ciudad con sombra (todas las comunas dentro de un grupo) ---
    const ciudad=document.createElementNS(svgNS,"g");
    ciudad.setAttribute("filter","url(#sombraCiudad)");
    svg.appendChild(ciudad);

    // contorno exterior unificado (silueta de CABA) debajo, para el "borde de costa"
    DATA.comunas.forEach(row=>{
      const anillos=poly[row.comuna]; if(!anillos) return;
      const proyectados=anillos.map(r=>r.map(([lo,la])=>proj(lo,la)));
      const dPath=proyectados.map(pathAnillo).join(' ');
      const [cx,cy]=centro(proyectados);
      pintarComuna(row.comuna, dPath, cx, cy, ciudad);
    });
    document.getElementById("mapNota").textContent="coroplético · polígonos oficiales de comuna (BA Data)";
  } else {
    const clip=siluetaCABA();
    const base=document.createElementNS(svgNS,"path");
    base.setAttribute("d",pathDe(clip)); base.setAttribute("fill","#0c121c");
    base.setAttribute("stroke","#2b3a52"); base.setAttribute("stroke-width","1.5"); svg.appendChild(base);
    const sitios=[],meta=[];
    DATA.comunas.forEach(row=>{const c=DATA.centroides[row.comuna];if(!c)return;const s=proj(c[0],c[1]);sitios.push(s);meta.push({row,s});});
    meta.forEach(({row,s})=>{const cell=celdaVoronoi(s,sitios,clip);if(cell.length<3)return;pintarComuna(row.comuna,pathDe(cell),s[0],s[1]);});
    document.getElementById("mapNota").textContent="coroplético aproximado (Voronoi desde centroides)";
  }
}

function dibujarComparador(){
  const a=parseInt(document.getElementById("cmpA").value);
  const b=parseInt(document.getElementById("cmpB").value);
  const cont=document.getElementById("cmpBody"); cont.innerHTML="";
  DATA.indicadores.forEach(ind=>{
    const va=valor(a,ind), vb=valor(b,ind), m=Math.max(va,vb,1);
    const pa=100*va/m, pb=100*vb/m;
    const item=document.createElement("div"); item.className="cmp-item";
    item.innerHTML=`
      <div class="cmp-name">${DATA.etiquetas[ind]}</div>
      <div class="cmp-top"><span class="va">A · Comuna ${a}: ${fmt(va)}</span>
        <span class="vb">Comuna ${b}: ${fmt(vb)} · B</span></div>
      <div class="cmp-bar">
        <span class="cmp-a" style="width:${pa/2}%"></span>
        <span class="cmp-b" style="width:${pb/2}%"></span>
      </div>`;
    cont.appendChild(item);
  });
}

(function(){
  // decide el modo de mapa: Leaflet (real) si carga; si no, SVG coroplético
  const usarLeaflet = initLeaflet();
  if(!usarLeaflet){
    document.getElementById("mapLeaflet").style.display="none";
    document.getElementById("mapFallback").style.display="";
  }
  const renderMapa = ind => usarLeaflet ? pintarLeaflet(ind) : dibujarMapa(ind);

  const sel=document.getElementById("mapSel");
  DATA.indicadores.forEach(ind=>{const o=document.createElement("option");o.value=ind;o.textContent=DATA.etiquetas[ind];sel.appendChild(o);});
  sel.addEventListener("change",()=>renderMapa(sel.value));
  const comunas=DATA.comunas.map(r=>r.comuna).sort((x,y)=>x-y);
  const cmpA=document.getElementById("cmpA"),cmpB=document.getElementById("cmpB");
  comunas.forEach(c=>{[cmpA,cmpB].forEach(s=>{const o=document.createElement("option");o.value=c;o.textContent="Comuna "+c;s.appendChild(o);});});
  cmpA.value=comunas[0]; cmpB.value=comunas[comunas.length>1?1:0];
  cmpA.addEventListener("change",dibujarComparador);
  cmpB.addEventListener("change",dibujarComparador);
  renderMapa(DATA.indicadores[0]);
  dibujarComparador();
})();
"""


if __name__ == "__main__":
    raise SystemExit(main())
