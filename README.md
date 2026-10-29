# 🧠 Cerebro Buenos Aires

Sistema didáctico de información urbana por comuna para CABA, reconstruido a partir del
modelo de [Cerebro Lima](https://cerebro-lima.vercel.app/) para el
[taller de Gobernanza de Datos](https://gobernanzadatos.vercel.app/tallerdatos).

## Estado de los datos

> La entrega incluye un lote oficial verificado del 28 de octubre de 2026 en
> `evidencias/oficial/`. El modo demo genera observaciones sintéticas y las identifica
> como **DEMO · NO OFICIAL**. El modo oficial exige descargar y validar un lote completo.

La pregunta del MVP es: **¿cómo se distribuyen Ecobici, ciclovías, espacios verdes y
hospitales entre las 15 comunas de Buenos Aires?**

## Garantías del pipeline

- **Demo y oficial están aislados:** demo usa `demo/raw` y `build/demo`; oficial usa `lago/`.
- **Ingesta cerrada:** si una fuente falla o cambia de esquema, no se promueve un lote parcial.
- **Trazabilidad obligatoria:** cada BRONZE requiere sidecar, `run_id` y SHA-256 válido.
- **SILVER por lote:** todas las tablas se construyen en staging y se reemplazan juntas.
- **Calidad atómica:** los cinco dominios deben pasar, compartir procedencia y `run_id`.
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

Requiere Python 3.10+. Para la población XLS y los adaptadores geográficos oficiales:

```bash
python -m pip install xlrd==2.0.2 shapely==2.1.2 pyproj==3.7.2
```

Parquet y las herramientas alternativas tienen dependencias adicionales en `requirements.txt`.

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

Requiere internet. Descarga cinco dominios usados por GOLD y la capa auxiliar de comunas
en el mismo lote. Los CSV, GeoJSON y XLS deben cumplir los contratos de
`scripts/fuentes.py`; si una URL o columna cambió, la ejecución
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

| Tramo | Comparación | Implementación principal |
|---|---|---|
| Catálogo | CSV curado vs API CKAN | CSV + script CKAN opcional |
| Ingesta | `urllib` vs `curl` | ambas |
| Transformación | adaptadores propios vs Polars | stdlib para demo; Shapely/pyproj para oficial |
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
app/official/index.html vista oficial generada y versionada tras ingesta válida
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


## Entrega oficial: población e indicadores por habitante

Lote `20261028T145728Z`, ejecutado el 28 de octubre de 2026 (Colombia).
Completó descarga → Silver → verificación → Gold → consultas → dashboard de totales.
Resultados: **406/407 estaciones**, **2.764 tramos**, **2.176 polígonos verdes públicos**,
**36 hospitales** y **15 comunas**. F10 utiliza población censal total de **2022**:
**3.121.707 habitantes**, fuente IDECBA (GCBA) sobre la base de INDEC.

- [Tabla final de indicadores](evidencias/oficial/gold/indicadores_por_comuna.csv).
- [Resumen y comprobación de 75 tasas](evidencias/oficial/resumen.json).
- [Reporte de calidad](evidencias/oficial/silver/_verificacion.json).
- [Originales y sidecars con URL, fecha y SHA-256](evidencias/oficial/raw/).
- [Diccionario](catalogo/diccionario_datos.md) y [bitácora real](bitacora/2026-10-28-ejecucion-oficial.md).

El XLS original F10 también se conserva en `evidencias/f10/` para su validación aislada.
Se extrae exclusivamente la hoja `2022`, columna `Total`, con 15 comunas únicas,
población entera positiva y reconciliación del total. La licencia F10 figura como
**No verificada**. No se asume que sea CC-BY.

### Reproducir y verificar

Desde la raíz, después de instalar las tres dependencias principales:

```bash
python tests/test_poblacion.py
python tests/test_infraestructura.py
python tests/test_orquestador.py
python tests/test_verificacion.py
python scripts/run_pipeline.py --ingesta
python scripts/evidencia_oficial.py
```

Las pruebas suman 21 casos, con subcasos para entradas inválidas. La demo se ejecuta
con `python scripts/run_pipeline.py --demo` y usa carpetas separadas.
Para descargar y exportar únicamente F10, sin sustituir Silver ni publicar Gold:

```bash
python scripts/ingest_all.py poblacion
python scripts/exportar_f10.py
```

Para volver a comprobar las evidencias guardadas sin acceso a internet, configurar
`CEREBRO_SILVER_DIR` con la ruta absoluta de `evidencias/oficial/silver` y
`CEREBRO_GOLD_DIR` con una carpeta nueva de salida; ejecutar `scripts/verify.py` y
`scripts/build_gold.py`. Conservar las rutas relativas y los bytes de los originales.

### Contrato para visualización

Silver `poblacion.csv`: `comuna,poblacion,anio`. Gold conserva los totales y añade
`poblacion`, `anio_poblacion` y estas columnas:

| Columna | Cálculo | Unidad |
|---|---|---|
| estaciones_ecobici_por_10000_hab | estaciones_ecobici / poblacion × 10.000 | estaciones / 10.000 hab |
| km_ciclovias_por_10000_hab | km_ciclovias / poblacion × 10.000 | km / 10.000 hab |
| espacios_verdes_por_10000_hab | espacios_verdes / poblacion × 10.000 | espacios / 10.000 hab |
| m2_verdes_por_hab | m2_espacios_verdes / poblacion | m² / hab |
| hospitales_por_10000_hab | hospitales / poblacion × 10.000 | hospitales / 10.000 hab |

Las tasas se redondean al final a seis decimales, sin redondear las sumas intermedias.
Población ausente o inválida bloquea Gold; nunca se convierte en cero. Los ceros de
infraestructura se conservan dentro de un lote válido. Para tasas de toda la ciudad,
sumar numeradores y dividir por la población total; nunca sumar tasas comunales.
`_meta.json` registra `indicadores_normalizados`, fórmulas, unidades y `fuentes.poblacion`.
`indicadores` conserva únicamente totales por compatibilidad con el dashboard actual.

### Decisiones de calidad y pendientes

- Ecobici usa intersección única con polígonos oficiales. La estación **541 AEROPARQUE**
  no intersecta la capa descargada y se mantiene en cuarentena: 1/407 (0,246 %).
  No se le asigna arbitrariamente una comuna. Anclajes ausentes quedan nulos.
- Hospitales declara **EPSG:9498** en su GeoJSON y se transforma a WGS84; se usa una
  clave estable derivada de nombre y dirección con control de duplicados.
- Los espacios verdes declaran CRS84. Se reparan **25 geometrías** mediante `make_valid`
  y se calcula superficie en EPSG:9498. El área mide polígonos públicos, no cobertura vegetal.
- Ciclovías conserva `longitud_m` y la comuna declarados por tramo, sin dividir fronteras.
- Se comprobaron automáticamente 75 tasas; el resumen incluye las comunas 1, 8 y 15.
  La revisión humana, con responsable identificado, sigue pendiente.
- Persona 2 debe implementar el selector de totales/tasas, unidades, año 2022 y
  comprobación visual. El dashboard generado actualmente muestra totales.
- Persona 3 debe revisar las 11 licencias con evidencia y consolidar la bitácora.
  También faltan comparaciones entre herramientas del taller. Esta entrega no acredita
  que esas tareas estén terminadas ni confirma un despliegue público.
