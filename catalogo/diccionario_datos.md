# Diccionario de datos — Cerebro Buenos Aires

Metadatos formales de cada dominio de la capa **SILVER**. Fuente única de verdad: `scripts/diccionario.py`. Los tipos coinciden con `transform_silver.py` y las reglas con `verify.py`. Esquema vigente contrastado con los CSV de SILVER y el lote oficial del **2026-10-28**. La procedencia se guarda en archivos `*.meta.json`, no en columnas adicionales. Hospitales usa claves estables derivadas de nombre y dirección; se rechazan los ID duplicados.

## poblacion

Población censal total 2022. Fuente: IDECBA sobre la base de INDEC.

- **Grano:** una fila por comuna
- **Clave primaria:** `comuna`

| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |
|---------|------|--------|-----|-------------|------------------|
| `comuna` | entero | comuna | no | Comuna CABA | 15 valores únicos 1..15 |
| `poblacion` | entero | habitantes | no | Población censal total | positiva; XLS reconcilia 3121707 |
| `anio` | entero | año | no | Año del censo | 2022 |

## ecobici

Estaciones de bicicletas públicas (Ecobici) de la Ciudad de Buenos Aires.

- **Grano:** una fila = una estación de Ecobici
- **Clave primaria:** `id`

| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |
|---------|------|--------|-----|-------------|------------------|
| `anclajes_totales` | entero | anclajes | no | Capacidad opcional; nula cuando la fuente no la informa. No se usa en las tasas de estaciones. | nulo o entero positivo |
| `id` | entero | - | no | Identificador oficial de la estación; comuna asignada con capa oficial trazable. | no nulo y único |
| `nombre` | texto | - | no | Nombre informado por la fuente oficial; Title Case en demo. | texto; sin validación de no vacío en verify.py |
| `comuna` | entero | comuna | no | Comuna de CABA derivada por punto-en-polígono a partir de lat/lon. | entero en 1..15 |
| `lat` | decimal | grados | no | Latitud (WGS84). | entre -34.71 y -34.52 (bounding box CABA) |
| `lon` | decimal | grados | no | Longitud (WGS84). | entre -58.54 y -58.33 (bounding box CABA) |

## ciclovias

Red de ciclovías de la Ciudad de Buenos Aires (geometrías de línea).

- **Grano:** una fila = un tramo de ciclovía
- **Clave primaria:** `id`

| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |
|---------|------|--------|-----|-------------|------------------|
| `id` | entero | - | no | Identificador único del tramo. | no nulo y único |
| `nombre` | texto | - | no | Nombre o calle del tramo de ciclovía. | normalizado; sin validación de no vacío en verify.py |
| `comuna` | entero | comuna | no | Comuna de CABA del tramo. | entero en 1..15 |
| `long_metros` | decimal | metros | no | Longitud del tramo en metros. | > 0 |
| `tipo` | texto | - | no | Tipo de infraestructura ciclista. | libre |

## espacios_verdes

Espacios verdes públicos (plazas, parques) de la Ciudad de Buenos Aires.

- **Grano:** una fila = un espacio verde
- **Clave primaria:** `id`

| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |
|---------|------|--------|-----|-------------|------------------|
| `id` | entero | - | no | Identificador único del espacio verde. | no nulo y único |
| `nombre` | texto | - | no | Nombre del espacio verde. | normalizado; sin validación de no vacío en verify.py |
| `comuna` | entero | comuna | no | Comuna de CABA del espacio verde. | entero en 1..15 |
| `area_m2` | decimal | m² | no | Área geométrica calculada en EPSG:9498, con geometría validada; no equivale a cobertura vegetal. | > 0 |
| `clasificacion` | texto | - | no | Clasificación del espacio (plaza, parque, etc.). | libre |
| `lat` | decimal | grados | no | Latitud (WGS84). | entre -34.71 y -34.52 (bounding box CABA) |
| `lon` | decimal | grados | no | Longitud (WGS84). | entre -58.54 y -58.33 (bounding box CABA) |

## hospitales

Hospitales de la Ciudad de Buenos Aires; no incluye un dominio independiente de CeSAC.

- **Grano:** una fila = un establecimiento de salud
- **Clave primaria:** `id`

| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |
|---------|------|--------|-----|-------------|------------------|
| `id` | entero | - | no | Clave estable derivada de nombre completo y dirección; se rechazan duplicados. | no nulo y único |
| `nombre` | texto | - | no | Nombre del hospital. | no vacío |
| `tipo` | texto | - | no | Tipo de establecimiento informado por la fuente (gna). | libre |
| `comuna` | entero | comuna | no | Comuna de CABA del establecimiento. | entero en 1..15 |
| `direccion` | texto | - | no | Dirección postal del establecimiento. | libre |
| `lat` | decimal | grados | no | Latitud (WGS84). | entre -34.71 y -34.52 (bounding box CABA) |
| `lon` | decimal | grados | no | Longitud (WGS84). | entre -58.54 y -58.33 (bounding box CABA) |
