"""Contrato F10: población censal total 2022, una fila por comuna."""
import csv
import math
import re
from pathlib import Path

ANIO = 2022
TOTAL = 3121707


def entero(value):
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"entero inválido: {value!r}") from None
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f"entero inválido: {value!r}")
    return int(number)


def validar(rows):
    clean = [{key: entero(row.get(key)) for key in ("comuna", "poblacion", "anio")}
             for row in rows]
    if len(clean) != 15 or {row['comuna'] for row in clean} != set(range(1, 16)):
        raise ValueError("F10 requiere las 15 comunas únicas (1..15)")
    if any(row['poblacion'] <= 0 or row['anio'] != ANIO for row in clean):
        raise ValueError("F10 requiere población positiva y año 2022")
    return sorted(clean, key=lambda row: row['comuna'])


def extraer_xls(path):
    import xlrd
    book = xlrd.open_workbook(str(path))
    sheet = book.sheet_by_name(str(ANIO))
    if sheet.cell_value(1, 0) != 'Comuna' or sheet.cell_value(2, 1) != 'Total':
        raise ValueError("Cambió el contrato XLS F10: Comuna / Total")
    rows = []
    for i in range(sheet.nrows):
        match = re.fullmatch(r'Comuna\s+(\d+)', str(sheet.cell_value(i, 0)).strip())
        if match:
            rows.append(dict(comuna=int(match[1]), poblacion=sheet.cell_value(i, 1), anio=ANIO))
    clean = validar(rows)
    total = entero(sheet.cell_value(3, 1))
    if total != TOTAL or sum(row['poblacion'] for row in clean) != total:
        raise ValueError("F10 no reconcilia con el total oficial 3.121.707")
    return clean


def limpiar(path):
    if Path(path).suffix == '.xls':
        rows = extraer_xls(path)
    else:
        with Path(path).open(encoding='utf-8-sig', newline='') as stream:
            rows = validar(list(csv.DictReader(stream)))
    return rows, {}, len(rows)


TASAS = {
    'estaciones_ecobici_por_10000_hab': ('estaciones_ecobici', 10000, 'estaciones / 10.000 habitantes'),
    'km_ciclovias_por_10000_hab': ('km_ciclovias', 10000, 'km / 10.000 habitantes'),
    'espacios_verdes_por_10000_hab': ('espacios_verdes', 10000, 'espacios / 10.000 habitantes'),
    'm2_verdes_por_hab': ('m2_espacios_verdes', 1, 'm² / habitante'),
    'hospitales_por_10000_hab': ('hospitales', 10000, 'hospitales / 10.000 habitantes'),
}


def normalizar(rows, poblacion):
    by_comuna = {row['comuna']: row for row in validar(poblacion)}
    for row in rows:
        population = by_comuna[row['comuna']]
        row.update(poblacion=population['poblacion'], anio_poblacion=population['anio'])
        for name, (numerator, factor, _) in TASAS.items():
            row[name] = round(row[numerator] / row['poblacion'] * factor, 6)
    return rows
