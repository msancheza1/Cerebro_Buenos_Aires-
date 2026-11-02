# Dependencias web locales

## MapLibre GL JS 5.24.0

Se conserva localmente la última versión 5.x porque ofrece un paquete UMD compatible con
`<script>` clásico y con la apertura directa mediante `file://`. MapLibre 6 es solo ESM y
su carga local depende de las restricciones de módulos del navegador.

- Proyecto: https://maplibre.org/maplibre-gl-js/
- Distribución descargada: https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/
- Licencia: BSD de 3 cláusulas, copiada en `MAPLIBRE-LICENSE.txt`.
- Descarga: 2026-11-01.

| Archivo | Bytes | SHA-256 |
|---|---:|---|
| `maplibre-gl.js` | 1.056.837 | `45a9b07a9189ce56054c620a947ccf41e291e58c95e9b61533b740aaa65ee5cb` |
| `maplibre-gl.css` | 70.024 | `ab1e70d59ec40465bae7e7030da2f3ccf28133fd502e62bd598eefbadfd7a732` |
| `MAPLIBRE-LICENSE.txt` | 5.984 | `ee5fc05a0677eaf69601d2c7db0d9ecd6cc27c3abc1d0733bc9ed34707cf8ef2` |

El mapa base conectado usa el estilo Liberty de OpenFreeMap:
`https://tiles.openfreemap.org/styles/liberty`. No requiere clave. Sus mosaicos se
solicitan únicamente cuando hay conexión; las comunas y los indicadores permanecen
incluidos en cada HTML.
