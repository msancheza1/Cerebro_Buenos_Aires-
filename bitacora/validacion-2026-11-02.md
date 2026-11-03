# Validación de las correcciones — 2026-11-02

Base: `8d293660160a9d6e5240a427c515efcc487abb03`.
Entorno: Python 3, xlrd 2.0.2, shapely 2.1.2, pyproj 3.7.2.

| Comando / comprobación | Resultado |
|---|---|
| `python -m unittest discover -s tests -p 'test_*.py'` sin GOLD demo previo | 20 pruebas OK |
| `python scripts/run_pipeline.py --demo` en copia nueva | 13 etapas completadas |
| `python tests/test_verificacion.py` | 6 casos OK |
| Generador HTML contra `evidencias/oficial/gold` | 15 comunas; HTML oficial regenerado |

La prueba demo usa una fixture temporal; ya no depende de un `build/demo/gold`
creado por una ejecución anterior. No fue necesario cambiar el orden del pipeline.
Las entradas incompletas o no finitas bloquean el generador antes de escribir el HTML.
Los ceros observados siguen siendo válidos. Se regeneraron ambas vistas estáticas.

No se ejecutó validación visual del sitio desplegado ni comparaciones experimentales
A/B con las herramientas alternativas. No se modificaron evidencias oficiales.
GitHub rechazó crear la rama remota con HTTP 403 `Resource not accessible by integration`;
el cambio queda disponible como commit local y parche aplicable a una rama del equipo.
