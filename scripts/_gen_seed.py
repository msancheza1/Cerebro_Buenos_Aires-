#!/usr/bin/env python3
"""
Generador de DATOS SEMILLA para ejecutar el pipeline sin internet.

⚠️ NO son observaciones oficiales ni prueban el esquema actual de BA Data. Implementan
el contrato de demostración del proyecto, usan valores plausibles y se guardan fuera
del lago oficial para impedir que una demo sobrescriba o se mezcle con una descarga.
"""
from __future__ import annotations
import csv
import datetime as dt
import io
import json
import random
from pipeline_common import (MODE, RAW, ROOT, atomic_write_text, display_path,
                             sha256_bytes)

random.seed(1515)  # reproducible
RUN_ID = "demo-seed-v1"

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
    archivo = d / "seed.csv"
    atomic_write_text(archivo, contenido)
    meta = {
        "dominio": dominio,
        "fuente": "Buenos Aires Data (fuente de referencia; datos generados)",
        "organismo": organismo,
        "url": url,
        "licencia": "CC-BY",
        "formato": "csv",
        "fecha_ingesta": dt.datetime.now().isoformat(timespec="seconds"),
        "herramienta": "generador_semilla",
        "_origen": "semilla_demo",
        "run_id": RUN_ID,
        "filas": len(filas),
        "bytes": len(contenido.encode("utf-8")),
        "sha256": sha256_bytes(contenido.encode("utf-8")),
    }
    atomic_write_text(archivo.with_suffix(".csv.meta.json"),
                      json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"[seed] {dominio:16s} {len(filas):>4d} filas -> {display_path(archivo)}")


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
    archivo = d / "seed.geojson"
    contenido = json.dumps(fc, ensure_ascii=False, indent=2)
    atomic_write_text(archivo, contenido)
    meta = {
        "dominio": "comunas", "fuente": "Buenos Aires Data (fuente de referencia; datos generados)",
        "organismo": "GCBA", "url": "https://data.buenosaires.gob.ar/dataset/comunas",
        "licencia": "CC-BY", "formato": "geojson",
        "fecha_ingesta": dt.datetime.now().isoformat(timespec="seconds"),
        "herramienta": "generador_semilla", "_origen": "semilla_demo",
        "run_id": RUN_ID, "features": len(feats),
        "bytes": len(contenido.encode("utf-8")),
        "sha256": sha256_bytes(contenido.encode("utf-8")),
    }
    atomic_write_text(archivo.with_suffix(".geojson.meta.json"),
                      json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"[seed] comunas          {len(feats):>4d} features -> {display_path(archivo)}")


if __name__ == "__main__":
    if MODE != "demo":
        raise SystemExit("La semilla solo puede generarse con CEREBRO_MODE=demo.")
    if RAW == (ROOT / "lago" / "raw").resolve():
        raise SystemExit("La semilla no puede escribirse en el lago oficial.")
    print(f"Generando datos semilla NO OFICIALES en {display_path(RAW)}/\n")
    gen_ecobici()
    gen_ciclovias()
    gen_espacios_verdes()
    gen_hospitales()
    gen_comunas()
    print("\n[ok] Semilla demo aislada del lago oficial.")
