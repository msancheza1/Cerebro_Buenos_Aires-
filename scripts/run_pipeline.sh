#!/usr/bin/env bash
# Orquesta el pipeline completo de Cerebro Buenos Aires.
# Uso:
#   bash scripts/run_pipeline.sh            # usa datos semilla (offline)
#   bash scripts/run_pipeline.sh --ingesta  # intenta ingesta real (necesita internet)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python

echo "════════════════════════════════════════════════"
echo " CEREBRO BUENOS AIRES · pipeline"
echo "════════════════════════════════════════════════"

if [[ "${1:-}" == "--ingesta" ]]; then
  echo "[0/6] Ingesta REAL desde BA Data..."
  $PY scripts/ingest_all.py || echo "  (ingesta falló; sigo con lo que haya en lago/raw/)"
else
  echo "[0/6] Datos semilla (offline)..."
  $PY scripts/_gen_seed.py
fi

echo "[1/6] Limpieza  bronze -> silver..."
$PY scripts/transform_silver.py

echo "[2/6] Verificación (si falla, no se publica)..."
$PY scripts/verify.py

echo "[3/6] Tests de verificación..."
$PY tests/test_verificacion.py

echo "[4/6] Indicadores  silver -> gold..."
$PY scripts/build_gold.py

echo "[5/6] Consultas de ejemplo (SQLite)..."
$PY scripts/query_sqlite.py

echo "[6/6] Dashboard estático..."
$PY scripts/build_dashboard.py

echo "════════════════════════════════════════════════"
echo " OK. Abrí app/index.html en el navegador."
echo "════════════════════════════════════════════════"
