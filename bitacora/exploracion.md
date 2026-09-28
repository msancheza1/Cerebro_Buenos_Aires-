# Bitácora de exploración — Cerebro Buenos Aires

**Ciudad elegida:** Buenos Aires (CABA). *Lima no vale: es el ejemplo.*
**Equipo:** 3–4 personas (ver reparto al final).
**Fecha de las pruebas:** 2026-09-25 (salvo indicación distinta por experimento).
**Regla del taller:** en cada tramo se prueban **≥ 2 herramientas sobre los mismos datos**
antes de elegir una; y **cero cifras sin fuente, sin vigencia o sin fecha de prueba**.

---

## Nota de entorno (condiciona qué se pudo correr)

Este trabajo se desarrolló en un entorno **sin acceso a internet ni a PyPI**. Consecuencias
declaradas con honestidad (el propio taller pide distinguir lo «corrido» de lo que no):

- La **ingesta real** contra `data.buenosaires.gob.ar` **no se pudo ejecutar aquí**; los
  scripts (`scripts/ingest_all.py`, `scripts/catalogo_ckan.py`) quedan listos y **fallan de
  forma controlada** sin conexión (verificado: `403` del proxy).
- Para poder correr el pipeline completo, se usaron **datos semilla** (marcados
  `_origen: semilla_demo`) que implementan el **contrato demo del proyecto**; no se
  afirma que reproduzcan el esquema actual de BA Data sin una descarga verificable.
- Herramientas no instalables offline (pandas, polars, duckdb, pyarrow, streamlit, pandera)
  se dejan como **variante B documentada y ejecutable con internet**; la **variante A**
  de cada tramo usa lo disponible (Python stdlib, SQLite, Node.js) y **sí se corrió**.

Esto no debilita la comparación de herramientas: el criterio de elección se argumenta igual,
y donde no se pudo medir tiempo real se dice explícitamente.

---

## Hallazgo temprano del rastreo (Tramo Fuentes)

Durante el rastreo inicial encontramos que Buenos Aires dispone de APIs públicas para varios
servicios urbanos (Ecobici, colectivos, tránsito, catastro, geocodificación). Sin embargo, el
portal BA Data informa que **algunos recursos API y GTFS están temporalmente suspendidos**
mientras se revisan (aparece, por ejemplo, en la API de Catastro). **Decisión:** no depender
de APIs en vivo para el MVP y **priorizar descargables** (CSV/JSON/GeoJSON). Queda registrado
en `catalogo/catalogo.csv` (fila id=11).

---

## Experimento 00 — Catálogo: CSV a mano vs API CKAN

| | Herramienta A | Herramienta B |
|---|---|---|
| Qué | Catálogo escrito a mano (`catalogo.csv`) | Descubrimiento vía API CKAN (`package_search`) |
| Corrido | Sí | No (requiere internet); script listo y degrada bien |
| Ventaja | Control total, incluye juicio (motivo, seleccionado) | Automatizable, se actualiza solo, trae formatos reales |
| Desventaja | Manual, envejece | Depende de que la API esté arriba (¡ver hallazgo!) |

**Decisión:** **CKAN para descubrir** + **catálogo propio para decidir**. La API lista qué
hay; la curaduría humana (columnas `seleccionado`/`motivo`) decide qué sirve. BA Data corre
sobre CKAN, así que el descubrimiento programático es barato.

---

## Experimento 01 — Ingesta: urllib (stdlib) vs curl

| | Herramienta A: urllib | Herramienta B: curl |
|---|---|---|
| Corrido offline | Falla controlada (403 proxy) | Falla controlada |
| Ventaja | Integra descarga + metadatos + sha256 + reintentos en un solo proceso Python | Muy simple, rapidísimo para un GET suelto |
| Desventaja | Requiere código | Incómodo para transformar/registrar metadatos después |

**Decisión:** **Python (`urllib`)**. La descarga no vive sola: tiene que escribir el sidecar
`*.meta.json` (fuente, url, licencia, fecha de ingesta, sha256) para que **cada cifra sea
rastreable** hasta su origen. `curl` queda como opción con `--curl` para pruebas rápidas.
*(No pudimos medir tiempos reales de red por falta de internet; la comparación es de diseño.)*

---

## Experimento 02 — Transformación / limpieza: Python stdlib vs Polars (y Pandas)

| | Herramienta A: stdlib `csv` | Herramienta B: Polars | Alternativa: Pandas |
|---|---|---|---|
| Corrido aquí | **Sí** (289/300 filas ecobici) | No (sin instalar) | No |
| Ventaja | Cero dependencias, corre en cualquier lado | Vectorizado, lazy, Parquet nativo, muy rápido | Ecosistema enorme, familiar |
| Desventaja | Más verboso, sin Parquet nativo | Dependencia extra | Más lento/memoria que Polars en volúmenes grandes |

**Mismos datos, mismo resultado esperado:** ambas rutas descartan las filas semilla con
comuna vacía o coordenada `(0,0)` y normalizan nombres. Corrido con stdlib:
`ecobici 289 filas (11 descartadas)`.

**Decisión:** para **este MVP**, **Python stdlib** (elegido porque corre sin instalar nada y el
volumen es chico). Para producción/volumen recomendamos **Polars** (ver `transform_silver_polars.py`):
gana a Pandas en velocidad/memoria y escribe Parquet nativo.

---

## Experimento 03 — Formato del lago: CSV vs Parquet

| | CSV | Parquet |
|---|---|---|
| Corrido | Sí (silver en CSV) | Solo si hay `pyarrow` (no en este entorno) |
| Ventaja | Universal, legible a ojo | Columnar, comprimido, tipos, mucho más rápido de consultar |
| Desventaja | Pesado, sin tipos, lento | Necesita librería para leer/escribir |

**Decisión:** **Parquet** para SILVER (el taller lo pide). `transform_silver.py` lo escribe
**automáticamente cuando `pyarrow` está disponible**; si no, cae a CSV para no romper el
pipeline. **Honestidad:** no falsificamos un Parquet «a mano» que no pudiéramos verificar;
con `pyarrow` instalado, el mismo script produce `lago/silver/*.parquet` (snappy).

---

## Experimento 04 — Verificación: reglas propias vs Pandera vs Great Expectations

| | A: reglas stdlib | B: Pandera | (C): Great Expectations |
|---|---|---|---|
| Corrido | **Sí** (4/4 dominios OK; 6/6 tests) | No (sin instalar) | No |
| Ventaja | Transparente, cero deps, fácil de testear | Esquema como código, liviano, integrable | Data docs, checkpoints, muy completo |
| Desventaja | Hay que escribir cada regla | Dependencia extra | Pesado de configurar para un MVP |

**Reglas aplicadas:** `id` no nulo/único, `comuna ∈ [1,15]`, coordenadas dentro del *bounding
box* de CABA (lat ∈ [-34.71, -34.52], lon ∈ [-58.54, -58.33]), positividad de anclajes/metros/área,
nombre no vacío. **«Si falla, no se publica»**: `build_gold.py` solo publica dominios con
`publicable: true` en `lago/silver/_verificacion.json`.

**Prueba de que atrapa lo malo:** `tests/test_verificacion.py` inyecta comuna=99, id duplicado,
coord (0,0), anclajes=0 y nombre vacío → **6/6 detectados**.

**Decisión:** reglas propias para el entregable (corren sin nada); **Pandera** como herramienta
recomendada al escalar (mejor que GE para 4 datasets: GE es *overkill*).

---

## Experimento 05 — Consulta: SQLite vs DuckDB

| | A: SQLite (stdlib) | B: DuckDB |
|---|---|---|
| Corrido | **Sí** (todas las queries) | No (sin instalar); script listo |
| Ventaja | Viene con Python, transaccional | Analítico, lee Parquet/CSV directo, ventana/CTE veloces |
| Desventaja | No columnar, menos óptimo para analítica | Dependencia extra |

**Salida demo ejecutada (no estadística oficial):** Comuna 1 lidera en la semilla generada — 47 estaciones Ecobici, 35 espacios verdes,
7 hospitales (índice de infraestructura = 89), seguida por comunas 14, 13, 2 y 4.

**Decisión:** **DuckDB** es la elección conceptual (replica «carpeta de Parquet con DuckDB
encima» del ejemplo Lima); **SQLite** es el plan B sin dependencias que **corrió** aquí.
Ambos ejecutan las **mismas** consultas (ver `query_sqlite.py` y `query_duckdb.py`).

---

## Experimento 06 — Lakehouse: DuckLake vs Apache Iceberg (time travel)

| | A: DuckLake | B: Apache Iceberg | Demo corrida: SQLite |
|---|---|---|---|
| Corrido | No (needs ext) | No (needs pyiceberg) | **Sí** |
| Idea | Catálogo en SQL + datos Parquet | Formato de tabla abierto estándar de la industria | Snapshots + consulta por versión |
| Ventaja | Cabe en un portátil, simple | Interoperable con todos los motores grandes | Cero deps, muestra el concepto |
| Desventaja | Más nuevo | Setup más ceremonioso | No es un lakehouse «de verdad» |

**Demo corrida (`lakehouse_timetravel.py`):** v1 = 100 estaciones → v2 = 105 → *time travel*
a v1 confirma 100, y el `diff` muestra 5 estaciones nuevas (#106–#110).

**Decisión:** **DuckLake** para este taller (lakehouse de bolsillo, sin servicios, alineado con
el ejemplo Lima y con la tendencia 2025–2026). **Iceberg** queda documentado como el estándar
de interoperabilidad al que apuntan los grandes. Scripts A y B listos para correr con deps.

---

## Experimento 07 — Vistas: HTML estático vs Streamlit

| | A: HTML estático | B: Streamlit |
|---|---|---|
| Corrido | **Sí** (`app/demo/index.html`, 26 KB) | No (sin instalar); app lista |
| Ventaja | Cero infra, se publica en cualquier hosting, abre offline | Interactivo (selectores, filtros), rápido de prototipar |
| Desventaja | No interactivo | Necesita servidor Python corriendo |

**Decisión:** **HTML estático** para el entregable publicable (sin tarjeta de crédito, sin
servidor), con el bloque obligatorio **Fuente · Última construcción · Estado ✓ verificado**.
**Streamlit** (`app/streamlit_app.py`) es la vista interactiva para explorar localmente.

---

## Trazabilidad de cifras (regla «cero cifras sin fuente/vigencia/fecha»)

- Cada descarga oficial en `lago/raw/**` y cada semilla en `demo/raw/**` tiene un
  `*.meta.json` con **fuente de referencia, URL, licencia, fecha de ingesta, run_id y sha256**.
- SILVER hereda la procedencia, el hash BRONZE y métricas de descarte en sus sidecars.
- GOLD separa **calidad** (`verified`) de **procedencia** (`demo` u `official`); el dashboard
  nunca presenta una semilla técnicamente válida como estadística oficial.
- El modo demo y el oficial usan directorios distintos. La ingesta oficial no reutiliza ni
  mezcla fuentes anteriores si falla un recurso.

---

## Reparto del equipo (sugerido)

- **Persona 1 — Fuentes + catálogo:** rastreo, `catalogo.csv`, licencias, vigencia, CKAN.
- **Persona 2 — Ingeniería de datos:** ingesta, bronze, limpieza a silver, Parquet, consultas.
- **Persona 3 — Calidad + aplicación:** verificación, gold, dashboard, lakehouse/time travel.
- **Todos:** esta bitácora de decisiones.

---

## Estado final de lo corrido

| Tramo | Herramienta corrida | Resultado |
|---|---|---|
| Ingesta (semilla) | stdlib | 5 dominios aislados en `demo/raw/` |
| Limpieza | stdlib | ecobici 289 (11 descartadas), ciclovías 120, verdes 250, hospitales 35 |
| Verificación | reglas propias | 4/4 publicables · tests 6/6 |
| Gold | SQLite | 5 indicadores × 15 comunas |
| Consulta | SQLite | En la semilla demo, Comuna 1 lidera (índice 89) |
| Lakehouse | SQLite | time travel v1=100 → v2=105 |
| Vistas | HTML | `app/demo/index.html` generado |

*Pendiente de correr con internet:* ingesta real (BA Data), y variantes B (CKAN, Polars,
Pandera, DuckDB, DuckLake, Iceberg, Streamlit) — todas con script listo.



---

## Revisión de seguridad de publicación — 2026-09-25

Una segunda revisión detectó que el primer MVP podía continuar después de una ingesta
fallida, reutilizar salidas antiguas y etiquetar un GOLD parcial como «verificado». Se
corrigieron esas debilidades:

1. demo y oficial quedaron en rutas separadas;
2. la ingesta usa staging y cancela el lote completo ante cualquier fallo;
3. BRONZE exige sidecar y SHA-256 coincidente;
4. SILVER y GOLD se reemplazan como conjuntos completos;
5. `verify.py` retorna error y detiene el pipeline si falla un dominio, hay mezcla de
   procedencias, cambia un hash o la tasa de descarte supera 10 %;
6. GOLD vuelve a comprobar los hashes verificados;
7. el dashboard separa demo (`app/demo`) de oficial (`app/official`), distingue calidad
   técnica de oficialidad y grafica los cinco indicadores.

**Decisión revisada:** «si falla, no se publica» se interpreta de manera **atómica por
corrida**, no como publicación parcial por dominio.