# 🧠 Cerebro Buenos Aires

Sistema de información urbana por comuna para la Ciudad Autónoma de Buenos Aires (CABA),
replicando tramo por tramo la arquitectura del ejemplo **Cerebro Lima**
(<https://cerebro-lima.vercel.app/>), como pide el taller de Gobernanza de Datos
(<https://gobernanzadatos.vercel.app/tallerdatos>).

> **Réplica, no copia.** Reconstruimos con nuestras manos un sistema que ya funciona,
> para entender por qué está hecho así. La ciudad elegida es **Buenos Aires** (Lima no vale,
> es el ejemplo).

## Pregunta que responde el sistema

> **¿Cómo cambia la disponibilidad de infraestructura y servicios urbanos entre las
> comunas de Buenos Aires?**

Indicadores por comuna:

- Estaciones de Ecobici por comuna
- Kilómetros de ciclovías por comuna
- Espacios verdes (cantidad y superficie) por comuna
- Hospitales / centros de salud por comuna

## Arquitectura (medallón: bronce → plata → oro)

```
        BUENOS AIRES DATA  ·  data.buenosaires.gob.ar
                       │
                       ▼
             ┌───────────────────┐
             │     CATÁLOGO      │  catalogo/catalogo.csv
             │ fuente, fecha,    │  (qué hay, qué sirve, por qué)
             │ licencia, URL     │
             └─────────┬─────────┘
                       ▼
                    INGESTA           scripts/ingest_*.py  (urllib | curl)
                       │
                       ▼
             ┌───────────────────┐
             │   BRONZE (raw)    │   lago/raw/<dominio>/<fecha>.{json,csv}
             │  tal cual salió   │   NO se modifica
             └─────────┬─────────┘
                       │  transformación / limpieza
                       ▼
             ┌───────────────────┐
             │  SILVER (limpio)  │   lago/silver/*.parquet (+ *.csv fallback)
             │  tipos, coords,   │   con columna de fuente y fecha
             │  normalización    │
             └─────────┬─────────┘
                       │  VERIFICACIÓN (si falla, NO se publica)
                       ▼
             ┌───────────────────┐
             │    GOLD (vistas)  │   lago/gold/*.parquet + indicadores por comuna
             └─────────┬─────────┘
                       │  DuckDB / SQLite
                       ▼
               DASHBOARD / VISTAS     app/  (HTML estático + Streamlit)
```

Equivalencia con Cerebro Lima: `lago/raw` = **bronce**, `lago/silver` = **plata**,
`lago/gold` + vistas = **oro** (medallion architecture de Databricks).

## Dos herramientas por tramo (requisito del taller)

| Tramo          | Herramienta A         | Herramienta B          | Elegida (ver bitácora) |
|----------------|-----------------------|------------------------|------------------------|
| Descubrimiento | Catálogo CSV a mano   | CKAN API (`/api/3/...`)| CKAN + catálogo propio |
| Ingesta        | `urllib` (Python std) | `curl`                 | Python (`urllib`)      |
| Transformación | Python stdlib `csv`   | Node.js                | Python stdlib          |
| (alt. docum.)  | Pandas                | Polars                 | Polars                 |
| Lago/formato   | CSV                   | Parquet                | Parquet                |
| Consulta       | SQLite                | DuckDB                 | DuckDB (SQLite corrido)|
| Lakehouse      | DuckLake              | Apache Iceberg         | DuckLake               |
| Validación     | Reglas propias (std)  | Pandera / GE           | Pandera                |
| Vistas         | HTML estático         | Streamlit              | Streamlit (HTML corrido)|

> La bitácora (`bitacora/exploracion.md`) justifica cada elección con tiempos,
> ventajas/desventajas y **fecha de prueba**.

## ⚠️ Nota de reproducibilidad (importante y honesta)

Este proyecto se construyó en un sandbox **sin acceso a internet** ni a PyPI.
Por eso:

- Los **scripts de ingesta real** (`scripts/ingest_*.py`) están completos y listos para
  correr **cuando tengas conexión** contra `data.buenosaires.gob.ar`.
- Para poder **correr el pipeline entero de punta a punta** aquí y ahora, se incluyen
  **datos semilla realistas** (`lago/raw/**`) que respetan la estructura real de los datasets
  de BA Data. Están marcados con `"_origen": "semilla_demo"` para que nadie los confunda
  con datos oficiales descargados.
- Todo lo que la bitácora marca como **«corrido»** se ejecutó con las herramientas
  disponibles en el sandbox (Python stdlib, Node.js, SQLite).

**Cero cifras sin fuente, sin vigencia o sin fecha de prueba.** Cuando corras la ingesta
real, los `raw/` se reemplazan por datos oficiales y los indicadores se recalculan solos.

## Cómo correr

### Requisitos

El **pipeline núcleo** (ingesta → silver → verify → gold → consulta SQLite →
dashboard HTML → lakehouse de bolsillo) corre **solo con la biblioteca estándar
de Python 3.9+**: no necesitas instalar nada.

Para habilitar las *herramientas B* documentadas (Parquet, Polars, DuckDB,
Pandera, Iceberg) y el dashboard interactivo de Streamlit:

```bash
python -m venv .venv
# Windows:        .venv\Scripts\activate
# Linux / macOS:  source .venv/bin/activate

pip install -r requirements.txt          # dependencias directas (versiones ==)
# o, para reproducir el entorno exacto probado:
pip install -r requirements.lock.txt
```

### Opción rápida: pipeline completo en un comando (recomendado)

```bash
python scripts/run_pipeline.py              # datos semilla (offline)
python scripts/run_pipeline.py --ingesta    # ingesta REAL desde BA Data (urllib)
python scripts/run_pipeline.py --curl       # ingesta REAL usando curl
```

`run_pipeline.py` es multiplataforma (Windows, Linux, macOS), usa el mismo
intérprete con el que lo invocás (respeta el `.venv`), corre los 7 tramos en
orden y **se detiene en el primer fallo**.

### Opción manual: tramo por tramo

```bash
# 0) (opcional) Ingesta REAL desde BA Data — requiere internet
python scripts/ingest_all.py            # baja a lago/raw/  (o usa --curl)

# Si NO hay internet, generá datos semilla:
python scripts/_gen_seed.py

# 1) Limpieza  bronze -> silver
python scripts/transform_silver.py

# 1-bis) Gobernanza: diccionario de datos (catalogo/diccionario_datos.{json,md})
python scripts/diccionario.py

# 2) Verificación (si falla, no publica)
python scripts/verify.py

# 2-bis) Gobernanza: perfilado / completitud por columna (lago/silver/_perfilado.json)
python scripts/profile_silver.py

# 3) Indicadores  silver -> gold
python scripts/build_gold.py

# 4) Consultas de ejemplo (SQLite corrido; DuckDB documentado)
python scripts/query_sqlite.py

# 5) Lakehouse demo: versionado + time travel
python scripts/lakehouse_timetravel.py

# 6) Dashboard estático (regenera app/index.html con fecha + cifras actuales)
python scripts/build_dashboard.py
#    luego abrí app/index.html en el navegador

# 6-bis) Dashboard Streamlit (requiere streamlit instalado)
streamlit run app/streamlit_app.py
```

> **Nota de portabilidad (Windows):** los scripts imprimen caracteres Unicode
> (`✓`, `✗`, `·`, `m²`). Para evitar `UnicodeEncodeError` en consolas cp1252,
> cada script importa `scripts/_utf8.py`, que reconfigura la salida a UTF-8 de
> forma automática. No necesitás `set PYTHONUTF8=1` ni el flag `-X utf8`.

## Estructura

```
cerebro-buenos-aires/
├── catalogo/           catalogo.csv  (inventario de fuentes)
│   ├── diccionario_datos.json  diccionario de datos (consumible por código)
│   └── diccionario_datos.md    diccionario de datos (legible)
├── scripts/            ingesta, transformación, verificación, gold, consultas, lakehouse
│   ├── run_pipeline.py orquestador multiplataforma (corre todo en orden)
│   ├── diccionario.py  gobernanza: genera el diccionario de datos
│   ├── profile_silver.py  gobernanza: perfilado/completitud por columna
│   └── _utf8.py        helper de portabilidad (salida UTF-8 en Windows)
├── lago/
│   ├── raw/            BRONZE (datos semilla / descargados)
│   ├── silver/         PLATA  (limpio, parquet/csv; + _perfilado.json)
│   └── gold/           ORO    (indicadores por comuna; _meta.json con linaje)
├── tests/              tests de reglas de validación
├── app/                dashboard (HTML estático + Streamlit)
├── bitacora/           exploracion.md  (justifica cada herramienta)
├── requirements.txt    dependencias directas (versiones fijadas)
├── requirements.lock.txt  entorno exacto (pip freeze)
└── README.md
```

## Fuentes públicas usadas (Buenos Aires y nacionales)

- **Buenos Aires Data** — portal oficial CKAN de datos abiertos de CABA:
  <https://data.buenosaires.gob.ar/>
- **API CKAN de BA Data** — <https://data.buenosaires.gob.ar/api/3/action/package_search>
- **Datos Argentina** (nacional) — <https://datos.gob.ar/>
- **INDEC** — <https://www.indec.gob.ar/> (contexto demográfico/socioeconómico)

Cada dataset concreto, con su URL y vigencia, está en `catalogo/catalogo.csv`.
