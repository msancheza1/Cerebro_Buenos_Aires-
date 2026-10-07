# Diccionario de datos — Cerebro Buenos Aires

Metadatos formales de cada dominio de la capa **SILVER**. Fuente única de verdad: `scripts/diccionario.py`. Los tipos coinciden con `transform_silver.py` y las reglas con `verify.py`. Esquema vigente contrastado con los CSV de SILVER y la ingesta del **2026-10-06**. La procedencia se guarda en archivos `*.meta.json`, no en columnas adicionales. Los ID pueden ser generados por la transformación cuando faltan o se repiten en RAW.

## ecobici

Estaciones de bicicletas públicas (Ecobici) de la Ciudad de Buenos Aires.

- **Grano:** una fila = una estación de Ecobici
- **Clave primaria:** `id`

| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |
|---------|------|--------|-----|-------------|------------------|
| `id` | entero | - | no | Identificador único de la estación. | no nulo y único |
| `nombre` | texto | - | no | Nombre de la estación (normalizado a Title Case). | normalizado; sin validación de no vacío en verify.py |
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
| `area_m2` | decimal | m² | no | Superficie del espacio verde en metros cuadrados. | > 0 |
| `clasificacion` | texto | - | no | Clasificación del espacio (plaza, parque, etc.). | libre |

## hospitales

Hospitales de la Ciudad de Buenos Aires; no incluye un dominio independiente de CeSAC.

- **Grano:** una fila = un establecimiento de salud
- **Clave primaria:** `id`

| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |
|---------|------|--------|-----|-------------|------------------|
| `id` | entero | - | no | Identificador único del establecimiento. | no nulo y único |
| `nombre` | texto | - | no | Nombre del hospital. | no vacío |
| `tipo` | texto | - | no | Especialidad o tipo informado por la fuente (esp). | libre |
| `comuna` | entero | comuna | no | Comuna de CABA del establecimiento. | entero en 1..15 |
| `direccion` | texto | - | no | Dirección postal del establecimiento. | libre |
