# Persona 1 — población y procesamiento

Implementado el 28 de octubre de 2026 (Colombia).

F10 usa población censal total de 2022, no una proyección a 2026. Fuente: IDECBA
(GCBA), sobre la base de INDEC, Censo 2022. La ficha oficial enlaza al XLS:
https://www.estadisticaciudad.gob.ar/eyc/wp-content/uploads/2022/12/PB2_22nb.xls

Se conserva el XLS, URL, organismo, fecha UTC y SHA-256 en Bronze y en evidencias/f10.
La licencia de F10 está declarada como No verificada; su revisión corresponde a persona 3.
Se lee exclusivamente la hoja 2022, columna Total. Resultado: 15 comunas únicas,
población entera positiva, suma 3.121.707. SHA-256:
97cd7c23c95f227ed8ef9e6f617ea02d1242a36c37f58c0a6c3cc07fdab1258f

## Reproducir

Desde la raíz, con Python y xlrd==2.0.2 instalado:

    python -m pip install xlrd==2.0.2
    python scripts/ingest_all.py poblacion
    python scripts/exportar_f10.py
    python tests/test_poblacion.py
    python tests/test_verificacion.py
    python tests/test_orquestador.py

El exportador solo escribe evidencias/f10; no cambia SILVER ni publica GOLD.
Para integración demo completa, aislada del lago oficial:

    python scripts/run_pipeline.py --demo

Para intentar las cinco fuentes oficiales en el mismo lote:

    python scripts/run_pipeline.py --ingesta

La ingesta fallida detiene el procesamiento. No se completan sidecars heredados con
metadatos inventados, ni se mezcla población oficial con infraestructura demo.
La infraestructura heredada aún tiene contratos incompatibles y metadatos incompletos.
Por ello la validación oficial aislada de F10 no acredita una corrida oficial completa.

## Contrato para persona 2

SILVER poblacion.csv: comuna,poblacion,anio. Exactamente 15 filas, año 2022.
GOLD indicadores_por_comuna.csv conserva los totales e incorpora poblacion,
anio_poblacion y estas columnas:

| Columna | Fórmula | Unidad |
|---|---|---|
| estaciones_ecobici_por_10000_hab | estaciones_ecobici / poblacion * 10000 | estaciones / 10.000 hab |
| km_ciclovias_por_10000_hab | km_ciclovias / poblacion * 10000 | km / 10.000 hab |
| espacios_verdes_por_10000_hab | espacios_verdes / poblacion * 10000 | espacios / 10.000 hab |
| m2_verdes_por_hab | m2_espacios_verdes / poblacion | m² / hab |
| hospitales_por_10000_hab | hospitales / poblacion * 10000 | hospitales / 10.000 hab |

Se usan sumas sin redondeo intermedio; las tasas se redondean al final a seis decimales.
Población ausente o inválida bloquea la publicación; nunca se sustituye por cero.
Comunas sin infraestructura conservan numerador cero dentro de un lote válido.
_meta.json contiene indicadores_normalizados, normalizacion y fuentes.poblacion.
indicadores conserva solo los totales porque el dashboard actual los suma.
Para una tasa global: sumar numeradores y dividir por la población total; nunca sumar tasas.
Persona 2 debe implementar el selector y mostrar el año 2022 junto al denominador.

## Evidencias y validación

evidencias/f10/poblacion.csv contiene población oficial. validacion.json reconcilia
el XLS. demo_indicadores_por_comuna.csv y su .meta.json son un ejemplo con datos
ficticios de las cinco fuentes: sirven para probar el contrato, no como resultados oficiales.
Se comprobó la extracción de las comunas 1, 8 y 15: 223.554, 204.367 y 196.876.
Las pruebas comparan cinco tasas en las 15 comunas contra cálculos independientes,
rechazan población faltante, duplicada, fraccionaria, no finita o no positiva,
año incorrecto y alteración de SILVER. GOLD también revalida los hashes de BRONZE.
La revisión humana de fuente, fórmulas y tres comunas sigue pendiente.

## Aporte real a bitácora (para consolidar por persona 3)

| Fecha y responsable | Encargo real | Aporte IA | Decisión | Verificación |
|---|---|---|---|---|
| 2026-10-28, responsable humano pendiente de completar | “haz la persona 1 ignora lo anteriro que te dije”, con la ruta local del proyecto | Verificación de la fuente oficial, integración F10, tasas, controles de hashes, pruebas y entrega local | Usar censo 2022 y licencia no verificada; mantener bloqueo de infraestructura heredada | Descarga real, reconciliación de 15 comunas y pruebas automatizadas; revisión humana pendiente |
