# Licencias por fuente — revisión 2026-11-02

Revisión asistida por Codex. Se transcribe el campo **Licencia** de cada ficha oficial, no una licencia inferida por pertenecer al mismo portal. Las variantes de idioma son páginas del mismo dataset. La consulta se hizo mediante lectura/búsqueda web; no constituye una captura íntegra archivada del portal.

| ID | Fuente | Texto exacto / estado | Evidencia consultada |
|---|---|---|---|
| 1 | Estaciones Ecobici | CC-BY-2.5-AR | [Ficha o recurso](https://data.buenosaires.gob.ar/sr/dataset/estaciones-bicicletas-publicas) |
| 2 | Ciclovías | CC-BY-2.5-AR | [Ficha o recurso](https://data.buenosaires.gob.ar/dataset/ciclovias) |
| 3 | Espacios verdes | CC-BY-2.5-AR | [Ficha o recurso](https://data.buenosaires.gob.ar/es_AR/dataset/espacios-verdes) |
| 4 | Hospitales | CC-BY-2.5-AR | [Ficha o recurso](https://data.buenosaires.gob.ar/es_AR/dataset/hospitales) |
| 5 | Centros de salud (CeSAC) | CC-BY-2.5-AR | [Ficha o recurso](https://data.buenosaires.gob.ar/es/dataset/centros-salud-accion-comunitaria-cesac) |
| 6 | Comunas | CC-BY-2.5-AR | [Ficha o recurso](https://data.buenosaires.gob.ar/es_AR/dataset/comunas) |
| 7 | Barrios | CC-BY-2.5-AR | [Ficha o recurso](https://data.buenosaires.gob.ar/sq/dataset/barrios) |
| 8 | Catálogo de datos (dataset del catálogo) | CC-BY-2.5-AR | [Ficha o recurso](https://data.buenosaires.gob.ar/dataset/datos-publicos) |
| 9 | API CKAN package_search | No verificada | [Ficha o recurso](https://data.buenosaires.gob.ar/api/3/action/package_search) |
| 10 | Población censal por comuna 2022 | No verificada | [Ficha o recurso](https://www.estadisticaciudad.gob.ar/eyc/wp-content/uploads/2022/12/PB2_22nb.xls) |
| 11 | API Transporte Público / GTFS | CC-BY-2.5-AR | [Ficha o recurso](https://data.buenosaires.gob.ar/dataset/api-transporte-publico) |

Texto legal para los nueve datasets que declaran esa licencia: https://creativecommons.org/licenses/by/2.5/ar/legalcode . La atribución debe identificar el organismo y dataset, enlazar la fuente y licencia e indicar las transformaciones realizadas.

## Límites y pendientes explícitos

- **F9 (CKAN package_search):** es un endpoint de descubrimiento. Las licencias de sus paquetes no prueban la licencia global de su respuesta. Queda sin licencia verificada hasta localizar una declaración aplicable a los metadatos.
- **F10 (IDECBA):** no se encontró una declaración explícita aplicable al XLS censal. El acceso público y las leyes citadas en la bitácora anterior no sustituyen una licencia de reutilización. Debe verificarse con IDECBA antes de dar este requisito por cerrado.
- F5 y F8 tenían URLs antiguas; se sustituyeron por las fichas halladas. F11 mezclaba Catastro con transporte y enlazaba la portada: ahora identifica API Transporte Público / GTFS.
- La etiqueta CC-BY-2.5-AR puede coincidir entre fuentes; la corrección es comprobar cada ficha y conservar su versión exacta, no forzar licencias distintas.
