# Diccionario de datos — Cerebro Buenos Aires

Metadatos formales de cada dominio de la capa **SILVER**. Fuente única de verdad: `scripts/diccionario.py`. Los tipos coinciden con `transform_silver.py` y las reglas con `verify.py`.

## ecobici

Estaciones de bicicletas públicas (Ecobici) de la Ciudad de Buenos Aires.

- **Grano:** una fila = una estación de Ecobici
- **Clave primaria:** `id`

| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |
|---------|------|--------|-----|-------------|------------------|
| `id` | entero | - | no | Identificador único de la estación. | no nulo y único |
| `nombre` | texto | - | no | Nombre de la estación (normalizado a Title Case). | no vacío |
| `comuna` | entero | comuna | no | Comuna de CABA donde se ubica la estación. | entero en 1..15 |
| `lat` | decimal | grados | no | Latitud (WGS84). | entre -34.71 y -34.52 (bounding box CABA) |
| `lon` | decimal | grados | no | Longitud (WGS84). | entre -58.54 y -58.33 (bounding box CABA) |
| `anclajes_totales` | entero | anclajes | no | Cantidad de anclajes de la estación. | > 0 |

## ciclovias

Red de ciclovías de la Ciudad de Buenos Aires (geometrías de línea).

- **Grano:** una fila = un tramo de ciclovía
- **Clave primaria:** `id`

| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |
|---------|------|--------|-----|-------------|------------------|
| `id` | entero | - | no | Identificador único del tramo. | no nulo y único |
| `nombre` | texto | - | no | Nombre o calle del tramo de ciclovía. | no vacío |
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
| `nombre` | texto | - | no | Nombre del espacio verde. | no vacío |
| `comuna` | entero | comuna | no | Comuna de CABA del espacio verde. | entero en 1..15 |
| `area_m2` | decimal | m² | no | Superficie del espacio verde en metros cuadrados. | > 0 |
| `clasificacion` | texto | - | no | Clasificación del espacio (plaza, parque, etc.). | libre |
| `lat` | decimal | grados | no | Latitud del centroide (WGS84). | entre -34.71 y -34.52 |
| `lon` | decimal | grados | no | Longitud del centroide (WGS84). | entre -58.54 y -58.33 |

## hospitales

Hospitales y centros de salud de la Ciudad de Buenos Aires.

- **Grano:** una fila = un establecimiento de salud
- **Clave primaria:** `id`

| Columna | Tipo | Unidad | PII | Descripción | Regla de calidad |
|---------|------|--------|-----|-------------|------------------|
| `id` | entero | - | no | Identificador único del establecimiento. | no nulo y único |
| `nombre` | texto | - | no | Nombre del hospital o centro de salud. | no vacío |
| `tipo` | texto | - | no | Tipo de establecimiento (hospital, CeSAC, etc.). | libre |
| `comuna` | entero | comuna | no | Comuna de CABA del establecimiento. | entero en 1..15 |
| `direccion` | texto | - | no | Dirección postal del establecimiento. | libre |
| `lat` | decimal | grados | no | Latitud (WGS84). | entre -34.71 y -34.52 |
| `lon` | decimal | grados | no | Longitud (WGS84). | entre -58.54 y -58.33 |
