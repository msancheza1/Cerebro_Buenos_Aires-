"""Contratos oficiales: unidades, CRS, comuna espacial y cuarentena explícita."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from infraestructura import adaptar
from pipeline_common import sha256_file
import verify


class ContratosOficiales(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.boundaries = self.folder / 'comunas.geojson'
        features = []
        for c in range(1, 16):
            x = -58.54 + (c-1)*.01
            features.append({'type': 'Feature', 'properties': {'comuna': c},
                'geometry': {'type': 'Polygon', 'coordinates': [[[x,-34.65],
                 [x+.01,-34.65],[x+.01,-34.64],[x,-34.64],[x,-34.65]]]}})
        self.geo(self.boundaries, features, 'EPSG:4326')

    def geo(self, path, features, crs):
        path.write_text(json.dumps({'type': 'FeatureCollection',
            'crs': {'type': 'name', 'properties': {'name': crs}}, 'features': features}), encoding='utf-8')

    def csv(self, name, rows):
        path = self.folder / name
        with path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        return path

    def test_ecobici_sin_anclajes_y_fuera_de_poligonos(self):
        path = self.csv('eco.csv', [dict(id=1,nombre='Dentro',latitud=-34.645,longitud=-58.535),
                                    dict(id=2,nombre='Fuera',latitud=0,longitud=0)])
        rows, rejects, count, audit = adaptar('ecobici', path, self.boundaries)
        self.assertEqual((len(rows), count), (1, 2))
        self.assertEqual(rows[0]['comuna'], 1)
        self.assertIsNone(rows[0]['anclajes_totales'])
        self.assertEqual(sum(rejects.values()), 1)
        self.assertEqual(audit['cuarentena'][0]['id'], '2')
        self.assertEqual(verify.CHECKS['ecobici'](rows), [])

    def test_longitud_m_y_duplicados(self):
        row = dict(id=9,nombre='Tramo',comuna=1,longitud_m='52.98',tipo='Ciclovía')
        path = self.csv('ciclo.csv', [row,row])
        rows, rejects, _, _ = adaptar('ciclovias', path, self.boundaries)
        self.assertEqual(rows[0]['long_metros'], 52.98)
        self.assertEqual(rejects, {'id_duplicado': 1})

    def test_hospital_crs_declarado_y_clave_estable(self):
        path = self.folder / 'hospital.geojson'
        feature = {'type':'Feature', 'properties': {'fna':'Hospital A','gna':'General',
                   'dir':'Calle 1','com':4}, 'geometry':{'type':'Point',
                   'coordinates':[26549.56742604346,69922.54409977954]}}
        self.geo(path,[feature],'EPSG:9498')
        rows, _, _, _ = adaptar('hospitales',path,self.boundaries)
        self.assertAlmostEqual(rows[0]['lon'],-58.3918835182,places=7)
        self.assertAlmostEqual(rows[0]['lat'],-34.6299496749,places=7)
        again, _, _, _ = adaptar('hospitales',path,self.boundaries)
        self.assertEqual(rows[0]['id'], again[0]['id'])

    def test_area_metrica_y_crs_ausente(self):
        path = self.folder / 'verde.geojson'
        feature = {'type':'Feature','properties':{'id':3,'nombre':'Plaza','comuna':1,
                   'clasificac':'PLAZA'}, 'geometry':{'type':'Polygon','coordinates':[[
                   [25000,70000],[25010,70000],[25010,70010],[25000,70010],[25000,70000]]]}}
        self.geo(path,[feature],'EPSG:9498')
        rows, rejects, _, _ = adaptar('espacios_verdes',path,self.boundaries)
        self.assertEqual(rejects,{})
        self.assertAlmostEqual(rows[0]['area_m2'],100,places=3)
        doc=json.loads(path.read_bytes()); del doc['crs']; path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'CRS'):
            adaptar('espacios_verdes',path,self.boundaries)

    def test_alteracion_de_auxiliar_bloquea_verificacion(self):
        raw=self.folder/'raw.csv'; raw.write_text('original')
        silver=self.folder/'ecobici.csv'; silver.write_text('silver')
        meta=dict(silver_sha256=sha256_file(silver),filas_entrada=1,filas_descartadas=0,
                  _origen='descarga_oficial',raw_file=str(raw),raw_sha256=sha256_file(raw),
                  auxiliares=[dict(raw_file=str(self.boundaries),sha256=sha256_file(self.boundaries))])
        (self.folder/'ecobici.meta.json').write_text(json.dumps(meta))
        self.boundaries.write_text('{}')
        with patch.object(verify,'SILVER',self.folder):
            errors,_=verify._metadata_violations('ecobici',silver)
        self.assertIn(('auxiliar_sha256_no_coincide',1), errors)


if __name__ == '__main__':
    unittest.main()
