#!/usr/bin/env python3
"""
Generador de DATOS SEMILLA (solo para poder correr el pipeline sin internet).

⚠️  NO son datos oficiales. Cada archivo lleva "_origen": "semilla_demo" en su meta.
    Respetan la ESTRUCTURA real de los datasets de BA Data (columnas y rangos plausibles:
    comunas 1-15, coordenadas dentro de CABA) para que la limpieza/validación/gold
    funcionen igual que con los datos reales.

Cuando corras scripts/ingest_all.py con internet, estos archivos se sobrescriben con
los datos oficiales descargados.
"""
from __future__ import annotations
import csv
import datetime as dt
import io
import json
import random
from pathlib import Path

random.seed(1515)  # reproducible
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "lago" / "raw"
HOY = dt.date.today().isoformat()

# CABA aprox: lat -34.705..-34.526 , lon -58.531..-58.335 ; comunas 1..15
LAT_MIN, LAT_MAX = -34.705, -34.526
LON_MIN, LON_MAX = -58.531, -58.335
COMUNAS = list(range(1, 16))
# Pesos plausibles (centro/norte con más infraestructura)
PESO_COMUNA = {1: 14, 2: 9, 3: 8, 4: 7, 5: 6, 6: 6, 7: 5, 8: 4,
               9: 4, 10: 4, 11: 5, 12: 5, 13: 8, 14: 10, 15: 6}


def rlat():
    return round(random.uniform(LAT_MIN, LAT_MAX), 6)


def rlon():
    return round(random.uniform(LON_MIN, LON_MAX), 6)


def comuna_ponderada():
    pobl = [c for c, w in PESO_COMUNA.items() for _ in range(w)]
    return random.choice(pobl)


def escribir_csv(dominio: str, fieldnames: list[str], filas: list[dict],
                 organismo: str, url: str):
    d = RAW / dominio
    d.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(filas)
    contenido = buf.getvalue()
    (d / f"{HOY}.csv").write_text(contenido, encoding="utf-8")
    (d / f"{HOY}.csv.meta.json").write_text(json.dumps({
        "dominio": dominio,
        "fuente": "Buenos Aires Data",
        "organismo": organismo,
        "url": url,
        "licencia": "CC-BY",
        "formato": "csv",
        "fecha_ingesta": dt.datetime.now().isoformat(timespec="seconds"),
        "herramienta": "semilla",
        "_origen": "semilla_demo",
        "filas": len(filas),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[seed] {dominio:16s} {len(filas):>4d} filas -> {(d / (HOY + '.csv')).relative_to(ROOT)}")


def gen_ecobici():
    filas = []
    n = 300
    for i in range(1, n + 1):
        c = comuna_ponderada()
        # inyectamos algunos defectos realistas para que la limpieza tenga trabajo:
        lat = rlat()
        lon = rlon()
        nombre = f"{i:03d} - Estacion {random.choice(['Plaza','Av','Parque','Estacion','Barrio'])} {i}"
        anclajes = random.choice([12, 16, 20, 24, 28, 32])
        # ~2% con comuna vacía y ~1% coord fuera de rango (para probar validación)
        comuna_val = "" if random.random() < 0.02 else c
        if random.random() < 0.01:
            lat = 0.0  # coordenada inválida a propósito
        filas.append({
            "id": i,
            "nombre": nombre.upper() if random.random() < 0.3 else nombre,
            "comuna": comuna_val,
            "lat": lat,
            "long": lon,
            "anclajes_totales": anclajes,
        })
    escribir_csv("ecobici", ["id", "nombre", "comuna", "lat", "long", "anclajes_totales"],
                 filas, "Secretaría de Transporte y Obras Públicas (GCBA)",
                 "https://data.buenosaires.gob.ar/dataset/estaciones-bicicletas-publicas")


def gen_ciclovias():
    filas = []
    for i in range(1, 121):
        c = comuna_ponderada()
        largo_m = round(random.uniform(120, 3200), 1)
        filas.append({
            "id": i,
            "nombre": f"Ciclovia {random.choice(['Av','Calle','Diag'])} {i}",
            "comuna": c,
            "long_metros": largo_m,
            "tipo": random.choice(["ciclovia", "bicisenda"]),
        })
    escribir_csv("ciclovias", ["id", "nombre", "comuna", "long_metros", "tipo"],
                 filas, "Secretaría de Transporte y Obras Públicas (GCBA)",
                 "https://data.buenosaires.gob.ar/dataset/ciclovias")


def gen_espacios_verdes():
    filas = []
    for i in range(1, 251):
        c = comuna_ponderada()
        area = round(random.uniform(150, 90000), 1)
        filas.append({
            "id": i,
            "nombre": f"{random.choice(['Plaza','Parque','Plazoleta','Jardin'])} {i}",
            "comuna": c,
            "area_m2": area,
            "clasificacion": random.choice(["plaza", "parque", "plazoleta", "jardin"]),
            "lat": rlat(),
            "lon": rlon(),
        })
    escribir_csv("espacios_verdes",
                 ["id", "nombre", "comuna", "area_m2", "clasificacion", "lat", "lon"],
                 filas, "Ministerio de Espacio Público e Higiene Urbana (GCBA)",
                 "https://data.buenosaires.gob.ar/dataset/espacios-verdes")


def gen_hospitales():
    # ~35 hospitales públicos, coordenadas y comuna
    nombres = ["Hospital General", "Hospital de Ninos", "Hospital Materno",
               "Hospital de Agudos", "Hospital de Emergencias", "Hospital Oftalmologico"]
    filas = []
    for i in range(1, 36):
        c = comuna_ponderada()
        filas.append({
            "id": i,
            "nombre": f"{random.choice(nombres)} {i}",
            "tipo": random.choice(["hospital_general", "hospital_especializado"]),
            "comuna": c,
            "direccion": f"Calle {random.randint(1,9999)}",
            "lat": rlat(),
            "lon": rlon(),
        })
    escribir_csv("hospitales",
                 ["id", "nombre", "tipo", "comuna", "direccion", "lat", "lon"],
                 filas, "Ministerio de Salud (GCBA)",
                 "https://data.buenosaires.gob.ar/dataset/hospitales")


def gen_comunas():
    # capa base: 15 comunas (GeoJSON simplificado, sin geometría real -> centroide)
    feats = []
    for c in COMUNAS:
        feats.append({
            "type": "Feature",
            "properties": {"comuna": c, "nombre": f"Comuna {c}"},
            "geometry": {"type": "Point", "coordinates": [rlon(), rlat()]},
        })
    fc = {"type": "FeatureCollection",
          "_origen": "semilla_demo",
          "features": feats}
    d = RAW / "comunas"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{HOY}.geojson").write_text(json.dumps(fc, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    (d / f"{HOY}.geojson.meta.json").write_text(json.dumps({
        "dominio": "comunas", "fuente": "Buenos Aires Data", "organismo": "GCBA",
        "url": "https://data.buenosaires.gob.ar/dataset/comunas",
        "licencia": "CC-BY", "formato": "geojson",
        "fecha_ingesta": dt.datetime.now().isoformat(timespec="seconds"),
        "herramienta": "semilla", "_origen": "semilla_demo", "features": len(feats),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[seed] comunas          {len(feats):>4d} features -> {(d / (HOY + '.geojson')).relative_to(ROOT)}")


if __name__ == "__main__":
    print(f"Generando datos semilla (NO oficiales) en lago/raw/ — {HOY}\n")
    gen_ecobici()
    gen_ciclovias()
    gen_espacios_verdes()
    gen_hospitales()
    gen_comunas()
    print("\n[ok] Semilla lista. Estos datos se sobrescriben al correr ingest_all.py con internet.")
