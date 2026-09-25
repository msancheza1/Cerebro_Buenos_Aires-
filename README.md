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

```bash
cd cerebro-buenos-aires

# 0) (opcional) Ingesta REAL desde BA Data — requiere internet
python scripts/ingest_all.py            # baja a lago/raw/  (o usa --curl)

# Si NO hay internet, el repo ya trae datos semilla en lago/raw/

# 1) Limpieza  bronze -> silver
python scripts/transform_silver.py

# 2) Verificación (si falla, no publica)
python scripts/verify.py

# 3) Indicadores  silver -> gold
python scripts/build_gold.py

# 4) Consultas de ejemplo (SQLite corrido; DuckDB documentado)
python scripts/query_sqlite.py

# 5) Lakehouse demo: versionado + time travel
python scripts/lakehouse_timetravel.py

# 6) Dashboard estático (abrir en navegador)
open app/index.html          # o servir la carpeta app/

# 6-bis) Dashboard Streamlit (requiere streamlit instalado)
streamlit run app/streamlit_app.py
```

## Estructura

```
cerebro-buenos-aires/
├── catalogo/           catalogo.csv  (inventario de fuentes)
├── scripts/            ingesta, transformación, verificación, gold, consultas, lakehouse
├── lago/
│   ├── raw/            BRONZE (datos semilla / descargados)
│   ├── silver/         PLATA  (limpio, parquet/csv)
│   └── gold/           ORO    (indicadores por comuna)
├── tests/              tests de reglas de validación
├── app/                dashboard (HTML estático + Streamlit)
├── bitacora/           exploracion.md  (justifica cada herramienta)
└── README.md
```

## Fuentes públicas usadas (Buenos Aires y nacionales)

- **Buenos Aires Data** — portal oficial CKAN de datos abiertos de CABA:
  <https://data.buenosaires.gob.ar/>
- **API CKAN de BA Data** — <https://data.buenosaires.gob.ar/api/3/action/package_search>
- **Datos Argentina** (nacional) — <https://datos.gob.ar/>
- **INDEC** — <https://www.indec.gob.ar/> (contexto demográfico/socioeconómico)

Cada dataset concreto, con su URL y vigencia, está en `catalogo/catalogo.csv`.
