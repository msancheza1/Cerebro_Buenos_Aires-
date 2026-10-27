# 🧠 Cerebro Buenos Aires

Sistema didáctico de información urbana por comuna para CABA, reconstruido a partir del
modelo de [Cerebro Lima](https://cerebro-lima.vercel.app/) para el
[taller de Gobernanza de Datos](https://gobernanzadatos.vercel.app/tallerdatos).

## Estado de los datos

> **El repositorio no versiona cifras oficiales.** El modo demo genera observaciones
> sintéticas para probar el pipeline y el dashboard las marca como **DEMO · NO OFICIAL**.
> El modo oficial sólo publica si descarga y valida un lote completo de BA Data.

La pregunta del MVP es: **¿cómo se distribuyen Ecobici, ciclovías, espacios verdes y
hospitales entre las 15 comunas de Buenos Aires?**

## Garantías del pipeline

- **Demo y oficial están aislados:** demo usa `demo/raw` y `build/demo`; oficial usa `lago/`.
- **Ingesta cerrada:** si una fuente falla o cambia de esquema, no se promueve un lote parcial.
- **Trazabilidad obligatoria:** cada BRONZE requiere sidecar, `run_id` y SHA-256 válido.
- **SILVER por lote:** todas las tablas se construyen en staging y se reemplazan juntas.
- **Calidad atómica:** los cuatro dominios deben pasar, compartir procedencia y `run_id`.
- **GOLD protegido:** comprueba que SILVER no cambió después de la verificación.
- **Procedencia explícita:** calidad técnica y oficialidad son estados separados.

```text
Fuentes BA Data
      ↓
Catálogo + contratos mínimos
      ↓
Ingesta a staging ── fallo → no promueve
      ↓
BRONZE + sidecar + SHA-256
      ↓
SILVER + métricas de rechazo
      ↓
Verificación atómica ── fallo → no publica
      ↓
GOLD (CSV + SQLite) → dashboard HTML / Streamlit
```

## Ejecutar

Requiere Python 3.10+; el camino principal usa sólo la biblioteca estándar.

### Demo reproducible y segura

```bash
bash scripts/run_pipeline.sh --demo
```

Genera datos sintéticos fuera del lago oficial, limpia, verifica, publica GOLD, ejecuta
consultas y actualiza `app/demo/index.html`. También se acepta `bash scripts/run_pipeline.sh`,
que equivale a `--demo` por compatibilidad.

### Ingesta oficial

```bash
bash scripts/run_pipeline.sh --ingesta
```

Requiere internet. Descarga los cuatro dominios usados por GOLD. Cada CSV debe cumplir el
contrato configurado en `scripts/fuentes.py`; si una URL o columna cambió, la ejecución
termina antes de SILVER/GOLD. **No existe fallback automático a datos antiguos o demo.**

### Etapas individuales

Las rutas pueden configurarse con `CEREBRO_RAW_DIR`, `CEREBRO_SILVER_DIR`,
`CEREBRO_GOLD_DIR`, `CEREBRO_APP_DIR` y `CEREBRO_MODE`.

```bash
python3 scripts/transform_silver.py
python3 scripts/verify.py
python3 scripts/build_gold.py
python3 scripts/query_sqlite.py
python3 scripts/build_dashboard.py
python3 tests/test_verificacion.py
```

Si `pyarrow` está instalado, SILVER produce además Parquet; sin él conserva el CSV
verificable. Las variantes exploratorias están en `transform_silver_polars.py`,
`verify_pandera.py`, `query_duckdb.py`, `lakehouse_ducklake.py`,
`lakehouse_iceberg.py` y `app/streamlit_app.py`.

## Dos herramientas por tramo

| Tramo | Comparación | Implementación ejecutable sin dependencias |
|---|---|---|
| Catálogo | CSV curado vs API CKAN | CSV + script CKAN opcional |
| Ingesta | `urllib` vs `curl` | ambas |
| Transformación | stdlib vs Polars | stdlib |
| Formato | CSV vs Parquet | CSV; Parquet con `pyarrow` |
| Verificación | reglas propias vs Pandera/GE | reglas propias |
| Consulta | SQLite vs DuckDB | SQLite |
| Lakehouse | DuckLake vs Iceberg | demo conceptual separada |
| Vistas | HTML estático vs Streamlit | HTML estático |

La evidencia y las decisiones están en `bitacora/exploracion.md`.

## Estructura

```text
catalogo/              inventario de fuentes y vigencia
scripts/               ingesta, transformación, calidad, GOLD y vistas
lago/raw/              BRONZE oficial local (ignorado por git)
lago/silver/           tablas limpias oficiales locales (ignorado por git)
lago/gold/             publicación oficial local (ignorada por git)
demo/raw/              semilla generada (ignorada por git)
build/demo/            SILVER/GOLD demo (ignorado por git)
app/index.html          selector entre publicaciones
app/demo/index.html     vista demo generada y revisable
app/official/index.html vista oficial local (sólo tras ingesta válida)
app/streamlit_app.py    vista interactiva opcional
tests/                  validaciones existentes
bitacora/               exploración y justificación
```

## Fuentes de referencia

- [Buenos Aires Data](https://data.buenosaires.gob.ar/)
- [API CKAN de BA Data](https://data.buenosaires.gob.ar/api/3/action/package_search)
- [Datos Argentina](https://datos.gob.ar/)
- [INDEC](https://www.indec.gob.ar/)

Las URLs descargables y sus contratos mínimos están centralizados en
`scripts/fuentes.py`; el inventario curado está en `catalogo/catalogo.csv`.
