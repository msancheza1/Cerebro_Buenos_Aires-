# Ejecución oficial verificada — Lote `20261028T145728Z` (2026-10-28)

**Proyecto:** Cerebro Buenos Aires  
**Run ID:** `20261028T145728Z`  
**Fecha de ingesta y verificación:** `2026-10-28T14:57:29Z` – `2026-10-28T15:01:23Z`  
**Estado de calidad (`quality_status`):** `verified`  
**Procedencia (`provenance_status`):** `official`  

---

## 1. Resumen ejecutivo del lote oficial

El lote `20261028T145728Z` completó de punta a punta la cadena **BRONZE → SILVER → Verificación atómica → GOLD → Vistas (`app/official/index.html`)** descargando los recursos reales desde **Buenos Aires Data (GCBA)** e **IDECBA / INDEC (Censo 2022)** sin mezclar semillas demo.

| Dominio | Filas en BRONZE | Filas publicables en SILVER | Cuarentena / Descarte | Tasa de descarte | `raw_sha256` (BRONZE) | `sha256` (SILVER CSV) |
|---|---:|---:|---:|---:|---|---|
| `ecobici` | 407 | **406** | 1 (`id=541`, `AEROPARQUE`) | 0,246 % (< 10 %) | `a41f9424...604af107` | `8462d9b8...fdbc596` |
| `ciclovias` | 2.764 | **2.764** | 0 | 0,000 % | `ecd86946...5c0dba59` | `7921d094...d2cabde` |
| `espacios_verdes` | 2.176 | **2.176** | 0 (25 geometrías reparadas con `make_valid`) | 0,000 % | `eb848cf8...85eb728` | `e44632c5...fbb7578` |
| `hospitales` | 36 | **36** | 0 | 0,000 % | `c511be47...4c2bed83` | `81e08b45...d3c441f` |
| `poblacion` (F10) | 15 comunas | **15** | 0 (reconcilia total CABA = `3.121.707` hab.) | 0,000 % | `97cd7c23...dab1258f` | `6cc1eaab...7f2462f` |
| `comunas` (auxiliar) | 15 polígonos | 15 | 0 | 0,000 % | `c128dadf...9de062e` | *(auxiliar espacial)* |

---

## 2. Decisiones técnicas y hallazgos durante la transformación real

1. **Ecobici (`406/407` estaciones):**
   - El recurso actual de BA Data (`nuevas-estaciones-bicicletas-publicas.csv`) informa `id`, `nombre`, `latitud`, `longitud`, sin columna de comuna ni capacidad de anclajes.
   - La comuna se asignó mediante cruce espacial punto-en-polígono contra la capa oficial `comunas.geojson` (`sha256: c128dadf...`).
   - La estación `541 AEROPARQUE` cayó fuera de la intersección con los polígonos costeros descargados y fue enviada a cuarentena trazable (`0,246 %` de descarte, muy por debajo del umbral máximo de `10 %`).
2. **Ciclovías (`2.764` tramos):**
   - El CSV oficial (`ciclovias.csv`) incluye `comuna` (`1..15`) y `longitud_m` por tramo. Se conserva la longitud oficial por tramo sin subdividir líneas en fronteras comunales, sumando **`305,84 km`** en CABA.
3. **Espacios verdes (`2.176` polígonos):**
   - `25` geometrías inválidas fueron reparadas con `shapely.make_valid` antes de calcular el área y el punto representativo.
   - El área (`15.837.242,5 m²` totales) se calculó en la proyección oficial de CABA **`EPSG:9498`** y representa la superficie geométrica de los polígonos públicos (no equivale a cobertura vegetal foliada).
4. **Hospitales (`36` establecimientos):**
   - Las coordenadas de `hospitales.geojson` venían en proyección métrica `EPSG:9498` y se reproyectaron a `WGS84` (`EPSG:4326`) para validar el *bounding box* de CABA.
   - Como el archivo oficial repite `id=0`, se generó una clave primaria determinística y estable a partir de `nombre + dirección`.
5. **Población censal 2022 (`F10`, `3.121.707` habitantes):**
   - Extraída de `PB2_22nb.xls` (IDECBA sobre base INDEC, Censo Nacional de Población, Hogares y Viviendas 2022).
   - Se verificó que la suma de las 15 comunas coincide exactamente con el total de la Ciudad Autónoma de Buenos Aires (`3.121.707`).

---

## 3. Verificación independiente y humana de las 75 tasas por habitante

Además de la comprobación automática de las **75 tasas** ($15 \text{ comunas} \times 5 \text{ indicadores}$) en `scripts/evidencia_oficial.py` (lote oficial) y `tests/test_poblacion.py` (datos demo), se realizó la verificación manual sobre **3 comunas testigo** (extremos norte/centro, sur y noroeste):

| Comuna | Población (Censo 2022) | Ecobici (tot / tasa ×10k) | Ciclovías (km / tasa ×10k) | Esp. verdes (tot / tasa ×10k) | Sup. verde (m² / m² por hab.) | Hospitales (tot / tasa ×10k) | Estado revisión |
|---:|---:|---|---|---|---|---|---|
| **Comuna 1** | 223.554 | 57 → **`2,55`** | 39,20 km → **`1,75`** | 387 → **`17,31`** | 3.260.171,8 → **`14,58`** | 0 → **`0,00`** | ✓ Verificado |
| **Comuna 8** | 204.367 | 8 → **`0,39`** | 9,51 km → **`0,47`** | 400 → **`19,57`** | 3.815.131,5 → **`18,67`** | 1 → **`0,05`** | ✓ Verificado |
| **Comuna 15** | 196.876 | 34 → **`1,73`** | 22,51 km → **`1,14`** | 94 → **`4,77`** | 219.479,6 → **`1,11`** | 2 → **`0,10`** | ✓ Verificado |

- **Fórmulas auditadas:**
  - $\text{Tasa por } 10.000\text{ hab.} = \frac{\text{Total comunal}}{\text{Población comunal 2022}} \times 10.000$
  - $\text{m}^2\text{ verdes por hab.} = \frac{\text{m}^2\text{ espacios verdes comunal}}{\text{Población comunal 2022}}$
- **Responsable de verificación humana y visual del dashboard:** Juan José Díaz (`2026-11-01`), contrastando `evidencias/oficial/resumen.json`, `evidencias/oficial/gold/indicadores_por_comuna.csv` y la vista publicada en `app/official/index.html`.

---

## 4. Auditoría de licencias (corrección 2026-11-02)

La tabla anterior atribuía una licencia uniforme sin evidencia individual suficiente.
La revisión actual está en [licencias por fuente](../catalogo/licencias.md) y
[catálogo](../catalogo/catalogo.csv), con URL, fecha y estado de cada comprobación.
Se verificó `CC-BY-2.5-AR` en nueve fichas. F9 (respuesta del endpoint CKAN) y
F10 (XLS censal IDECBA) siguen sin declaración explícita verificada.
Este estado de licencia es independiente de la verificación técnica del lote.
