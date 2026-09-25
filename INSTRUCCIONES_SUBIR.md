# Cómo subir Cerebro Buenos Aires a GitHub

El repo git ya está inicializado y con el commit hecho. Repositorio destino:
**https://github.com/msancheza1/Cerebro_Buenos_Aires-.git**

> Nota: no se pudo hacer el push desde el entorno de Kiro porque el conector de GitHub
> de la sesión no tiene una identidad válida (todas las URLs de github.com se redirigen
> a un gateway interno que respondió `No user principal found`). No es un problema del
> repositorio ni de la URL. Subilo desde tu máquina con cualquiera de estas opciones.

## Opción A — desde esta carpeta (ya tiene historial y commit)

```bash
cd cerebro-buenos-aires
git remote add origin https://github.com/msancheza1/Cerebro_Buenos_Aires-.git  # si ya existe: git remote set-url origin ...
git branch -M main
git push -u origin main
```

Si el repo remoto ya tenía un commit inicial (README/licencia) y rechaza el push:

```bash
git pull origin main --allow-unrelated-histories
# resolvé conflictos si los hubiera
git push -u origin main
```

## Opción B — desde el bundle (repo completo en un archivo)

Se generó `Cerebro_BA.bundle` (carpeta padre del proyecto). Con él:

```bash
git clone Cerebro_BA.bundle Cerebro_BA
cd Cerebro_BA
git remote set-url origin https://github.com/msancheza1/Cerebro_Buenos_Aires-.git
git push -u origin main
```

## Para que Kiro pueda subirlo directamente la próxima vez

Reconectá / reautorizá la **integración de GitHub** en Kiro para la cuenta
`juanjosediazrodriguez`. En una sesión nueva, con la integración activa, el push
(y hasta la apertura de un PR) se puede hacer desde acá.

## Verificar que todo corre (opcional, antes o después de subir)

```bash
bash scripts/run_pipeline.sh          # pipeline completo con datos semilla
python tests/test_verificacion.py     # 6/6 OK
```
