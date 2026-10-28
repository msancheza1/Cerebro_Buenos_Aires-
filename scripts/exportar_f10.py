"""Exporta evidencia oficial F10 aislada; no cambia SILVER/GOLD globales."""
import json
import shutil
from pathlib import Path
from pipeline_common import RAW, ROOT, atomic_write_text
from poblacion import limpiar, TOTAL
from transform_silver import _meta_raw, escribir_silver, SCHEMAS


def main():
    candidates = sorted((RAW / 'runs').glob('*/poblacion/*.xls'))
    if not candidates:
        raise ValueError('Primero ejecutar: python scripts/ingest_all.py poblacion')
    raw = candidates[-1]
    meta = _meta_raw(raw, 'poblacion')
    if meta['_origen'] != 'descarga_oficial':
        raise ValueError('La evidencia F10 requiere descarga oficial')
    rows, rejects, count = limpiar(raw)
    output = ROOT / 'evidencias/f10'
    escribir_silver(output, 'poblacion', rows, SCHEMAS['poblacion'], meta, rejects, count, raw)
    # Referencia portable para compartir la evidencia fuera de esta computadora.
    evidence_meta = output / 'poblacion.meta.json'
    document = json.loads(evidence_meta.read_text(encoding='utf-8'))
    document['raw_file'] = 'evidencias/f10/PB2_22nb.xls'
    atomic_write_text(evidence_meta, json.dumps(document, ensure_ascii=False, indent=2))
    shutil.copy2(raw, output / 'PB2_22nb.xls')
    shutil.copy2(raw.with_suffix('.xls.meta.json'), output / 'PB2_22nb.xls.meta.json')
    atomic_write_text(output / 'validacion.json', json.dumps({
        'estado': 'F10 oficial aislada; no acredita lote completo de infraestructura',
        'comunas': len(rows), 'poblacion_total': sum(r['poblacion'] for r in rows),
        'total_oficial': TOTAL, 'anio': 2022, 'sha256_xls': meta['sha256'],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
