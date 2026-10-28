"""Contrato F10 y comprobación independiente de cinco tasas en 15 comunas."""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from poblacion import validar, extraer_xls, normalizar


def fixture():
    return [dict(comuna=c, poblacion=100000+c*1000, anio=2022) for c in range(1, 16)]


class Poblacion(unittest.TestCase):
    def test_contrato_valido(self):
        self.assertEqual(len(validar(fixture())), 15)

    def test_faltante_duplicada_fuera_rango(self):
        for rows in (fixture()[:-1], fixture()+[fixture()[0]],
                     [dict(row, comuna=16) if row['comuna']==15 else row for row in fixture()]):
            with self.assertRaises(ValueError):
                validar(rows)

    def test_numeros_y_anio_invalidos(self):
        for key, values in {'poblacion': [0, -1, 1.5, 'NaN', 'inf', None],
                            'anio': [2026, 2022.5], 'comuna': [1.5]}.items():
            for value in values:
                rows = fixture(); rows[0][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validar(rows)

    def test_xls_oficial_y_tres_comunas(self):
        rows = extraer_xls(ROOT / 'evidencias/f10/PB2_22nb.xls')
        self.assertEqual(sum(r['poblacion'] for r in rows), 3121707)
        self.assertEqual([rows[i]['poblacion'] for i in (0, 7, 14)], [223554, 204367, 196876])

    def test_ausente_no_se_sustituye_por_cero(self):
        with self.assertRaises(ValueError):
            normalizar([{'comuna': 1}], fixture()[:-1])

    def test_integracion_demo_y_tasas(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            base = Path(folder)
            env = dict(os.environ, CEREBRO_MODE='demo',
                       CEREBRO_RAW_DIR=str(base/'raw'), CEREBRO_SILVER_DIR=str(base/'silver'),
                       CEREBRO_GOLD_DIR=str(base/'gold'), CEREBRO_APP_DIR=str(base/'app'))
            def run(script, success=True):
                result = subprocess.run([sys.executable, str(ROOT/'scripts'/script)],
                                        env=env, capture_output=True, text=True, errors='replace')
                self.assertEqual(result.returncode == 0, success, result.stdout+result.stderr)
            for script in ('_gen_seed.py', 'transform_silver.py', 'verify.py', 'build_gold.py'):
                run(script)
            def read(path):
                with path.open(encoding='utf-8') as stream:
                    return list(csv.DictReader(stream))
            rows = read(base/'gold/indicadores_por_comuna.csv')
            self.assertEqual(len(rows), 15)
            for row in rows:
                c = int(row['comuna']); pop = 100000+c*1000
                def domain(name):
                    return [r for r in read(base/'silver'/f'{name}.csv') if int(r['comuna']) == c]
                expected = {
                    'estaciones_ecobici_por_10000_hab': len(domain('ecobici'))*10000/pop,
                    'km_ciclovias_por_10000_hab': sum(float(r['long_metros']) for r in domain('ciclovias'))/1000*10000/pop,
                    'espacios_verdes_por_10000_hab': len(domain('espacios_verdes'))*10000/pop,
                    'm2_verdes_por_hab': sum(float(r['area_m2']) for r in domain('espacios_verdes'))/pop,
                    'hospitales_por_10000_hab': len(domain('hospitales'))*10000/pop,
                }
                for name, value in expected.items():
                    self.assertAlmostEqual(float(row[name]), round(value, 6), places=6)
                self.assertEqual(int(row['anio_poblacion']), 2022)
            meta = json.loads((base/'gold/_meta.json').read_text(encoding='utf-8'))
            self.assertEqual(meta['provenance_status'], 'demo')
            self.assertEqual(meta['fuentes']['poblacion']['_origen'], 'semilla_demo')
            original = (base/'silver/poblacion.csv').read_bytes()
            with (base/'silver/poblacion.csv').open('a') as f:
                f.write('1,999,2022\n')
            run('build_gold.py', success=False)
            (base/'silver/poblacion.csv').write_bytes(original)
            with (base/'raw/poblacion/seed.csv').open('a') as f:
                f.write('1,999,2022\n')
            run('build_gold.py', success=False)
            run('verify.py', success=False)


if __name__ == '__main__':
    unittest.main()
