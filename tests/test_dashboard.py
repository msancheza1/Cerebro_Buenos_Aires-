"""Pruebas del dashboard híbrido: mapa WebGL 3D y respaldo SVG autocontenido."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_dashboard


class Dashboard(unittest.TestCase):
    def test_maplibre_local_tiene_version_y_hash_fijados(self):
        expected = {
            "maplibre-gl.js": "45a9b07a9189ce56054c620a947ccf41e291e58c95e9b61533b740aaa65ee5cb",
            "maplibre-gl.css": "ab1e70d59ec40465bae7e7030da2f3ccf28133fd502e62bd598eefbadfd7a732",
            "MAPLIBRE-LICENSE.txt": "ee5fc05a0677eaf69601d2c7db0d9ecd6cc27c3abc1d0733bc9ed34707cf8ef2",
        }
        vendor = ROOT / "app/vendor"
        for name, digest in expected.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((vendor / name).read_bytes()).hexdigest(), digest)
        readme = (vendor / "README.md").read_text(encoding="utf-8")
        self.assertIn("MapLibre GL JS 5.24.0", readme)
        self.assertIn("BSD de 3 cláusulas", readme)

    def test_capa_oficial_contiene_15_comunas_rutas_y_etiquetas(self):
        metadata = json.loads((ROOT / "evidencias/oficial/gold/_meta.json").read_text(encoding="utf-8"))
        features, source = build_dashboard._load_boundaries(metadata)
        self.assertTrue(source.is_file())
        self.assertEqual([feature["comuna"] for feature in features], list(range(1, 16)))
        paths = build_dashboard._map_paths(features)
        self.assertEqual(paths.count('class="commune"'), 15)
        self.assertEqual(paths.count('class="map-label"'), 15)
        self.assertEqual(paths.count('data-center-x='), 15)
        for comuna in range(1, 16):
            self.assertIn(f'data-comuna="{comuna}"', paths)
            self.assertIn(f'>C{comuna}</text>', paths)
        geojson = build_dashboard._map_geojson(
            features, [{"comuna": comuna} for comuna in range(1, 16)]
        )
        self.assertEqual(len(geojson["features"]), 15)
        self.assertEqual({feature["id"] for feature in geojson["features"]}, set(range(1, 16)))
        for feature in geojson["features"]:
            self.assertIsInstance(feature["properties"]["label_lon"], float)
            self.assertIsInstance(feature["properties"]["label_lat"], float)

    def _generate(self, gold: Path) -> str:
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            output = Path(folder) / "app"
            env = dict(os.environ, CEREBRO_GOLD_DIR=str(gold), CEREBRO_APP_DIR=str(output))
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_dashboard.py")],
                cwd=ROOT, env=env, capture_output=True, text=True, errors="replace"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return (output / "index.html").read_text(encoding="utf-8")

    def test_vista_oficial_es_autocontenida_y_no_se_marca_como_demo(self):
        document = self._generate(ROOT / "evidencias/oficial/gold")
        self.assertEqual(document.count('class="commune"'), 15)
        self.assertIn("Mapa coroplético interactivo", document)
        self.assertIn('const ROWS=', document)
        self.assertIn("Datos oficiales", document)
        self.assertIn('href="../index.html"', document)
        for marker in ('id="maplibre-map"', 'id="map-viewport"', 'id="zoom-in"',
                       'id="dimension-toggle"', 'id="streets-toggle"',
                       'id="commune-select"', 'id="rank-badge"',
                       'type:"fill-extrusion"', 'function startWebGLMap',
                       'function connectStreets', 'function focusCommune',
                       'function supportsWebGL', 'const LOCAL_MAP_STYLE'):
            self.assertIn(marker, document)
        self.assertIn('../vendor/maplibre-gl.js', document)
        self.assertIn('../vendor/maplibre-gl.css', document)
        self.assertIn('https://tiles.openfreemap.org/styles/liberty', document)
        self.assertEqual(document.count('"type":"Feature","id":'), 15)
        self.assertEqual(document.count('class="map-label"'), 15)
        self.assertNotIn("DEMO · NO OFICIAL", document)
        for secret_marker in ("api_key", "access_token", "pk.ey"):
            self.assertNotIn(secret_marker, document.lower())
        self.assertNotIn("leaflet", document.lower())
        self.assertNotIn("mapbox", document.lower())

    def test_vista_demo_conserva_aviso_y_usa_la_misma_geometria_real(self):
        document = self._generate(ROOT / "build/demo/gold")
        self.assertEqual(document.count('class="commune"'), 15)
        self.assertIn("DEMO · NO OFICIAL", document)
        self.assertIn("Estas cifras son sintéticas", document)
        self.assertIn("evidencias", document)
        self.assertIn("oficial", document)
        self.assertIn("comunas", document)


if __name__ == "__main__":
    unittest.main()
