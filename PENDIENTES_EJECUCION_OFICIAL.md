# Cómo completar la ejecución oficial

La implementación F10 y la prueba completa con datos ficticios están realizadas.
La tabla oficial de indicadores requiere corregir primero los cuatro contratos de
infraestructura. No basta con añadir run_id a archivos antiguos.

## 1. Descargar un lote nuevo y acreditar el origen

En scripts/fuentes.py, confirmar las URLs vigentes de los recursos oficiales de
Ecobici, ciclovías, espacios verdes y hospitales. Las URLs históricas están en sus
sidecars de lago/raw, pero deben volver a comprobarse antes de usarlas.
Conservar cada descarga sin modificar, con URL original/final, fecha UTC,
organismo, licencia acreditada o explícitamente no verificada, tamaño y SHA-256.
El mismo proceso de ingesta debe crear run_id y _origen=descarga_oficial para el
lote. No atribuir un origen o una fecha nueva a los archivos heredados.

## 2. Adaptar y comprobar cada contrato

Modificar tanto la validación de entrada de scripts/ingest_all.py y
scripts/fuentes.py como los adaptadores de scripts/transform_silver.py.
Mantener el original en Bronze y hacer las conversiones en Silver.

| Fuente | Diferencia observada | Trabajo necesario |
|---|---|---|
| Ecobici | latitud/longitud; comuna vacía en algunas filas; sin anclajes_totales | Mapear latitud a lat y longitud a lon. Asignar comunas ausentes mediante polígonos oficiales trazables. Si el recurso no informa anclajes, acordar ese campo como opcional y actualizar el contrato y su regla de verificación; no inventar valores. El indicador solicitado cuenta estaciones. |
| Ciclovías | longitud_m | Mapear a long_metros y comprobar que la unidad sea metro. Revisar tramos que cruzan comunas para evitar doble conteo o atribuciones arbitrarias. |
| Espacios verdes | area, clasificac y geometría | Verificar que area represente m² y mapear a area_m2; clasificac a clasificacion. Identificar el sistema de coordenadas y derivar una ubicación representativa con una regla explícita. No confundir grados cuadrados con m². |
| Hospitales | com, fna/nam, dir y geometría proyectada; sin id numérico | Mapear comuna/nombre/dirección. Acreditar el CRS de origen antes de transformar a WGS84; no inferirlo solo por los números. Definir un identificador estable, documentado y comprobado contra duplicados. |

Si se usa una capa oficial de comunas para asignación espacial, descargarla y
validarla dentro del lote, guardar también su hash y registrar ese linaje en Silver.
No usar centroides ni identificadores artificiales sin documentar su derivación.
Actualizar scripts/diccionario.py y regenerar el diccionario cuando cambie un contrato.

## 3. Probar los adaptadores antes de publicar

Añadir pruebas con muestras reales de cada recurso: columnas, tipos, unidades,
coordenadas, comuna, claves duplicadas y campos ausentes. Revisar los rechazos y
su efecto sobre los totales. La verificación actual bloquea dominios vacíos,
calidad inválida y más del 10 % de filas descartadas; no elevar el umbral para
ocultar una conversión incorrecta. Guardar recuentos antes y después y explicar
cualquier descarte. Comparar manualmente al menos tres comunas contra las fuentes.

## 4. Ejecutar las cinco fuentes oficiales juntas

Desde la raíz del proyecto:

```powershell
python -m pip install xlrd==2.0.2
python tests/test_poblacion.py
python tests/test_verificacion.py
python tests/test_orquestador.py
python scripts/run_pipeline.py --ingesta
```

Si hay un fallo de ingesta o transformación, corregirlo y repetir el lote completo.
No copiar poblacion.csv oficial sobre una salida demo ni reutilizar un reporte viejo.
Confirmar en lago/silver/_verificacion.json quality_status=verified y
provenance_status=official, con el mismo run_id en los cinco dominios.
Confirmar en lago/gold/_meta.json datos_oficiales=true y las cinco fuentes.
La tabla lago/gold/indicadores_por_comuna.csv debe tener 15 filas, población 2022
positiva y cinco tasas; sus denominadores deben sumar 3.121.707 habitantes.
Comprobar manualmente estaciones/población*10000 y m²/población en tres comunas.

## 5. Entrega a las otras personas

Persona 2: usar las columnas y unidades de PERSONA_1_F10.md, implementar el selector
de totales/tasas en scripts/build_dashboard.py, mostrar año 2022 y “Sin datos” si
no hay población, y validar la salida oficial de app/official/index.html.
Para una tasa de toda la ciudad, sumar numeradores y dividir por la población total.
Nunca sumar las tasas de las comunas.

Persona 3: revisar individualmente las 11 licencias, conservar evidencias y consolidar
los encargos reales y sus verificaciones en la bitácora. El registro de F10 está en
PERSONA_1_F10.md; falta completar el responsable y la revisión humana.

El despliegue del dashboard debe hacerse después de revisar los datos oficiales y
los cambios de visualización. Subir esta implementación a GitHub no acredita esos
pendientes ni una ejecución oficial completa.
