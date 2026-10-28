"""Comprueba que una descarga fallida no alcanza transformación/publicación."""
import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_pipeline


class SeguridadOrquestador(unittest.TestCase):
    def test_ingesta_fallida_detiene_todos_los_pasos(self):
        for flag in ("--ingesta", "--curl"):
            with self.subTest(flag=flag), patch.object(sys, "argv", ["pipeline", flag]), \
                    patch.dict(os.environ), patch.object(run_pipeline.subprocess, "run",
                    return_value=SimpleNamespace(returncode=1)) as run, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(run_pipeline.main(), 1)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(os.environ["CEREBRO_MODE"], "official")

    def test_demo_aisla_todas_las_salidas(self):
        with patch.object(sys, "argv", ["pipeline", "--demo"]), patch.dict(os.environ), \
                patch.object(run_pipeline.subprocess, "run",
                return_value=SimpleNamespace(returncode=0)), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_pipeline.main(), 0)
            self.assertEqual(os.environ["CEREBRO_MODE"], "demo")
            for variable, relative in {
                "RAW": "demo/raw", "SILVER": "build/demo/silver",
                "GOLD": "build/demo/gold", "APP": "app/demo",
            }.items():
                self.assertEqual(Path(os.environ[f"CEREBRO_{variable}_DIR"]),
                                 run_pipeline.ROOT / relative)


if __name__ == "__main__":
    unittest.main()
