"""Adaptadores de los recursos oficiales; Bronze siempre conserva sus bytes."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from poblacion import entero


def identifier(text):
    # Clave estable, independiente del orden de descarga; colisiones se rechazan.
    return int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:15], 16)


def document(path):
    from pyproj import CRS, Transformer
    doc = json.loads(Path(path).read_bytes())
    declared = doc.get('crs', {}).get('properties', {}).get('name')
    if not declared:
        raise ValueError(f'{path}: falta CRS explícito')
    source = CRS.from_user_input(declared)
    return doc, Transformer.from_crs(source, 4326, always_xy=True)


def adaptar(domain, path, comunas_path):
    from shapely.geometry import shape, Point
    from shapely.ops import transform
    from shapely import make_valid
    from pyproj import Transformer
    to_metric = Transformer.from_crs(4326, 9498, always_xy=True)
    boundaries, conversion = document(comunas_path)
    polygons = [(entero(f['properties']['comuna']),
                 transform(conversion.transform, shape(f['geometry'])))
                for f in boundaries['features']]
    if len(polygons) != 15 or {c for c, _ in polygons} != set(range(1, 16)):
        raise ValueError('La capa auxiliar debe contener 15 comunas únicas')

    def locate(lon, lat):
        matches = [c for c, polygon in polygons if polygon.covers(Point(lon, lat))]
        if len(matches) != 1:
            raise ValueError('comuna_espacial_ambigua_o_ausente')
        return matches[0]

    rejects, audit = Counter(), Counter()
    quarantine = []
    output, seen = [], set()
    if Path(path).suffix == '.csv':
        with Path(path).open(encoding='utf-8-sig', newline='') as stream:
            source_rows = list(csv.DictReader(stream))
        converter = None
    else:
        doc, converter = document(path)
        source_rows = doc['features']
    for source in source_rows:
        try:
            r = source if converter is None else source['properties']
            if domain == 'ecobici':
                lat, lon = float(r['latitud']), float(r['longitud'])
                c = locate(lon, lat)
                out = dict(id=entero(r['id']), nombre=r['nombre'].strip(), comuna=c,
                           lat=lat, lon=lon, anclajes_totales=None)
                audit['comuna_asignada_por_geometria'] += 1
            elif domain == 'ciclovias':
                # La comuna y longitud del segmento se conservan como declara la fuente.
                out = dict(id=entero(r['id']), nombre=r['nombre'].strip(),
                           comuna=entero(r['comuna']), long_metros=float(r['longitud_m']), tipo=r['tipo'])
            else:
                geom = transform(converter.transform, shape(source['geometry']))
                if geom.is_empty:
                    raise ValueError('geometria_vacia')
                if not geom.is_valid:
                    geom = make_valid(geom)
                    audit['geometria_reparada_para_area_y_punto'] += 1
                point = geom.representative_point()
                lon, lat = point.x, point.y
                if domain == 'hospitales':
                    if geom.geom_type != 'Point':
                        raise ValueError('hospital_no_puntual')
                    out = dict(id=identifier(r['fna'].strip()+'|'+r['dir'].strip()),
                               nombre=r['fna'].strip(), tipo=r['gna'], comuna=entero(r['com']),
                               direccion=r['dir'], lat=lat, lon=lon)
                else:
                    # La superficie se calcula en el CRS métrico oficial CABA 2019.
                    metric = transform(to_metric.transform, geom)
                    out = dict(id=entero(r['id']), nombre=(r['nombre'] or r['nom_mapa'] or '').strip(),
                               comuna=entero(r['comuna']), area_m2=metric.area,
                               clasificacion=r['clasificac'], lat=lat, lon=lon)
            if not 1 <= out['comuna'] <= 15:
                raise ValueError('comuna_fuera_de_rango')
            for key in ('long_metros', 'area_m2'):
                if key in out and (not math.isfinite(out[key]) or out[key] <= 0):
                    raise ValueError(key+'_no_positivo')
            if 'lat' in out and not (-34.72 <= out['lat'] <= -34.51 and -58.55 <= out['lon'] <= -58.32):
                raise ValueError('coordenadas_fuera_de_caba')
            if out['id'] in seen:
                raise ValueError('id_duplicado')
            seen.add(out['id'])
            output.append(out)
        except (ValueError, TypeError, KeyError) as error:
            rejects[str(error)] += 1
            quarantine.append({'id': r.get('id'), 'nombre': r.get('nombre', r.get('fna')),
                               'motivo': str(error)})
    return output, dict(rejects), len(source_rows), {**audit, 'cuarentena': quarantine}
