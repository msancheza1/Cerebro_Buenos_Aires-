#!/usr/bin/env bash
# Pipeline seguro de Cerebro Buenos Aires.
#   bash scripts/run_pipeline.sh --demo      # datos generados, aislados de lago/
#   bash scripts/run_pipeline.sh --ingesta   # fuentes oficiales; aborta ante cualquier fallo
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
MODE="${1:---demo}"

case "$MODE" in
  --demo)
    export CEREBRO_MODE=demo
    export CEREBRO_RAW_DIR="$PWD/demo/raw"
    export CEREBRO_SILVER_DIR="$PWD/build/demo/silver"
    export CEREBRO_GOLD_DIR="$PWD/build/demo/gold"
    export CEREBRO_APP_DIR="$PWD/app/demo"
    echo "MODO DEMO · cifras generadas, NO oficiales"
    "$PY" scripts/_gen_seed.py
    ;;
  --ingesta)
    export CEREBRO_MODE=official
    export CEREBRO_RAW_DIR="$PWD/lago/raw"
    export CEREBRO_SILVER_DIR="$PWD/lago/silver"
    export CEREBRO_GOLD_DIR="$PWD/lago/gold"
    export CEREBRO_APP_DIR="$PWD/app/official"
    echo "MODO OFICIAL · el lote completo debe descargarse y validar"
    "$PY" scripts/ingest_all.py
    ;;
  *)
    echo "Uso: bash scripts/run_pipeline.sh [--demo|--ingesta]" >&2
    exit 2
    ;;
esac

echo "[1/6] Limpieza BRONZE -> SILVER"
"$PY" scripts/transform_silver.py

echo "[2/6] Verificación atómica"
"$PY" scripts/verify.py

echo "[3/6] Validaciones existentes"
"$PY" tests/test_verificacion.py

echo "[4/6] Publicación SILVER -> GOLD"
"$PY" scripts/build_gold.py

echo "[5/6] Consultas SQLite"
"$PY" scripts/query_sqlite.py

echo "[6/6] Dashboard"
"$PY" scripts/build_dashboard.py

echo "OK · $CEREBRO_APP_DIR/index.html · modo=$CEREBRO_MODE"
