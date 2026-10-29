# Ejecución oficial: realizada y pendientes restantes

El 28 de octubre de 2026 (Colombia) se completó el procesamiento oficial del lote
20261028T145728Z: descarga → Silver → verificación → Gold → consultas → dashboard local.
No se reutilizaron sidecars heredados ni se mezcló infraestructura demo con F10 oficial.

## Resultados

| Dominio | Filas aceptadas / entrada |
|---|---|
| Ecobici | 406 / 407 |
| Ciclovías | 2764 / 2764 |
| Espacios verdes públicos | 2176 / 2176 |
| Hospitales | 36 / 36 |
| Población | 15 / 15 |

Población censal 2022: 3.121.707 habitantes. Se recalcularon independientemente las
75 tasas (cinco por cada una de las 15 comunas) desde Silver y se contrastaron con Gold.
Las comprobaciones guardan ejemplos de las comunas 1, 8 y 15.
Pruebas: 6 F10, 5 de adaptadores oficiales, 2 del orquestador y 6 reglas existentes.

## Cómo se resolvieron los bloqueos

- Se sustituyeron las URLs 404 por los recursos directos del servidor oficial.
- Se descargó la capa oficial de comunas en el mismo lote y se controla su SHA-256
  tanto al verificar como al construir Gold.
- Ecobici: latitud/longitud y comuna por intersección espacial única. Anclajes queda
  nulo si la fuente no lo informa; la cantidad de estaciones no depende de ese campo.
- Ciclovías: longitud_m se convierte a long_metros, conservando longitud y comuna
  declaradas por tramo; no se subdividen tramos en fronteras comunales.
- Espacios verdes: el GeoJSON declara CRS84. Se reparan 25 geometrías inválidas
  con make_valid y se calcula área en el CRS métrico EPSG:9498 y un punto representativo.
  Esta superficie corresponde a polígonos públicos, no a cobertura vegetal efectiva.
- Hospitales: el GeoJSON declara EPSG:9498; se transforma a WGS84. Se usa una clave
  estable derivada de nombre completo y dirección, comprobando duplicados.

La estación 541 AEROPARQUE (-34.55572, -58.41321) no intersecta los polígonos de comunas
descargados. Se excluye de los indicadores comunales y se registra en cuarentena:
1/407, aproximadamente 0,246 %. No se asigna a la comuna más cercana.

## Evidencias

- evidencias/oficial/raw/: seis descargas originales y sus sidecars, con fecha UTC,
  URL, organismo, tamaño y SHA-256, además del manifiesto del lote.
- evidencias/oficial/silver/: cinco tablas, metadatos de transformación y verificación.
- evidencias/oficial/gold/indicadores_por_comuna.csv: totales, población, año y cinco tasas.
- evidencias/oficial/resumen.json: recuentos, muestras y comprobación de las 75 tasas.
- app/official/index.html: dashboard local generado con los totales oficiales.

## Reproducir

Desde la raíz del proyecto:

```powershell
python -m pip install xlrd==2.0.2 shapely==2.1.2 pyproj==3.7.2
python tests/test_poblacion.py
python tests/test_infraestructura.py
python tests/test_orquestador.py
python tests/test_verificacion.py
python scripts/run_pipeline.py --ingesta
python scripts/evidencia_oficial.py
```

Para verificar la evidencia guardada sin volver a descargar, configurar CEREBRO_SILVER_DIR
con la ruta absoluta de evidencias/oficial/silver y CEREBRO_GOLD_DIR con otra carpeta de
salida; ejecutar scripts/verify.py y después scripts/build_gold.py. Los originales
de evidencia deben conservar sus bytes y ubicación relativa dentro del repositorio.

## Lo que aún falta

1. Revisión humana de tres comunas, de la cuarentena y de las decisiones geográficas.
2. Persona 2: selector de totales/tasas, unidades, año 2022 y validación visual.
   El generador actual conserva los totales; no se acredita esa mejora visual.
3. Persona 3: revisión individual y evidencia de las 11 licencias. F10 sigue como
   No verificada; las cinco fuentes BA Data utilizadas declaran CC-BY-2.5-AR en sus fichas.
4. Revisar y publicar el dashboard final después de integrar la visualización.
5. Completar las comparaciones entre dos herramientas que exige el taller.

El procesamiento oficial realizado no sustituye esos entregables ni acredita un
despliegue público del nuevo dashboard.
