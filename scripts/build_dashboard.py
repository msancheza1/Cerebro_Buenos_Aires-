#!/usr/bin/env python3
"""Genera el observatorio urbano HTML estático y su maqueta 3D / coroplética autocontenida.

Un mapa coroplético 3D colorea y extruye verticalmente cada comuna según el valor de un
indicador. Esta vista no usa servicios propietarios ni claves: renderiza una maqueta 3D
isométrica sobre WebGL (MapLibre GL local) con separación entre bloques, distinción entre
paredes laterales y cara superior (techo), y respaldo SVG autocontenido.
"""
from __future__ import annotations

import csv
import datetime as dt
import html as html_lib
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from pipeline_common import APP, GOLD, ROOT, atomic_write_text, display_path, resolve_reference
from prep_comunas import _simplificar_geom

MAP_WIDTH = 900
MAP_HEIGHT = 650
MAP_PADDING = 28

INDICATORS = [
    {
        "id": "ecobici",
        "total": "estaciones_ecobici",
        "rate": "estaciones_ecobici_por_10000_hab",
        "label": "Estaciones Ecobici",
        "short": "Ecobici",
        "total_unit": "estaciones",
        "rate_unit": "estaciones / 10.000 hab.",
        "factor": 10000,
    },
    {
        "id": "ciclovias",
        "total": "km_ciclovias",
        "rate": "km_ciclovias_por_10000_hab",
        "label": "Ciclovías",
        "short": "Ciclovías",
        "total_unit": "km",
        "rate_unit": "km / 10.000 hab.",
        "factor": 10000,
    },
    {
        "id": "espacios",
        "total": "espacios_verdes",
        "rate": "espacios_verdes_por_10000_hab",
        "label": "Espacios verdes",
        "short": "Espacios verdes",
        "total_unit": "espacios públicos",
        "rate_unit": "espacios / 10.000 hab.",
        "factor": 10000,
    },
    {
        "id": "superficie",
        "total": "m2_espacios_verdes",
        "rate": "m2_verdes_por_hab",
        "label": "Superficie verde",
        "short": "Superficie verde",
        "total_unit": "m²",
        "rate_unit": "m² / habitante",
        "factor": 1,
    },
    {
        "id": "hospitales",
        "total": "hospitales",
        "rate": "hospitales_por_10000_hab",
        "label": "Hospitales",
        "short": "Hospitales",
        "total_unit": "establecimientos",
        "rate_unit": "hospitales / 10.000 hab.",
        "factor": 10000,
    },
]


def _safe_url(value: str) -> str:
    parsed = urlparse(value or "")
    return value if parsed.scheme == "https" and parsed.netloc else "#"


def _num(value):
    """No confundir ausencias o valores no finitos con ceros observados."""
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Valor numérico ausente o inválido: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Valor numérico no finito: {value!r}")
    return int(number) if number.is_integer() else number


def _es(value, decimals: int = 0) -> str:
    """Formato numérico español: 3.121.707 y 14,58."""
    text = f"{float(value):,.{decimals}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _load_gold() -> tuple[list[dict], dict]:
    with (GOLD / "indicadores_por_comuna.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    metadata = json.loads((GOLD / "_meta.json").read_text(encoding="utf-8"))
    if metadata.get("quality_status") != "verified":
        raise ValueError("GOLD no tiene quality_status=verified")
    if len(rows) != 15 or {int(row["comuna"]) for row in rows} != set(range(1, 16)):
        raise ValueError("GOLD debe contener exactamente las 15 comunas")
    required = {"poblacion", "anio_poblacion"}
    required.update(item[field] for item in INDICATORS for field in ("total", "rate"))
    for row in rows:
        for field in required:
            number = _num(row.get(field))
            if number < 0:
                raise ValueError(f"Comuna {row['comuna']}: {field} negativo")
            if field in {"poblacion", "anio_poblacion"} and (number <= 0 or number != int(number)):
                raise ValueError(f"Comuna {row['comuna']}: {field} debe ser entero positivo")
    if len({row["anio_poblacion"] for row in rows}) != 1:
        raise ValueError("GOLD mezcla años censales")
    return rows, metadata


def _boundary_source(metadata: dict) -> Path:
    """Busca primero la capa trazable del lote y luego la evidencia oficial versionada."""
    if metadata.get("provenance_status") == "official":
        for source in metadata.get("fuentes", {}).values():
            for auxiliary in source.get("auxiliares", []):
                candidate = resolve_reference(str(auxiliary.get("raw_file", "")))
                if candidate.is_file():
                    return candidate

    evidence = sorted((ROOT / "evidencias" / "oficial" / "raw" / "comunas").glob("*.geojson"))
    if evidence:
        return evidence[-1]

    fallback = ROOT / "lago" / "gold" / "comunas.geojson"
    if fallback.is_file():
        return fallback
    raise FileNotFoundError("no hay una capa oficial de comunas para construir el mapa")


def _load_boundaries(metadata: dict) -> tuple[list[dict], Path]:
    source = _boundary_source(metadata)
    document = json.loads(source.read_text(encoding="utf-8"))
    features = []
    for feature in document.get("features", []):
        properties = feature.get("properties") or {}
        try:
            comuna = int(properties.get("comuna"))
        except (ValueError, TypeError):
            continue
        geometry = _simplificar_geom(feature.get("geometry") or {})
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"geometría no poligonal para Comuna {comuna}")
        features.append({
            "comuna": comuna,
            "barrios": str(properties.get("barrios") or "Sin detalle de barrios"),
            "geometry": geometry,
        })
    if len(features) != 15 or {feature["comuna"] for feature in features} != set(range(1, 16)):
        raise ValueError("la capa del mapa debe contener 15 comunas únicas (1..15)")
    return sorted(features, key=lambda feature: feature["comuna"]), source


def _rings(geometry: dict):
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        return coordinates
    return [ring for polygon in coordinates for ring in polygon]


def _ring_area(ring) -> float:
    return abs(sum(first[0] * second[1] - second[0] * first[1]
                   for first, second in zip(ring, ring[1:])))


def _ring_centroid(ring) -> tuple[float, float]:
    """Centroide de un anillo; usa el promedio si el área es degenerada."""
    area2 = cx = cy = 0.0
    for first, second in zip(ring, ring[1:]):
        cross = first[0] * second[1] - second[0] * first[1]
        area2 += cross
        cx += (first[0] + second[0]) * cross
        cy += (first[1] + second[1]) * cross
    if abs(area2) < 1e-12:
        return (sum(point[0] for point in ring) / len(ring),
                sum(point[1] for point in ring) / len(ring))
    return cx / (3 * area2), cy / (3 * area2)


def _feature_center(feature: dict) -> tuple[float, float]:
    rings = [ring for ring in _rings(feature["geometry"]) if len(ring) >= 4]
    return _ring_centroid(max(rings, key=_ring_area))


def _map_geojson(features: list[dict], rows: list[dict]) -> dict:
    """Une geometría local e indicadores GOLD para la fuente GeoJSON de MapLibre."""
    by_commune = {int(row["comuna"]): row for row in rows}
    output = []
    for feature in features:
        commune = feature["comuna"]
        center_lon, center_lat = _feature_center(feature)
        output.append({
            "type": "Feature",
            "id": commune,
            "properties": {
                **by_commune[commune],
                "comuna": commune,
                "barrios": feature["barrios"],
                "label_lon": center_lon,
                "label_lat": center_lat,
            },
            "geometry": feature["geometry"],
        })
    return {"type": "FeatureCollection", "features": output}


def _map_paths(features: list[dict]) -> str:
    points = [point for feature in features for ring in _rings(feature["geometry"])
              for point in ring]
    min_lon = min(point[0] for point in points)
    max_lon = max(point[0] for point in points)
    min_lat = min(point[1] for point in points)
    max_lat = max(point[1] for point in points)
    scale = min(
        (MAP_WIDTH - 2 * MAP_PADDING) / (max_lon - min_lon),
        (MAP_HEIGHT - 2 * MAP_PADDING) / (max_lat - min_lat),
    )
    map_width = (max_lon - min_lon) * scale
    map_height = (max_lat - min_lat) * scale
    offset_x = (MAP_WIDTH - map_width) / 2
    offset_y = (MAP_HEIGHT - map_height) / 2

    def project(point):
        x = offset_x + (point[0] - min_lon) * scale
        y = offset_y + (max_lat - point[1]) * scale
        return x, y

    paths = []
    labels = []

    for feature in features:
        commands = []
        feature_rings = [ring for ring in _rings(feature["geometry"]) if len(ring) >= 4]
        for ring in feature_rings:
            projected = [project(point) for point in ring]
            commands.append("M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in projected) + " Z")
        comuna = feature["comuna"]
        barrios = html_lib.escape(feature["barrios"], quote=True)
        largest_ring = max(feature_rings, key=_ring_area)
        center_x, center_y = project(_ring_centroid(largest_ring))
        paths.append(
            f'<path class="commune" data-comuna="{comuna}" data-barrios="{barrios}" '
            f'data-center-x="{center_x:.2f}" data-center-y="{center_y:.2f}" '
            f'd="{" ".join(commands)}" tabindex="0" role="button" '
            f'aria-label="Comuna {comuna}"><title>Comuna {comuna}</title></path>'
        )
        labels.append(
            f'<text class="map-label" data-label-comuna="{comuna}" '
            f'x="{center_x:.2f}" y="{center_y:.2f}" aria-hidden="true">C{comuna}</text>'
        )
    return "\n".join(paths + labels)


def _sources_html(metadata: dict) -> str:
    output = []
    for domain, source in metadata.get("fuentes", {}).items():
        url = html_lib.escape(_safe_url(str(source.get("url", ""))), quote=True)
        output.append(
            "<li><span>" + html_lib.escape(str(domain).replace("_", " ").title()) + "</span>"
            + html_lib.escape(str(source.get("organismo", source.get("fuente", ""))))
            + f' · <a href="{url}" rel="noreferrer">ver fuente</a></li>'
        )
    return "".join(output)


def _json_script(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def main() -> int:
    APP.mkdir(parents=True, exist_ok=True)
    rows, metadata = _load_gold()
    boundaries, boundary_path = _load_boundaries(metadata)
    map_paths = _map_paths(boundaries)

    numeric_rows = []
    for row in rows:
        numeric_rows.append({key: _num(value) for key, value in row.items()})
    map_geojson = _map_geojson(boundaries, numeric_rows)

    provenance = metadata.get("provenance_status", "unknown")
    is_demo = provenance == "demo"
    population_year = int(numeric_rows[0].get("anio_poblacion", 2022))
    population_total = sum(int(row["poblacion"]) for row in numeric_rows)
    generated = html_lib.escape(str(metadata.get("generado", dt.datetime.now().isoformat(timespec="seconds"))))
    run_id = html_lib.escape(str(metadata.get("run_id") or "sin run_id"))
    map_source = html_lib.escape(display_path(boundary_path))

    notice = ""
    if is_demo:
        notice = """
        <aside class="demo-notice" role="status">
          <span class="notice-icon">!</span>
          <div><strong>DEMO · NO OFICIAL</strong><p>Estas cifras son sintéticas y sirven para probar el pipeline. No describen Buenos Aires.</p></div>
        </aside>"""

    status_label = "Demo no oficial" if is_demo else "Datos oficiales"
    status_class = "demo" if is_demo else "official"
    footer_label = "cifras sintéticas de demostración" if is_demo else "datos oficiales de BA Data e IDECBA"

    template = r'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#050c17">
<title>Cerebro Buenos Aires · Observatorio urbano</title>
<link rel="stylesheet" href="../vendor/maplibre-gl.css">
<style>
:root {
  color-scheme: dark;
  --bg:#050c17; --surface:#0b1726; --surface-2:#102136; --surface-3:#152c46;
  --line:rgba(120,175,215,.18); --text:#eef7fb; --muted:#8ea8ba;
  --cyan:#31c7d9; --mint:#49e5b5; --violet:#8b7cf6; --amber:#ffc857;
  --shadow:0 22px 55px rgba(0,0,0,.38); --radius:20px;
}
*{box-sizing:border-box} html{scroll-behavior:smooth}
body{margin:0;min-width:320px;background:
  radial-gradient(circle at 78% -10%,rgba(49,199,217,.16),transparent 34rem),
  radial-gradient(circle at -8% 30%,rgba(139,124,246,.12),transparent 28rem),var(--bg);
  color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--cyan)} button{font:inherit}.shell{width:min(1240px,calc(100% - 40px));margin:auto}
.topbar{height:72px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:11px;font-weight:760;letter-spacing:-.02em}.brand-mark{display:grid;place-items:center;width:34px;height:34px;border-radius:11px;background:linear-gradient(135deg,var(--cyan),var(--violet));box-shadow:0 8px 24px rgba(49,199,217,.22)}
.back-link{color:var(--muted);text-decoration:none;font-size:.86rem}.back-link:hover{color:var(--text)}
.hero{padding:68px 0 42px;display:grid;grid-template-columns:minmax(0,1.35fr) minmax(260px,.65fr);gap:50px;align-items:end}
.eyebrow{margin:0 0 14px;color:var(--mint);font-size:.76rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase}
h1{margin:0;max-width:790px;font-size:clamp(2.55rem,6vw,5.3rem);line-height:.96;letter-spacing:-.065em}.hero h1 span{color:var(--cyan)}
.lead{max-width:650px;margin:24px 0 0;color:var(--muted);font-size:1.08rem;line-height:1.7}
.hero-meta{padding:22px;border:1px solid var(--line);border-radius:var(--radius);background:linear-gradient(145deg,rgba(16,33,54,.92),rgba(11,23,38,.76));box-shadow:var(--shadow)}
.status{display:inline-flex;align-items:center;gap:8px;padding:7px 11px;border-radius:999px;font-size:.75rem;font-weight:760}.status::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}.status.official{color:var(--mint);background:rgba(73,229,181,.1)}.status.demo{color:var(--amber);background:rgba(255,200,87,.1)}
.meta-number{margin:20px 0 3px;font-size:2rem;font-weight:790;letter-spacing:-.04em}.meta-copy{margin:0;color:var(--muted);font-size:.83rem;line-height:1.55}
.demo-notice{display:flex;gap:14px;margin-bottom:24px;padding:16px 18px;border:1px solid rgba(255,200,87,.35);border-radius:16px;background:rgba(80,54,9,.58);color:#ffe3a1}.notice-icon{display:grid;place-items:center;flex:0 0 27px;height:27px;border-radius:50%;background:var(--amber);color:#201701;font-weight:900}.demo-notice strong{font-size:.83rem;letter-spacing:.08em}.demo-notice p{margin:3px 0 0;color:#e9ca84;font-size:.86rem}
.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin:0 0 24px}.kpi{min-width:0;padding:18px;border:1px solid var(--line);border-radius:17px;background:rgba(11,23,38,.82)}.kpi-value{font-size:clamp(1.25rem,2.1vw,1.85rem);font-weight:780;letter-spacing:-.04em;white-space:nowrap}.kpi-label{margin-top:7px;color:var(--muted);font-size:.74rem;line-height:1.35}.kpi:first-child .kpi-value{color:var(--cyan)}
.control-panel{position:sticky;top:10px;z-index:10;margin-bottom:18px;padding:13px;display:flex;align-items:center;justify-content:space-between;gap:14px;border:1px solid var(--line);border-radius:18px;background:rgba(5,12,23,.92);box-shadow:0 12px 35px rgba(0,0,0,.32);backdrop-filter:blur(14px)}
.segmented,.indicator-tabs{display:flex;gap:5px;flex-wrap:wrap}.mode-btn,.indicator-btn{border:0;border-radius:11px;background:transparent;color:var(--muted);cursor:pointer;font-weight:680;font-size:.78rem;padding:10px 13px}.mode-btn:hover,.indicator-btn:hover{color:var(--text);background:rgba(255,255,255,.05)}.mode-btn.active{color:#04151b;background:var(--cyan)}.indicator-btn.active{color:var(--text);background:var(--surface-3);box-shadow:inset 0 0 0 1px rgba(49,199,217,.28)}
.section-card{border:1px solid var(--line);border-radius:var(--radius);background:rgba(11,23,38,.8);box-shadow:var(--shadow);overflow:hidden}.section-head{display:flex;align-items:end;justify-content:space-between;gap:20px;padding:24px 26px;border-bottom:1px solid var(--line)}.section-head h2{margin:0;font-size:1.25rem;letter-spacing:-.025em}.section-head p{margin:5px 0 0;color:var(--muted);font-size:.84rem}.map-layout{display:grid;grid-template-columns:minmax(0,1fr) 320px;min-height:640px}
.map-stage{position:relative;min-height:640px;display:grid;place-items:center;min-width:0;padding:25px;overflow:hidden;isolation:isolate;background:
  radial-gradient(ellipse at 50% 56%,rgba(49,199,217,.16) 0%,rgba(19,52,84,.12) 38%,rgba(4,10,20,.96) 76%),
  linear-gradient(rgba(49,199,217,.045) 1px,transparent 1px),
  linear-gradient(90deg,rgba(49,199,217,.045) 1px,transparent 1px);
  background-size:auto,36px 36px,36px 36px}
.map-stage::before{content:"";position:absolute;inset:0;pointer-events:none;z-index:2;box-shadow:inset 0 0 90px rgba(3,8,16,.88)}
.map-stage::after{content:"MAQUETA 3D · ALTURA = VALOR";position:absolute;right:18px;top:18px;z-index:4;pointer-events:none;color:rgba(73,229,181,.75);font-size:.62rem;font-weight:800;letter-spacing:.16em;padding:6px 11px;border-radius:999px;border:1px solid rgba(73,229,181,.25);background:rgba(5,12,23,.82)}
#city-map{width:100%;height:auto;max-height:570px;overflow:visible;cursor:grab;touch-action:none;user-select:none;transform:perspective(1100px) rotateX(26deg) rotateZ(-10deg);filter:drop-shadow(0 28px 28px rgba(0,0,0,.62));transition:transform .35s ease}#city-map.dragging{cursor:grabbing}.commune{fill:#152c46;stroke:#061221;stroke-width:1.8;vector-effect:non-scaling-stroke;cursor:pointer;transition:fill .24s ease,filter .18s ease,transform .2s ease}.commune:hover,.commune:focus,.commune.selected{stroke:#ffc857;stroke-width:2.8;filter:brightness(1.22) drop-shadow(0 -8px 14px rgba(255,200,87,.35));outline:none}.map-label{fill:#f4fbff;stroke:#050c17;stroke-width:3px;paint-order:stroke;pointer-events:none;text-anchor:middle;dominant-baseline:central;font-size:13px;font-weight:850;letter-spacing:-.03em;vector-effect:non-scaling-stroke;transition:font-size .18s ease}.map-label.selected{fill:var(--amber);font-size:17px}.map-controls{position:absolute;top:18px;left:18px;z-index:6;display:grid;gap:6px}.map-control{display:grid;place-items:center;width:38px;height:38px;padding:0;border:1px solid rgba(255,255,255,.14);border-radius:11px;background:rgba(5,12,23,.91);color:var(--text);box-shadow:0 8px 20px rgba(0,0,0,.22);cursor:pointer;font-size:1rem;font-weight:800}.map-control:hover,.map-control:focus-visible{border-color:var(--cyan);color:var(--cyan);outline:none}.map-hint{position:absolute;left:18px;bottom:16px;z-index:5;padding:7px 11px;border:1px solid var(--line);border-radius:9px;background:rgba(5,12,23,.86);color:var(--muted);font-size:.65rem;pointer-events:none}.zoom-level{font-size:.62rem;color:var(--muted)}.map-tooltip{position:fixed;z-index:40;display:none;min-width:190px;padding:12px 14px;border:1px solid rgba(49,199,217,.28);border-radius:12px;background:rgba(5,12,23,.95);box-shadow:0 14px 35px rgba(0,0,0,.55);pointer-events:none;font-size:.78rem}.map-tooltip strong{display:block;margin-bottom:3px}.map-tooltip span{color:var(--mint);font-weight:700}.map-tooltip small{display:block;margin-top:5px;color:var(--muted)}
.maplibre-map{position:absolute;inset:0;z-index:1;display:none;background:radial-gradient(circle at 50% 52%,#0c2138 0%,#050c17 74%)}.map-stage.webgl-active .maplibre-map{display:block}.map-stage.webgl-active #city-map,.map-stage.webgl-active .fallback-only{display:none}.webgl-toolbar{position:absolute;top:18px;left:18px;z-index:6;display:none;gap:7px;flex-wrap:wrap}.map-stage.webgl-active .webgl-toolbar{display:flex}.map-pill{padding:8px 13px;border:1px solid rgba(120,175,215,.24);border-radius:999px;background:rgba(5,12,23,.88);color:var(--muted);box-shadow:0 8px 24px rgba(0,0,0,.35);cursor:pointer;font-size:.7rem;font-weight:750;backdrop-filter:blur(10px);transition:all .16s ease}.map-pill:hover,.map-pill:focus-visible{color:var(--text);border-color:var(--cyan);outline:none}.map-pill.active{color:#04151b;border-color:var(--cyan);background:linear-gradient(135deg,var(--cyan),var(--mint))}
.map-connection{position:absolute;left:18px;bottom:48px;z-index:6;display:none;align-items:center;gap:7px;padding:7px 11px;border:1px solid var(--line);border-radius:9px;background:rgba(5,12,23,.88);color:var(--muted);font-size:.65rem;pointer-events:none}.map-stage.webgl-active .map-connection{display:flex}.map-connection span{width:7px;height:7px;border-radius:50%;background:var(--mint);box-shadow:0 0 0 4px rgba(73,229,181,.16)}.map-connection.online span{background:var(--cyan);box-shadow:0 0 0 4px rgba(49,199,217,.18)}
.map-attribution{position:absolute;right:10px;bottom:8px;z-index:6;display:none;padding:3px 7px;border-radius:5px;background:rgba(5,12,23,.76);color:var(--muted);font-size:.56rem}.map-stage.webgl-active .map-attribution{display:block}.map-attribution a{color:#aac1cf;text-decoration:none}
.maplibregl-ctrl-top-right{top:56px;right:14px}.maplibregl-ctrl-group{overflow:hidden;border:1px solid rgba(120,175,215,.22);border-radius:11px!important;background:rgba(5,12,23,.9)!important;box-shadow:0 8px 24px rgba(0,0,0,.38)!important}.maplibregl-ctrl-group button+button{border-color:rgba(120,175,215,.14)!important}.maplibregl-ctrl button .maplibregl-ctrl-icon{filter:invert(1)}.maplibregl-popup-content{padding:13px 15px;border:1px solid rgba(49,199,217,.32);border-radius:13px;background:rgba(5,12,23,.95);color:var(--text);box-shadow:0 18px 42px rgba(0,0,0,.6);font:12px/1.5 Inter,system-ui,sans-serif}.maplibregl-popup-content strong{display:block;font-size:.86rem;color:#fff}.maplibregl-popup-content span{color:var(--mint);font-weight:750}.maplibregl-popup-close-button{color:var(--muted)}.maplibregl-popup-anchor-bottom .maplibregl-popup-tip{border-top-color:rgba(5,12,23,.95)}.maplibregl-popup-anchor-top .maplibregl-popup-tip{border-bottom-color:rgba(5,12,23,.95)}
.gl-marker-anchor{pointer-events:auto;transition:opacity .2s ease}.gl-marker-anchor.hidden-flag{display:none!important}.gl-marker-anchor.selected{z-index:10!important}
.gl-commune-label{--lift:0px;position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:36px;height:26px;padding:0 7px;border:1px solid rgba(155,248,219,.68);border-radius:8px;background:rgba(5,12,23,.92);color:#eef7fb;box-shadow:0 6px 16px rgba(0,0,0,.65);font:800 10px/1.05 Inter,system-ui,sans-serif;cursor:pointer;transition:transform .18s ease,border-color .18s ease,background .18s ease;transform:translateY(var(--lift))}
.gl-commune-label::after{content:"";position:absolute;left:50%;top:100%;width:1.5px;height:8px;background:rgba(155,248,219,.55);transform:translateX(-50%);pointer-events:none}
.gl-commune-label small{font-size:8px;font-weight:750;color:var(--mint);margin-top:1px;font-variant-numeric:tabular-nums}
.gl-commune-label:hover,.gl-commune-label.selected{border-color:var(--amber);background:#1b2232;color:var(--amber);transform:translateY(var(--lift)) scale(1.16);box-shadow:0 10px 24px rgba(0,0,0,.78),0 0 18px rgba(255,200,87,.45)}
.gl-commune-label.selected::after{background:var(--amber);height:11px}
.gl-commune-label.selected small{color:#ffe3a1}
.map-side{padding:25px;border-left:1px solid var(--line);background:rgba(5,12,23,.48)}.side-kicker{color:var(--cyan);font-size:.69rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase}.commune-picker{display:block;margin:15px 0 19px}.commune-picker span{display:block;margin-bottom:7px;color:var(--muted);font-size:.68rem}.commune-select{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:11px;background:var(--surface);color:var(--text);font:inherit;font-size:.78rem;outline:none}.commune-select:focus{border-color:var(--cyan)}.commune-title{margin:8px 0 3px;font-size:1.8rem;letter-spacing:-.04em}.commune-neighborhoods{min-height:52px;margin:0;color:var(--muted);font-size:.77rem;line-height:1.5}.selected-value{margin:20px 0 12px;padding:16px;border:1px solid rgba(49,199,217,.22);border-radius:15px;background:rgba(49,199,217,.075)}.selected-value strong{display:block;color:var(--mint);font-size:1.7rem;letter-spacing:-.04em}.selected-value span{color:var(--muted);font-size:.75rem}.comparison{display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:center;margin-bottom:16px;padding:11px 12px;border-radius:12px;background:rgba(255,255,255,.035)}.rank-badge{display:grid;place-items:center;min-width:43px;height:31px;padding:0 8px;border-radius:9px;background:var(--surface-3);color:var(--cyan);font-size:.72rem;font-weight:800}.comparison strong{display:block;font-size:.74rem}.comparison small{display:block;margin-top:2px;color:var(--muted);font-size:.66rem}.mini-list{margin:0;padding:0;list-style:none}.mini-list li{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--line);color:var(--muted);font-size:.75rem}.mini-list b{color:var(--text);font-variant-numeric:tabular-nums}.legend{margin-top:22px}.legend-title{display:flex;justify-content:space-between;margin-bottom:8px;color:var(--muted);font-size:.65rem}.legend-bar{height:8px;border-radius:99px;background:linear-gradient(90deg,#15314f,#196387,#22b0b5,#49e5b5,#a8ffdf)}.legend-steps{display:grid;grid-template-columns:repeat(5,1fr);gap:3px;margin-top:8px}.legend-step{height:5px;border-radius:99px}.legend-labels{display:flex;justify-content:space-between;margin-top:7px;color:var(--muted);font-size:.66rem}
.analytics-grid{display:grid;grid-template-columns:.72fr 1.28fr;gap:18px;margin-top:18px}.ranking,.data-table{padding:24px 26px;min-width:0}.ranking h2,.data-table h2{margin:0 0 6px;font-size:1.12rem}.panel-sub{margin:0 0 20px;color:var(--muted);font-size:.78rem}.rank-row{display:grid;grid-template-columns:28px 76px 1fr auto;gap:10px;align-items:center;margin:13px 0;font-size:.78rem}.rank-position{color:var(--muted)}.rank-track{height:7px;border-radius:99px;background:#091522;overflow:hidden}.rank-fill{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--cyan),var(--mint))}.rank-value{font-weight:700;font-variant-numeric:tabular-nums}.table-scroll{overflow:auto;max-height:425px;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:13px}table{width:100%;border-collapse:separate;border-spacing:0;font-size:.76rem}th,td{padding:11px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th{position:sticky;top:0;z-index:2;background:var(--surface);color:var(--muted);font-size:.67rem;text-transform:uppercase;letter-spacing:.06em}th:first-child,td:first-child{text-align:left;position:sticky;left:0;z-index:1;background:rgba(11,23,38,.96);backdrop-filter:blur(6px)}th:first-child{z-index:3;background:var(--surface)}tbody tr{cursor:pointer}tbody tr:hover td{background:rgba(49,199,217,.07)}td.active-col{color:var(--mint);font-weight:760}
.provenance{margin:18px 0 50px;padding:27px}.provenance-grid{display:grid;grid-template-columns:.8fr 1.2fr;gap:36px}.provenance h2{margin:0 0 8px;font-size:1.15rem}.provenance p{margin:0;color:var(--muted);font-size:.79rem;line-height:1.65}.source-list{margin:0;padding:0;list-style:none}.source-list li{display:flex;justify-content:space-between;gap:15px;padding:8px 0;border-bottom:1px solid var(--line);color:var(--muted);font-size:.72rem}.source-list span{color:var(--text);font-weight:650}.source-list a{white-space:nowrap}.technical{margin-top:17px;padding-top:14px;border-top:1px solid var(--line);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.66rem;color:#6f899c;overflow-wrap:anywhere}
footer{padding:28px 0 42px;border-top:1px solid var(--line);color:var(--muted);font-size:.72rem}.footer-inner{display:flex;justify-content:space-between;gap:20px}
@media(max-width:1000px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.map-layout{grid-template-columns:1fr}.map-side{border-left:0;border-top:1px solid var(--line)}.analytics-grid{grid-template-columns:1fr}.hero{grid-template-columns:1fr;gap:24px;padding:42px 0 28px}.hero-meta{max-width:100%;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px}}
@media(max-width:700px){
  .shell{width:calc(100% - 24px)}
  .topbar{height:58px}
  .brand{font-size:.92rem;gap:9px}.brand-mark{width:30px;height:30px;border-radius:9px;font-size:.8rem}
  .back-label{display:none}
  .hero{padding:24px 0 18px;gap:16px}
  .eyebrow{margin-bottom:8px;font-size:.68rem}
  h1{font-size:clamp(1.95rem,8.4vw,2.75rem);line-height:1.02}
  .lead{margin-top:12px;font-size:.92rem;line-height:1.55}
  .hero-meta{padding:14px 16px;border-radius:16px;display:grid;grid-template-columns:auto 1fr;align-items:center;gap:8px 14px}
  .hero-meta .status{grid-column:1 / -1;justify-self:start;padding:5px 10px;font-size:.68rem}
  .meta-number{margin:0;font-size:1.5rem}
  .meta-copy{font-size:.74rem;line-height:1.35}
  .kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:16px}
  .kpi{padding:12px 13px;border-radius:14px}
  .kpi-value{font-size:1.22rem}
  .kpi-label{margin-top:4px;font-size:.68rem;line-height:1.25}
  .control-panel{position:sticky;top:6px;z-index:25;display:flex;flex-direction:column;align-items:stretch;gap:8px;padding:10px;border-radius:15px;margin-bottom:14px}
  .segmented{display:grid;grid-template-columns:1fr 1fr;gap:4px;background:rgba(255,255,255,.035);padding:3px;border-radius:11px}
  .mode-btn{padding:8px 10px;font-size:.75rem;text-align:center}
  .indicator-tabs{display:flex;flex-wrap:nowrap;overflow-x:auto;gap:6px;margin-top:0;padding-bottom:2px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
  .indicator-tabs::-webkit-scrollbar{display:none}
  .indicator-btn{flex:0 0 auto;white-space:nowrap;padding:8px 12px;font-size:.74rem}
  .section-head{align-items:start;flex-direction:column;gap:8px;padding:16px 18px}
  .section-head h2{font-size:1.08rem}
  .section-head p{font-size:.76rem}
  .section-head .status{display:none}
  .map-layout{min-height:0}
  .map-stage{min-height:410px;height:420px;padding:10px}
  .map-stage::after,.map-connection,.map-attribution{display:none!important}
  .webgl-toolbar{top:10px;left:10px;right:54px;flex-wrap:nowrap;overflow-x:auto;gap:5px;padding-bottom:2px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
  .webgl-toolbar::-webkit-scrollbar{display:none}
  .map-pill{flex:0 0 auto;white-space:nowrap;padding:7px 11px;font-size:.67rem}
  .maplibregl-ctrl-top-right{top:8px;right:8px}
  .map-hint{left:10px;right:10px;bottom:8px;text-align:center;font-size:.61rem;padding:5px 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  #city-map{max-height:360px;transform:perspective(900px) rotateX(18deg) rotateZ(-6deg)}
  .map-side{padding:18px}
  .commune-picker{margin:10px 0 14px}
  .commune-title{font-size:1.45rem}
  .commune-neighborhoods{min-height:0;margin-bottom:4px;font-size:.74rem}
  .selected-value{margin:12px 0 10px;padding:13px 14px;display:flex;align-items:baseline;justify-content:space-between;gap:10px}
  .selected-value strong{font-size:1.45rem}
  .mini-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 14px}
  .mini-list li{padding:7px 0;font-size:.72rem}
  .ranking,.data-table,.provenance{padding:18px}
  .rank-row{grid-template-columns:22px 68px 1fr auto;gap:8px;font-size:.74rem;margin:10px 0}
  .table-scroll{max-height:360px}
  th,td{padding:9px 8px;font-size:.72rem}
  .provenance-grid{grid-template-columns:1fr;gap:20px}
  .source-list li{flex-direction:column;align-items:flex-start;gap:3px}
  .footer-inner{display:block}.footer-inner span{display:block;margin-top:5px}
}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
</style>
</head>
<body class="__BODY_CLASS__">
<header class="shell topbar">
  <div class="brand"><span class="brand-mark">BA</span>Cerebro Buenos Aires</div>
  <a class="back-link" href="../index.html" aria-label="Cambiar publicación">← <span class="back-label">Cambiar publicación</span></a>
</header>
<main class="shell">
  <section class="hero">
    <div><p class="eyebrow">Observatorio urbano por comuna</p><h1>Buenos Aires,<br><span>vista en datos.</span></h1><p class="lead">Explorá cómo se distribuyen la movilidad, los espacios verdes y los hospitales entre las 15 comunas de la ciudad.</p></div>
    <div class="hero-meta"><span class="status __STATUS_CLASS__">__STATUS_LABEL__</span><div class="meta-number">__POPULATION__</div><p class="meta-copy">habitantes · Censo __YEAR__<br>Calidad del lote: verificada</p></div>
  </section>
  __NOTICE__
  <section id="kpi-grid" class="kpis" aria-label="Indicadores de toda la ciudad"></section>
  <nav class="control-panel" aria-label="Controles del observatorio">
    <div class="segmented" role="tablist" aria-label="Modo de visualización">
      <button class="mode-btn active" data-mode="total" role="tab" aria-selected="true">Totales</button>
      <button class="mode-btn" data-mode="rate" role="tab" aria-selected="false">Por habitante</button>
    </div>
    <div id="indicator-tabs" class="indicator-tabs" aria-label="Indicador del mapa"></div>
  </nav>
  <section class="section-card">
    <header class="section-head"><div><h2 id="map-title">Mapa por comuna</h2><p id="map-subtitle">Cada comuna es un bloque 3D independiente cuya altura representa el valor del indicador.</p></div><span class="status __STATUS_CLASS__">15 comunas · Bloques 3D</span></header>
    <div class="map-layout">
      <div id="map-stage" class="map-stage">
        <div id="maplibre-map" class="maplibre-map" aria-label="Maqueta 3D interactiva de las comunas de Buenos Aires"></div>
        <div id="webgl-toolbar" class="webgl-toolbar" aria-label="Controles de maqueta 3D">
          <button type="button" id="dimension-toggle" class="map-pill active" aria-pressed="true">Relieve 3D</button>
          <button type="button" id="scale-toggle" class="map-pill" aria-pressed="false">Altura: Normal</button>
          <button type="button" id="orbit-toggle" class="map-pill" aria-pressed="false">Rotar 360°</button>
          <button type="button" id="reset-camera" class="map-pill">Centrar vista</button>
          <button type="button" id="streets-toggle" class="map-pill" aria-pressed="false">Fondo: Maqueta</button>
        </div>
        <div id="map-connection" class="map-connection"><span></span>Bloques 3D separados por comuna · Techo claro y paredes sombreadas</div>
        <div class="map-attribution"><a href="https://data.buenosaires.gob.ar" rel="noreferrer">BA Data</a> · Geometría oficial de comunas</div>
        <div class="map-controls fallback-only" aria-label="Controles del mapa SVG de respaldo">
          <button type="button" id="zoom-in" class="map-control" aria-label="Acercar mapa" title="Acercar">+</button>
          <button type="button" id="zoom-out" class="map-control" aria-label="Alejar mapa" title="Alejar">−</button>
          <button type="button" id="zoom-reset" class="map-control" aria-label="Restablecer mapa" title="Ver toda la ciudad">⌂</button>
          <span id="zoom-level" class="zoom-level" aria-live="polite">100 %</span>
        </div>
        <div id="map-hint" class="map-hint">Arrastrá para mover · clic derecho o Ctrl + arrastrar para inclinar/girar 3D · rueda para zoom</div>
        <svg id="city-map" viewBox="0 0 900 650" role="img" aria-labelledby="map-title map-description">
          <desc id="map-description">Mapa coroplético interactivo de las 15 comunas de Buenos Aires, con zoom y desplazamiento.</desc>
          <defs>
            <filter id="map-shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="-8" dy="18" stdDeviation="12" flood-color="#000" flood-opacity=".55"/></filter>
          </defs>
          <g id="map-viewport" fill-rule="evenodd" filter="url(#map-shadow)">__MAP_PATHS__</g>
        </svg>
        <div id="map-tooltip" class="map-tooltip" aria-hidden="true"></div>
      </div>
      <aside class="map-side" aria-live="polite">
        <div class="side-kicker">Detalle territorial</div>
        <label class="commune-picker"><span>Ir directamente a</span><select id="commune-select" class="commune-select" aria-label="Seleccionar comuna"></select></label>
        <h3 id="commune-title" class="commune-title">Comuna 1</h3><p id="commune-neighborhoods" class="commune-neighborhoods"></p>
        <div class="selected-value"><strong id="selected-value">—</strong><span id="selected-unit">—</span></div>
        <div class="comparison"><span id="rank-badge" class="rank-badge">#—</span><div><strong id="comparison-text">Comparando…</strong><small id="comparison-base">Promedio de las 15 comunas</small></div></div>
        <ul id="commune-metrics" class="mini-list"></ul>
        <div class="legend"><div class="legend-title"><span>Menor altura / valor</span><span>Mayor altura / valor</span></div><div class="legend-bar"></div><div id="legend-steps" class="legend-steps"></div><div class="legend-labels"><span id="legend-min">Menor</span><span id="legend-max">Mayor</span></div></div>
      </aside>
    </div>
  </section>
  <div class="analytics-grid">
    <section class="section-card ranking"><h2>Comunas con mayor valor</h2><p id="ranking-subtitle" class="panel-sub"></p><div id="ranking-list"></div></section>
    <section class="section-card data-table"><h2>Datos por comuna</h2><p class="panel-sub">Seleccioná una fila para enfocar su bloque 3D en la maqueta.</p><div class="table-scroll"><table><thead id="table-head"></thead><tbody id="table-body"></tbody></table></div></section>
  </div>
  <section class="section-card provenance">
    <div class="provenance-grid"><div><p class="eyebrow">Trazabilidad</p><h2>De dónde vienen los datos</h2><p>La calidad técnica y la procedencia son estados diferentes. Este lote superó las reglas de estructura, integridad y consistencia; la etiqueta de publicación indica si las observaciones son oficiales o sintéticas.</p><div class="technical">run_id: __RUN_ID__<br>gold: __GENERATED__<br>mapa: __MAP_SOURCE__</div></div><ul class="source-list">__SOURCES__</ul></div>
  </section>
</main>
<footer><div class="shell footer-inner"><strong>Cerebro Buenos Aires</strong><span>__FOOTER_LABEL__ · Censo __YEAR__</span></div></footer>
<script src="../vendor/maplibre-gl.js"></script>
<script>
const ROWS=__ROWS_JSON__;
const MAP_GEOJSON=__GEOJSON_JSON__;
const INDICATORS=__INDICATORS_JSON__;
let mode="total",indicatorId="ecobici",selectedCommune=1,heightBoost=1;
const byCommune=Object.fromEntries(ROWS.map(row=>[Number(row.comuna),row]));
const paths=[...document.querySelectorAll(".commune")];
const format=(value,decimals=0)=>new Intl.NumberFormat("es-AR",{minimumFractionDigits:decimals,maximumFractionDigits:decimals}).format(Number(value));
const indicator=()=>INDICATORS.find(item=>item.id===indicatorId);
const key=()=>indicator()[mode];
const unit=()=>indicator()[mode+"_unit"];
const decimals=itemKey=>itemKey.includes("km_")||itemKey.includes("_por_")||itemKey==="m2_verdes_por_hab"?2:(itemKey==="m2_espacios_verdes"?1:0);
const value=row=>Number(row[key()]);
function cityValue(item){const total=ROWS.reduce((sum,row)=>sum+Number(row[item.total]),0);if(mode==="total")return total;const population=ROWS.reduce((sum,row)=>sum+Number(row.poblacion),0);return total/population*item.factor}
function rgbTuple(value,min,max){const t=max===min ? 0.65 : Math.max(0,Math.min(1,(value-min)/(max-min)));const stops=[[21,49,79],[25,99,135],[34,176,181],[73,229,181],[168,255,223]];const p=t*(stops.length-1),i=Math.min(stops.length-2,Math.floor(p)),f=p-i;return stops[i].map((v,j)=>Math.round(v+(stops[i+1][j]-v)*f))}
function color(value,min,max){return `rgb(${rgbTuple(value,min,max).join(",")})`}
function shadeRgb(rgb,factor){return `rgb(${rgb.map(c=>Math.max(0,Math.min(255,Math.round(c*factor)))).join(",")})`}
function renderKpis(){const population=ROWS.reduce((sum,row)=>sum+Number(row.poblacion),0);const cards=[`<article class="kpi"><div class="kpi-value">${format(population)}</div><div class="kpi-label">Habitantes · Censo __YEAR__</div></article>`];INDICATORS.forEach(item=>cards.push(`<article class="kpi"><div class="kpi-value">${format(cityValue(item),decimals(item[mode]))}</div><div class="kpi-label">${item.label}<br>${item[mode+"_unit"]}</div></article>`));document.getElementById("kpi-grid").innerHTML=cards.join("")}
function isMobileView(){return window.innerWidth<=700}
function defaultCamera(){return {center:[-58.442,-34.617],zoom:isMobileView()?9.88:10.48,pitch:is3D?(isMobileView()?52:56):0,bearing:is3D?-24:0}}
function renderControls(){document.getElementById("indicator-tabs").innerHTML=INDICATORS.map(item=>`<button class="indicator-btn ${item.id===indicatorId?"active":""}" data-indicator="${item.id}">${item.short}</button>`).join("");document.querySelectorAll(".indicator-btn").forEach(button=>button.addEventListener("click",()=>{indicatorId=button.dataset.indicator;render();button.scrollIntoView({block:"nearest",inline:"center",behavior:"smooth"})}))}
function renderMap(){const values=ROWS.map(value),min=Math.min(...values),max=Math.max(...values);paths.forEach(path=>{const row=byCommune[Number(path.dataset.comuna)],v=value(row);path.style.fill=color(v,min,max);path.classList.toggle("selected",Number(path.dataset.comuna)===selectedCommune);path.setAttribute("aria-label",`Comuna ${row.comuna}: ${format(v,decimals(key()))} ${unit()}`)});document.getElementById("legend-min").textContent=format(min,decimals(key()));document.getElementById("legend-max").textContent=format(max,decimals(key()));document.getElementById("map-title").textContent=`${indicator().label} por comuna`;document.getElementById("map-subtitle").textContent=`${mode==="total"?"Total absoluto":"Tasa normalizada"} (${unit()}) · Altura y brillo del bloque 3D según valor`}
function selectCommune(comuna){selectedCommune=Number(comuna);const row=byCommune[selectedCommune],path=paths.find(item=>Number(item.dataset.comuna)===selectedCommune);document.getElementById("commune-title").textContent=`Comuna ${selectedCommune}`;document.getElementById("commune-neighborhoods").textContent=path.dataset.barrios;document.getElementById("selected-value").textContent=format(value(row),decimals(key()));document.getElementById("selected-unit").textContent=unit();document.getElementById("commune-metrics").innerHTML=`<li><span>Población</span><b>${format(row.poblacion)}</b></li>`+INDICATORS.filter(item=>item.id!==indicatorId).map(item=>`<li><span>${item.short}</span><b>${format(row[item[mode]],decimals(item[mode]))}</b></li>`).join("");paths.forEach(item=>item.classList.toggle("selected",Number(item.dataset.comuna)===selectedCommune))}
function renderRanking(){const rows=[...ROWS].sort((a,b)=>value(b)-value(a)).slice(0,5),max=value(rows[0])||1;document.getElementById("ranking-subtitle").textContent=`${indicator().label} · ${unit()}`;document.getElementById("ranking-list").innerHTML=rows.map((row,index)=>`<div class="rank-row"><span class="rank-position">0${index+1}</span><span>Comuna ${row.comuna}</span><span class="rank-track"><span class="rank-fill" style="width:${value(row)/max*100}%"></span></span><span class="rank-value">${format(value(row),decimals(key()))}</span></div>`).join("")}
function renderTable(){const cols=INDICATORS.map(item=>({key:item[mode],label:item.short}));document.getElementById("table-head").innerHTML=`<tr><th>Comuna</th><th>Población</th>${cols.map(col=>`<th class="${col.key===key()?"active-col":""}">${col.label}</th>`).join("")}</tr>`;document.getElementById("table-body").innerHTML=ROWS.map(row=>`<tr data-row-commune="${row.comuna}"><td>Comuna ${row.comuna}</td><td>${format(row.poblacion)}</td>${cols.map(col=>`<td class="${col.key===key()?"active-col":""}">${format(row[col.key],decimals(col.key))}</td>`).join("")}</tr>`).join("");document.querySelectorAll("[data-row-commune]").forEach(row=>row.addEventListener("click",()=>selectCommune(row.dataset.rowCommune)))}
function render(){document.querySelectorAll(".mode-btn").forEach(button=>{const active=button.dataset.mode===mode;button.classList.toggle("active",active);button.setAttribute("aria-selected",active)});renderControls();renderKpis();renderMap();selectCommune(selectedCommune);renderRanking();renderTable();updateWebGLMap();updateWebGLSelection();updateMarkerValues()}
document.querySelectorAll(".mode-btn").forEach(button=>button.addEventListener("click",()=>{mode=button.dataset.mode;render()}));
const tooltip=document.getElementById("map-tooltip");paths.forEach(path=>{const comuna=Number(path.dataset.comuna);path.addEventListener("mouseenter",event=>{const row=byCommune[comuna];tooltip.innerHTML=`<strong>Comuna ${comuna}</strong><span>${format(value(row),decimals(key()))} ${unit()}</span><small>${path.dataset.barrios}</small>`;tooltip.style.display="block"});path.addEventListener("mousemove",event=>{tooltip.style.left=`${event.clientX+15}px`;tooltip.style.top=`${event.clientY+15}px`});path.addEventListener("mouseleave",()=>tooltip.style.display="none");path.addEventListener("focus",()=>selectCommune(comuna));path.addEventListener("click",()=>selectCommune(comuna));path.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();selectCommune(comuna)}})});
const mapSvg=document.getElementById("city-map"),mapViewport=document.getElementById("map-viewport"),mapLabels=[...document.querySelectorAll(".map-label")],communeSelect=document.getElementById("commune-select");
communeSelect.innerHTML=ROWS.map(row=>`<option value="${row.comuna}">Comuna ${row.comuna}</option>`).join("");
let mapScale=1,mapX=0,mapY=0,dragStart=null,mapMoved=false;
function clampMap(){mapX=Math.min(0,Math.max(900*(1-mapScale),mapX));mapY=Math.min(0,Math.max(650*(1-mapScale),mapY))}
function applyMapTransform(){clampMap();mapViewport.setAttribute("transform",`translate(${mapX} ${mapY}) scale(${mapScale})`);mapLabels.forEach(label=>{const selected=Number(label.dataset.labelComuna)===selectedCommune;label.classList.toggle("selected",selected);label.style.fontSize=`${(selected?17:13)/mapScale}px`;label.style.strokeWidth=`${3/mapScale}px`});document.getElementById("zoom-level").textContent=`${Math.round(mapScale*100)} %`}
function zoomAt(nextScale,x=450,y=325){const target=Math.max(1,Math.min(5,nextScale)),ratio=target/mapScale;mapX=x-(x-mapX)*ratio;mapY=y-(y-mapY)*ratio;mapScale=target;applyMapTransform()}
function resetMap(){mapScale=1;mapX=0;mapY=0;applyMapTransform();if(glReady&&glMap){stopOrbit();glMap.flyTo({...defaultCamera(),duration:950,essential:true})}}
function zoomToCommune(comuna){const path=paths.find(item=>Number(item.dataset.comuna)===Number(comuna)),box=path.getBBox();const target=Math.min(4,Math.max(1.6,Math.min(900/(box.width+80),650/(box.height+80))));mapScale=target;mapX=450-(box.x+box.width/2)*target;mapY=325-(box.y+box.height/2)*target;applyMapTransform()}
document.getElementById("zoom-in").addEventListener("click",()=>zoomAt(mapScale*1.35));document.getElementById("zoom-out").addEventListener("click",()=>zoomAt(mapScale/1.35));document.getElementById("zoom-reset").addEventListener("click",resetMap);
mapSvg.addEventListener("wheel",event=>{event.preventDefault();const rect=mapSvg.getBoundingClientRect(),x=(event.clientX-rect.left)*900/rect.width,y=(event.clientY-rect.top)*650/rect.height;zoomAt(mapScale*(event.deltaY<0?1.18:1/1.18),x,y)},{passive:false});
mapSvg.addEventListener("pointerdown",event=>{if(event.button!==0)return;dragStart={x:event.clientX,y:event.clientY,mapX,mapY};mapMoved=false;mapSvg.classList.add("dragging");mapSvg.setPointerCapture(event.pointerId)});
mapSvg.addEventListener("pointermove",event=>{if(!dragStart)return;const rect=mapSvg.getBoundingClientRect(),dx=(event.clientX-dragStart.x)*900/rect.width,dy=(event.clientY-dragStart.y)*650/rect.height;if(Math.abs(dx)+Math.abs(dy)>3)mapMoved=true;mapX=dragStart.mapX+dx;mapY=dragStart.mapY+dy;applyMapTransform()});
function stopDrag(event){if(!dragStart)return;dragStart=null;mapSvg.classList.remove("dragging");if(mapSvg.hasPointerCapture(event.pointerId))mapSvg.releasePointerCapture(event.pointerId);setTimeout(()=>mapMoved=false,0)}
mapSvg.addEventListener("pointerup",stopDrag);mapSvg.addEventListener("pointercancel",stopDrag);mapSvg.addEventListener("click",event=>{if(mapMoved){event.preventDefault();event.stopImmediatePropagation()}},true);
paths.forEach(path=>path.addEventListener("dblclick",event=>{event.preventDefault();selectedCommune=Number(path.dataset.comuna);selectCommune(selectedCommune);zoomToCommune(selectedCommune)}));
const originalSelectCommune=selectCommune;
selectCommune=function(comuna){originalSelectCommune(comuna);const row=byCommune[selectedCommune],ordered=[...ROWS].sort((a,b)=>value(b)-value(a)),rank=ordered.findIndex(item=>Number(item.comuna)===selectedCommune)+1,average=mode==="total"?cityValue(indicator())/15:cityValue(indicator()),current=value(row),delta=average?((current-average)/average)*100:0;communeSelect.value=String(selectedCommune);document.getElementById("rank-badge").textContent=`#${rank} de 15`;document.getElementById("comparison-text").textContent=Math.abs(delta)<.05?"En el promedio de la ciudad":`${format(Math.abs(delta),0)} % ${delta>0?"por encima":"por debajo"} del promedio`;document.getElementById("comparison-base").textContent=`Promedio: ${format(average,decimals(key()))} ${unit()}`;const values=ROWS.map(value),min=Math.min(...values),max=Math.max(...values);document.getElementById("legend-steps").innerHTML=Array.from({length:5},(_,index)=>{const v=min+(max-min)*index/4;return `<span class="legend-step" style="background:${color(v,min,max)}" title="${format(v,decimals(key()))}"></span>`}).join("");applyMapTransform();updateWebGLSelection()};
communeSelect.addEventListener("change",()=>{selectCommune(communeSelect.value);focusCommune(communeSelect.value)});document.addEventListener("keydown",event=>{if(event.key==="Escape")resetMap()});
const LOCAL_MAP_STYLE={version:8,name:"Cerebro BA Maqueta 3D",light:{anchor:"viewport",color:"#ffffff",intensity:0.75,position:[1.6,210,42]},sources:{},layers:[{id:"background",type:"background",paint:{"background-color":"#050c17"}}]};
const ONLINE_MAP_STYLE="https://tiles.openfreemap.org/styles/liberty";
const mapStage=document.getElementById("map-stage"),connectionBadge=document.getElementById("map-connection"),dimensionButton=document.getElementById("dimension-toggle"),scaleButton=document.getElementById("scale-toggle"),streetsButton=document.getElementById("streets-toggle"),orbitButton=document.getElementById("orbit-toggle"),resetCameraButton=document.getElementById("reset-camera");
let glMap=null,glReady=false,glHandlersBound=false,glSelected=null,glHovered=null,is3D=true,showMaquetaFlags=false,streetsOnline=false,streetRequest=false,glPopup=null,glMarkers=[],orbitFrame=null;
function syncFlagsVisibility(){const visible=!is3D||showMaquetaFlags;glMarkers.forEach(item=>{if(item.anchor)item.anchor.classList.toggle("hidden-flag",!visible)})}
function setConnection(text,online=false){document.documentElement.dataset.mapBase=online?"online":"local";connectionBadge.lastChild.textContent=text;connectionBadge.classList.toggle("online",online);streetsButton.textContent=showMaquetaFlags?"Fondo: Maqueta (con etiquetas)":"Fondo: Maqueta";streetsButton.classList.toggle("active",showMaquetaFlags||online);streetsButton.setAttribute("aria-pressed",String(showMaquetaFlags||online));syncFlagsVisibility()}
function buildStageGrid(){const features=[];const cx=-58.442,cy=-34.616;for(let lon=-58.58;lon<=-58.30;lon+=0.02){features.push({type:"Feature",properties:{kind:"grid"},geometry:{type:"LineString",coordinates:[[lon,-34.73],[lon,-34.50]]}})}for(let lat=-34.73;lat<=-34.50;lat+=0.02){features.push({type:"Feature",properties:{kind:"grid"},geometry:{type:"LineString",coordinates:[[-58.58,lat],[-58.30,lat]]}})}[0.068,0.105,0.138].forEach((r,idx)=>{const ring=[];for(let a=0;a<=64;a++){const rad=a*Math.PI*2/64;ring.push([cx+Math.cos(rad)*r*1.18,cy+Math.sin(rad)*r*0.95])}features.push({type:"Feature",properties:{kind:idx===1?"ring-accent":"ring"},geometry:{type:"LineString",coordinates:ring}})});return {type:"FeatureCollection",features}}
function insetGeometry(geometry,cx,cy,scale=0.915){const shrinkRing=ring=>ring.map(pt=>[cx+(pt[0]-cx)*scale,cy+(pt[1]-cy)*scale]);if(geometry.type==="Polygon")return {type:"Polygon",coordinates:geometry.coordinates.map(shrinkRing)};if(geometry.type==="MultiPolygon")return {type:"MultiPolygon",coordinates:geometry.coordinates.map(poly=>poly.map(shrinkRing))};return geometry}
function communeHeight(v,min,max){const t=max===min ? .65 :Math.max(0,Math.min(1,(v-min)/(max-min)));return (260+Math.pow(t,0.88)*2900)*heightBoost}
function webglData(){const values=ROWS.map(value),min=Math.min(...values),max=Math.max(...values);return {type:"FeatureCollection",features:MAP_GEOJSON.features.map(feature=>{const row=byCommune[Number(feature.properties.comuna)],v=value(row),rgb=rgbTuple(v,min,max),h=communeHeight(v,min,max);return {...feature,properties:{...feature.properties,_value:v,_color:color(v,min,max),_wall_color:shadeRgb(rgb,0.58),_roof_color:shadeRgb(rgb,1.15),_height:h,_wall_top:Math.max(90,h-55)}}})}}
function webglInsetPrisms(){const base=webglData();return {type:"FeatureCollection",features:base.features.map(feature=>({...feature,geometry:insetGeometry(feature.geometry,feature.properties.label_lon,feature.properties.label_lat,0.915)}))}}
function restyleDarkBlueprint(style){const allowed=[];(style.layers||[]).forEach(layer=>{if(layer.type==="symbol")return;if(layer.type==="background"){allowed.push({...layer,paint:{"background-color":"#050c17"}});return}if(layer.id.includes("water")){allowed.push({...layer,paint:layer.type==="fill"?{"fill-color":"#08182b","fill-opacity":0.9}:{"line-color":"#123252"}});return}if(layer.type==="line"&&(layer.id.includes("road")||layer.id.includes("Street")||layer.id.includes("transportation")||layer.id.includes("highway"))){allowed.push({...layer,paint:{"line-color":"rgba(49,199,217,0.14)","line-width":0.85}});return}});return {...style,light:{anchor:"viewport",color:"#ffffff",intensity:0.75,position:[1.6,210,42]},layers:allowed}}
function installWebGLLayers(){if(!glMap||!glMap.isStyleLoaded())return;if(!glMap.getSource("cerebro-grid"))glMap.addSource("cerebro-grid",{type:"geojson",data:buildStageGrid()});if(!glMap.getLayer("stage-grid"))glMap.addLayer({id:"stage-grid",type:"line",source:"cerebro-grid",paint:{"line-color":["case",["==",["get","kind"],"ring-accent"],"rgba(73,229,181,0.28)",["==",["get","kind"],"ring"],"rgba(49,199,217,0.18)","rgba(49,199,217,0.07)"],"line-width":["case",["==",["get","kind"],"ring-accent"],1.5,1]}});if(!glMap.getSource("cerebro-comunas"))glMap.addSource("cerebro-comunas",{type:"geojson",data:webglData()});if(!glMap.getSource("cerebro-prisms"))glMap.addSource("cerebro-prisms",{type:"geojson",data:webglInsetPrisms()});if(!glMap.getLayer("communes-flat"))glMap.addLayer({id:"communes-flat",type:"fill",source:"cerebro-comunas",paint:{"fill-color":["case",["boolean",["feature-state","selected"],false],"#ffc857",["get","_color"]],"fill-opacity":.22}});if(!glMap.getLayer("communes-outline"))glMap.addLayer({id:"communes-outline",type:"line",source:"cerebro-comunas",paint:{"line-color":["case",["boolean",["feature-state","selected"],false],"#ffc857","rgba(49,199,217,.52)"],"line-width":["case",["boolean",["feature-state","selected"],false],2.8,1.4]}});if(!glMap.getLayer("communes-3d"))glMap.addLayer({id:"communes-3d",type:"fill-extrusion",source:"cerebro-prisms",paint:{"fill-extrusion-color":["case",["boolean",["feature-state","selected"],false],"#c7911e",["boolean",["feature-state","hover"],false],"#2eb8a6",["get","_wall_color"]],"fill-extrusion-base":0,"fill-extrusion-height":["case",["boolean",["feature-state","selected"],false],["+",["get","_wall_top"],340],["boolean",["feature-state","hover"],false],["+",["get","_wall_top"],170],["get","_wall_top"]],"fill-extrusion-opacity":.96,"fill-extrusion-vertical-gradient":true}});if(!glMap.getLayer("communes-roof"))glMap.addLayer({id:"communes-roof",type:"fill-extrusion",source:"cerebro-prisms",paint:{"fill-extrusion-color":["case",["boolean",["feature-state","selected"],false],"#ffd46b",["boolean",["feature-state","hover"],false],"#9bf8db",["get","_roof_color"]],"fill-extrusion-base":["case",["boolean",["feature-state","selected"],false],["+",["get","_wall_top"],340],["boolean",["feature-state","hover"],false],["+",["get","_wall_top"],170],["get","_wall_top"]],"fill-extrusion-height":["case",["boolean",["feature-state","selected"],false],["+",["get","_height"],340],["boolean",["feature-state","hover"],false],["+",["get","_height"],170],["get","_height"]],"fill-extrusion-opacity":.98,"fill-extrusion-vertical-gradient":false}});if(!glMap.getLayer("communes-hit"))glMap.addLayer({id:"communes-hit",type:"fill",source:"cerebro-comunas",paint:{"fill-color":"#ffffff","fill-opacity":.01}});glReady=true;document.documentElement.dataset.mapLayers="ready";updateWebGLMap();updateWebGLSelection();bindWebGLEvents();updateMarkerValues()}
function updateWebGLMap(){if(!glReady||!glMap||!glMap.getSource("cerebro-comunas"))return;glMap.getSource("cerebro-comunas").setData(webglData());if(glMap.getSource("cerebro-prisms"))glMap.getSource("cerebro-prisms").setData(webglInsetPrisms());if(glMap.getLayer("communes-3d")){glMap.setPaintProperty("communes-3d","fill-extrusion-opacity",is3D ? .96 : 0);if(glMap.getLayer("communes-roof"))glMap.setPaintProperty("communes-roof","fill-extrusion-opacity",is3D ? .98 : 0);glMap.setPaintProperty("communes-flat","fill-opacity",is3D ? .22 : .88)}updateWebGLSelection();updateMarkerValues()}
function updateWebGLSelection(){if(!glReady||!glMap||!glMap.getSource("cerebro-comunas"))return;if(glSelected!==null){glMap.setFeatureState({source:"cerebro-comunas",id:glSelected},{selected:false});if(glMap.getSource("cerebro-prisms"))glMap.setFeatureState({source:"cerebro-prisms",id:glSelected},{selected:false})}glSelected=selectedCommune;glMap.setFeatureState({source:"cerebro-comunas",id:glSelected},{selected:true});if(glMap.getSource("cerebro-prisms"))glMap.setFeatureState({source:"cerebro-prisms",id:glSelected},{selected:true});glMarkers.forEach(item=>{const sel=item.comuna===selectedCommune;item.element.classList.toggle("selected",sel);if(item.anchor)item.anchor.classList.toggle("selected",sel)});updateMarkerAltitudes()}
function updateMarkerAltitudes(){if(!glMarkers.length)return;const values=ROWS.map(value),min=Math.min(...values),max=Math.max(...values);const pitchRad=(glMap?glMap.getPitch():56)*Math.PI/180,zoomFactor=glMap?Math.min(1.6,Math.max(0.75,Math.pow(2,(glMap.getZoom()-10.48)*0.65))):1;glMarkers.forEach(item=>{const row=byCommune[item.comuna],t=max===min?0.5:Math.max(0,Math.min(1,(value(row)-min)/(max-min)));const px=is3D?-Math.round((10+t*26+(item.comuna===selectedCommune?6:0))*Math.sin(pitchRad)*zoomFactor):0;item.element.style.setProperty("--lift",`${px}px`)})}
function updateMarkerValues(){glMarkers.forEach(item=>{const row=byCommune[item.comuna];if(item.sub)item.sub.textContent=format(value(row),decimals(key()))});updateMarkerAltitudes()}
function popupContent(properties){const root=document.createElement("div"),title=document.createElement("strong"),metric=document.createElement("span"),detail=document.createElement("small");title.textContent=`Comuna ${properties.comuna}`;metric.textContent=`${format(properties._value,decimals(key()))} ${unit()}`;detail.textContent=properties.barrios;root.append(title,metric,detail);return root}
function bindWebGLEvents(){if(glHandlersBound)return;glHandlersBound=true;glPopup=new maplibregl.Popup({closeButton:false,closeOnClick:false,offset:20});glMap.on("mousemove","communes-hit",event=>{if(!event.features?.length)return;glMap.getCanvas().style.cursor="pointer";const featId=Number(event.features[0].properties.comuna);if(glHovered!==null&&glHovered!==featId){glMap.setFeatureState({source:"cerebro-comunas",id:glHovered},{hover:false});if(glMap.getSource("cerebro-prisms"))glMap.setFeatureState({source:"cerebro-prisms",id:glHovered},{hover:false})}glHovered=featId;glMap.setFeatureState({source:"cerebro-comunas",id:glHovered},{hover:true});if(glMap.getSource("cerebro-prisms"))glMap.setFeatureState({source:"cerebro-prisms",id:glHovered},{hover:true});glPopup.setLngLat(event.lngLat).setDOMContent(popupContent(event.features[0].properties)).addTo(glMap)});glMap.on("mouseleave","communes-hit",()=>{glMap.getCanvas().style.cursor="";if(glHovered!==null){glMap.setFeatureState({source:"cerebro-comunas",id:glHovered},{hover:false});if(glMap.getSource("cerebro-prisms"))glMap.setFeatureState({source:"cerebro-prisms",id:glHovered},{hover:false})}glHovered=null;glPopup.remove()});glMap.on("click","communes-hit",event=>{if(!event.features?.length)return;stopOrbit();const comuna=Number(event.features[0].properties.comuna);selectCommune(comuna);focusCommune(comuna)});glMap.on("move",updateMarkerAltitudes);glMap.on("mousedown",stopOrbit);glMap.on("touchstart",stopOrbit)}
function createWebGLLabels(){MAP_GEOJSON.features.forEach(feature=>{const anchor=document.createElement("div");anchor.className="gl-marker-anchor hidden-flag";const element=document.createElement("button");element.type="button";element.className="gl-commune-label";const title=document.createElement("span");title.textContent=`C${feature.properties.comuna}`;const sub=document.createElement("small");element.append(title,sub);element.setAttribute("aria-label",`Seleccionar Comuna ${feature.properties.comuna}`);element.addEventListener("click",event=>{event.stopPropagation();stopOrbit();selectCommune(feature.properties.comuna);focusCommune(feature.properties.comuna)});anchor.appendChild(element);const marker=new maplibregl.Marker({element:anchor,anchor:"center"}).setLngLat([feature.properties.label_lon,feature.properties.label_lat]).addTo(glMap);glMarkers.push({comuna:Number(feature.properties.comuna),anchor,element,sub,marker})});updateMarkerValues();syncFlagsVisibility()}
function focusCommune(comuna){if(glReady&&glMap){stopOrbit();const feature=MAP_GEOJSON.features.find(item=>Number(item.properties.comuna)===Number(comuna));glMap.flyTo({center:[feature.properties.label_lon,feature.properties.label_lat],zoom:isMobileView()?10.95:11.55,pitch:is3D?(isMobileView()?54:58):0,bearing:is3D?-24:0,duration:1050,essential:true})}else zoomToCommune(comuna)}
function setDimension(next3D){is3D=next3D;if(!is3D)stopOrbit();if(is3D)showMaquetaFlags=false;document.documentElement.dataset.mapDimension=is3D?"3d":"2d";dimensionButton.textContent=is3D?"Relieve 3D":"Planta 2D";dimensionButton.classList.toggle("active",is3D);dimensionButton.setAttribute("aria-pressed",String(is3D));syncFlagsVisibility();setConnection(showMaquetaFlags?"Maqueta con etiquetas C1–C15":"Bloques 3D separados por comuna · Techo claro y paredes sombreadas",streetsOnline);updateWebGLMap();if(glMap)glMap.easeTo({pitch:is3D?(isMobileView()?52:56):0,bearing:is3D?-24:0,duration:850,essential:true})}
function toggleHeightScale(){heightBoost=heightBoost===1?1.55:1;scaleButton.textContent=heightBoost>1?"Altura: Alta":"Altura: Normal";scaleButton.classList.toggle("active",heightBoost>1);scaleButton.setAttribute("aria-pressed",String(heightBoost>1));updateWebGLMap()}
function toggleOrbit(){if(!glMap)return;if(orbitFrame){stopOrbit();return}if(!is3D)setDimension(true);orbitButton.classList.add("active");orbitButton.setAttribute("aria-pressed","true");let last=performance.now();function step(now){if(!orbitFrame)return;const dt=(now-last)/1000;last=now;glMap.setBearing((glMap.getBearing()+dt*11)%360);orbitFrame=requestAnimationFrame(step)}orbitFrame=requestAnimationFrame(step)}
function stopOrbit(){if(orbitFrame){cancelAnimationFrame(orbitFrame);orbitFrame=null}if(orbitButton){orbitButton.classList.remove("active");orbitButton.setAttribute("aria-pressed","false")}}
async function connectStreets(){if(!glMap||streetRequest||streetsOnline)return;streetRequest=true;setConnection("Cargando plano arquitectónico oscuro…");const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),6500);try{const response=await fetch(ONLINE_MAP_STYLE,{signal:controller.signal});if(!response.ok)throw new Error(`HTTP ${response.status}`);const style=await response.json();streetsOnline=true;glMap.setStyle(restyleDarkBlueprint(style));setConnection("Plano arquitectónico oscuro + Bloques 3D",true)}catch(error){streetsOnline=false;setConnection("Bloques 3D separados por comuna · Techo claro y paredes sombreadas");console.info("Mapa base no disponible; se conserva la maqueta 3D local.",error.message)}finally{clearTimeout(timer);streetRequest=false;if(!streetsOnline)setConnection("Bloques 3D separados por comuna · Techo claro y paredes sombreadas")}}
function disconnectStreets(){streetsOnline=false;glMap.setStyle(LOCAL_MAP_STYLE);setConnection("Bloques 3D separados por comuna · Techo claro y paredes sombreadas")}
function supportsWebGL(){try{const canvas=document.createElement("canvas");return Boolean(window.WebGLRenderingContext&&(canvas.getContext("webgl2")||canvas.getContext("webgl")))}catch(error){return false}}
function startWebGLMap(){document.documentElement.dataset.mapRuntime="checking";document.documentElement.dataset.mapDimension="3d";try{if(!window.maplibregl||!supportsWebGL()){document.documentElement.dataset.mapRuntime="svg-fallback";document.getElementById("map-hint").textContent="Vista isométrica SVG de respaldo · WebGL no está disponible";return}mapStage.classList.add("webgl-active");document.getElementById("map-hint").textContent=isMobileView()?"1 dedo: mover · 2 dedos: girar/zoom · tocá una comuna":"Arrastrá para mover · clic derecho o Ctrl + arrastrar para girar 3D · rueda para zoom";const cam=defaultCamera();glMap=new maplibregl.Map({container:"maplibre-map",style:LOCAL_MAP_STYLE,center:cam.center,zoom:cam.zoom,pitch:cam.pitch,bearing:cam.bearing,maxPitch:78,antialias:true,attributionControl:false});document.documentElement.dataset.mapRuntime="webgl";glMap.addControl(new maplibregl.NavigationControl({visualizePitch:true}),"top-right");if(!isMobileView())glMap.addControl(new maplibregl.FullscreenControl(),"top-right");createWebGLLabels();setConnection("Bloques 3D separados por comuna · Techo claro y paredes sombreadas");glMap.on("style.load",()=>{installWebGLLayers();if(streetsOnline)setConnection("Plano arquitectónico oscuro + Bloques 3D",true)});glMap.once("load",updateWebGLSelection);window.addEventListener("resize",()=>{if(glMap)glMap.resize()})}catch(error){mapStage.classList.remove("webgl-active");document.documentElement.dataset.mapRuntime="svg-error";document.documentElement.dataset.mapError=String(error?.message||error);document.getElementById("map-hint").textContent="Vista SVG de respaldo · el modo 3D no pudo iniciar";console.warn("MapLibre no pudo iniciar; se usa el respaldo SVG.",error)}}
dimensionButton.addEventListener("click",()=>setDimension(!is3D));scaleButton.addEventListener("click",toggleHeightScale);orbitButton.addEventListener("click",toggleOrbit);resetCameraButton.addEventListener("click",resetMap);streetsButton.addEventListener("click",()=>{showMaquetaFlags=!showMaquetaFlags;setConnection(showMaquetaFlags?"Maqueta con etiquetas C1–C15":"Bloques 3D separados por comuna · Techo claro y paredes sombreadas",streetsOnline)});
render();
selectCommune(selectedCommune);
startWebGLMap();
</script>
</body>
</html>'''

    replacements = {
        "__BODY_CLASS__": status_class,
        "__STATUS_CLASS__": status_class,
        "__STATUS_LABEL__": status_label,
        "__POPULATION__": _es(population_total),
        "__YEAR__": str(population_year),
        "__NOTICE__": notice,
        "__MAP_PATHS__": map_paths,
        "__RUN_ID__": run_id,
        "__GENERATED__": generated,
        "__MAP_SOURCE__": map_source,
        "__SOURCES__": _sources_html(metadata),
        "__FOOTER_LABEL__": footer_label,
        "__ROWS_JSON__": _json_script(numeric_rows),
        "__GEOJSON_JSON__": _json_script(map_geojson),
        "__INDICATORS_JSON__": _json_script(INDICATORS),
    }
    output_html = template
    for marker, replacement in replacements.items():
        output_html = output_html.replace(marker, replacement)
    if "__" in output_html:
        raise ValueError("quedó un marcador sin reemplazar en el dashboard")

    output = APP / "index.html"
    atomic_write_text(output, output_html)
    print(f"[ok] Observatorio -> {display_path(output)} ({len(output_html):,} bytes)")
    print(f"     Maqueta 3D + SVG: 15 comunas · fuente {map_source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
