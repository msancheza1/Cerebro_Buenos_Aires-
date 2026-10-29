"""Archiva el lote oficial verificado y revalida copias portables antes de entregarlas."""
import _utf8
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from pipeline_common import ROOT, RAW, SILVER, REQUIRED_DOMAINS, reference_path, resolve_reference, sha256_file


def main():
    report = json.loads((SILVER/'_verificacion.json').read_bytes())
    if report['quality_status'] != 'verified' or report['provenance_status'] != 'official':
        raise ValueError('Solo se archiva una ejecución oficial verificada')
    output = ROOT/'evidencias/oficial'
    run = RAW/'runs'/report['run_id']
    if not run.is_dir():
        raise ValueError('No existe el lote BRONZE verificado')
    shutil.copytree(run,output/'raw',dirs_exist_ok=True)
    (output/'silver').mkdir(parents=True,exist_ok=True)
    for domain in REQUIRED_DOMAINS:
        for suffix in ('.csv','.parquet'):
            source=SILVER/(domain+suffix)
            if source.exists(): shutil.copy2(source,output/'silver'/source.name)
        meta=json.loads((SILVER/f'{domain}.meta.json').read_bytes())
        original=resolve_reference(meta['raw_file'])
        copy=output/'raw'/domain/original.name
        if sha256_file(copy) != meta['raw_sha256']:
            raise ValueError('Cambió un original al copiarlo')
        meta['raw_file']=reference_path(copy)
        for aux in meta.get('auxiliares',[]):
            aux['raw_file']=reference_path(output/'raw'/'comunas'/Path(aux['raw_file']).name)
        (output/'silver'/f'{domain}.meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    env=dict(os.environ,CEREBRO_SILVER_DIR=str(output/'silver'),CEREBRO_GOLD_DIR=str(output/'gold'),
             CEREBRO_APP_DIR=str(ROOT/'app/official'))
    for script in ('verify.py','build_gold.py','build_dashboard.py'):
        subprocess.run([sys.executable,str(ROOT/'scripts'/script)],env=env,check=True)
    def read(path):
        with path.open(encoding='utf-8') as f: return list(csv.DictReader(f))
    rows=read(output/'gold/indicadores_por_comuna.csv')
    checked=0
    samples=[]
    for row in rows:
        pop=int(row['poblacion']); c=int(row['comuna'])
        def records(domain):
            return [r for r in read(output/'silver'/f'{domain}.csv') if int(r['comuna'])==c]
        expected={
            'estaciones_ecobici_por_10000_hab':len(records('ecobici'))/pop*10000,
            'km_ciclovias_por_10000_hab':sum(float(r['long_metros']) for r in records('ciclovias'))/1000/pop*10000,
            'espacios_verdes_por_10000_hab':len(records('espacios_verdes'))/pop*10000,
            'm2_verdes_por_hab':sum(float(r['area_m2']) for r in records('espacios_verdes'))/pop,
            'hospitales_por_10000_hab':len(records('hospitales'))/pop*10000,
        }
        for name,value in expected.items():
            if abs(float(row[name])-round(value,6))>0.0000001:
                raise ValueError(f'Tasa incorrecta: comuna {c}, {name}')
            checked+=1
        if c in (1,8,15): samples.append({'comuna':c,'poblacion':pop,'tasas_recalculadas':expected})
    if len(rows)!=15 or sum(int(r['poblacion']) for r in rows)!=3121707:
        raise ValueError('Población final no reconcilia')
    summary=dict(run_id=report['run_id'],quality_status='verified',provenance_status='official',
        comunas=15,poblacion_total=3121707,anio_poblacion=2022,tasas_recalculadas=checked,
        muestras=samples,filas={d:report['resultado'][d]['filas'] for d in REQUIRED_DOMAINS},
        observaciones=['Ecobici 541 AEROPARQUE: excluida por falta de intersección con polígonos oficiales; 1/407.',
        '25 geometrías de espacios verdes reparadas con make_valid para calcular área y punto representativo.',
        'Superficie de polígonos públicos calculada en EPSG:9498; no mide cobertura vegetal.',
        'Ciclovías conserva comuna y longitud_m oficiales por tramo; no subdivide fronteras.',
        'El dashboard generado conserva totales; el selector de tasas corresponde a persona 2.',
        'Licencia F10 sin verificar; la revisión humana sigue pendiente.'])
    (output/'resumen.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Evidencia oficial portable: 75 tasas recalculadas, 15 comunas y seis originales con SHA-256.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
