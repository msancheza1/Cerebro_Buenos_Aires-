# Bitácora de asistencia IA

Registro consolidado el 2026-11-02. Herramienta: Codex en ChatGPT.
Solicitante: integrante del equipo en esta conversación (no se atribuye nombre no confirmado).
Los dos encargos históricos de exploración se conservan en `exploracion.md`.
Este archivo añade encargos observables, sin inventar conversaciones, fechas originales
ni aprobaciones humanas. Las citas son instrucciones del usuario; los subtrabajos
son decisiones técnicas del asistente, no nuevos prompts ficticios.

## IA-03 — Revisión del repositorio

- Fecha de registro/revisión: 2026-11-02.
- Instrucción literal: «revisalo de nuevo que ya esta todo, para ver que flata».
- Entrada: main `8d293660160a9d6e5240a427c515efcc487abb03`, indicaciones del profesor.
- Resultado: detección de prueba dependiente de GOLD demo, conversión de ausencias
  a cero, catálogo genérico, afirmaciones A/B sin ejecuciones y registro IA insuficiente.
- Comprobación automática: 75 tasas oficiales recalculadas; filas embebidas del HTML
  contrastadas con GOLD. El pipeline demo falló antes de crear GOLD; generar GOLD
  manualmente permitió pasar las pruebas existentes.
- Decisión: corregir esos defectos y separar evidencia disponible de pendientes.
- Revisión humana de este encargo: pendiente; no confundir con la revisión humana
  del lote del 2026-11-01 documentada por el equipo en otra bitácora.

## IA-04 — Corrección y verificación

- Fecha: 2026-11-02.
- Instrucción literal: «realiza las correcciones que faltan».
- Entrada: hallazgos IA-03 y mismo commit base.
- Subtrabajo 1: hacer la prueba demo independiente del estado local usando una copia
  temporal de datos y metadatos. Esa fixture sirve para probar el rótulo demo, no
  es un nuevo lote oficial ni la fuente usada por la demo publicada.
- Subtrabajo 2: rechazar números ausentes, no finitos, negativos y población inválida
  antes de publicar HTML; conservar ceros observados. Añadir regresión con subcasos.
- Subtrabajo 3: consultar fichas de licencias, corregir URLs/selección de Comunas y
  dejar F9/F10 explícitamente pendientes donde no se encontró declaración aplicable.
- Subtrabajo 4: corregir el README y la bitácora para no declarar comparaciones
  no ejecutadas como completadas.
- Evidencia de cambios: diff del commit de esta rama; `tests/test_dashboard.py`,
  `scripts/build_dashboard.py`, `catalogo/licencias.md` y documentación enlazada.
- Validación: ver `validacion-2026-11-02.md`.
- Revisión humana: pendiente de revisar el diff y las fichas enlazadas. No se afirma
  que el equipo haya aprobado estos cambios ni que la IA haya hecho una revisión visual.

## Criterio para próximos registros

Añadir fecha, responsable real, herramienta, instrucción exacta, archivos de entrada,
resultado aceptado/rechazado, prueba reproducible y nombre/fecha de revisión humana.
No dividir una sola instrucción en supuestos encargos independientes para inflar el registro.
