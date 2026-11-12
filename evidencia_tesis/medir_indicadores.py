"""Mide R² externo y tiempos del pronóstico en una base de prueba aislada.

Usa la selección ya obtenida por evaluar_365.py. El ajuste se repite con el
primer 80 % cronológico de cada serie y R² se calcula sobre el 20 % final.
Los tiempos son observaciones de esta ejecución, no garantías de rendimiento.
"""
import argparse
import json
import os
import platform
import statistics
import sys
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if not os.environ.get('OPERA_DB_PATH'):
    raise SystemExit('Defina OPERA_DB_PATH para utilizar una base de prueba aislada.')

parser = argparse.ArgumentParser(description='Medición reproducible de indicadores.')
parser.add_argument('--evaluacion', type=Path, default=ROOT / 'evidencia_tesis/resultados/evaluacion_365.json')
parser.add_argument('--output', type=Path, default=ROOT / 'evidencia_tesis/resultados/indicadores_365.json')
args = parser.parse_args()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

import numpy as np
import sklearn
import statsmodels
from sklearn.metrics import r2_score
from inventario.models import MateriaPrima
from produccion.services.forecasting.preprocessing import preparar
from produccion.services.forecasting.models import ajustar, predecir

seleccion = {
    row['codigo']: row for row in json.loads(args.evaluacion.read_text(encoding='utf-8'))['filas']
    if 'modelo_elegido_solo_en_train' in row
}
filas = []
for mp in MateriaPrima.objects.order_by('codigo'):
    if mp.codigo not in seleccion:
        continue
    anterior = seleccion[mp.codigo]
    serie, _ = preparar(mp)
    # La base puede recibir registros posteriores a la evaluación publicada.
    # Se conserva exactamente su ventana de 365 días.
    serie = serie.loc[:'2026-11-04']
    corte = int(len(serie) * .8)
    train, test = serie.iloc[:corte], serie.iloc[corte:]
    if len(train) != anterior['train_dias'] or len(test) != anterior['test_dias']:
        raise ValueError(f'La serie de {mp.codigo} cambió desde evaluar_365.py')
    modelo = anterior['modelo_elegido_solo_en_train']
    inicio = perf_counter_ns()
    ajustado, _ = ajustar(modelo, train)
    ajuste_ms = (perf_counter_ns() - inicio) / 1e6
    predicho = predecir(modelo, ajustado, train, len(test))
    r2 = float(r2_score(test.to_numpy(), predicho))
    if not np.isfinite(r2):
        raise ValueError(f'R² no finito para {mp.codigo}')
    tiempos_ms = []
    for _ in range(3):
        inicio = perf_counter_ns()
        predecir(modelo, ajustado, train, 60)
        tiempos_ms.append((perf_counter_ns() - inicio) / 1e6)
    filas.append({
        'codigo': mp.codigo, 'modelo': modelo,
        'dias_ajuste': len(train), 'dias_prueba': len(test),
        'r2_externo': round(r2, 4),
        'ajuste_ms': round(ajuste_ms, 2),
        'pronostico_60d_mediana_ms': round(statistics.median(tiempos_ms), 2),
        'pronostico_60d_repeticiones_ms': [round(t, 2) for t in tiempos_ms],
    })

resumen = {
    'protocolo': 'Selección interna previa; ajuste del ganador en el 80 % inicial; R² sobre el 20 % final; tiempo de ajuste de una ejecución; mediana de tres pronósticos de 60 días consecutivos por insumo.',
    'entorno': {'python': platform.python_version(), 'sistema': platform.platform(), 'sklearn': sklearn.__version__, 'statsmodels': statsmodels.__version__},
    'insumos': len(filas),
    'r2_mediana': round(statistics.median(x['r2_externo'] for x in filas), 4),
    'r2_minimo': min(x['r2_externo'] for x in filas),
    'r2_maximo': max(x['r2_externo'] for x in filas),
    'ajuste_mediana_ms': round(statistics.median(x['ajuste_ms'] for x in filas), 2),
    'ajuste_minimo_ms': min(x['ajuste_ms'] for x in filas),
    'ajuste_maximo_ms': max(x['ajuste_ms'] for x in filas),
    'pronostico_60d_mediana_ms': round(statistics.median(x['pronostico_60d_mediana_ms'] for x in filas), 2),
    'pronostico_60d_minimo_ms': min(x['pronostico_60d_mediana_ms'] for x in filas),
    'pronostico_60d_maximo_ms': max(x['pronostico_60d_mediana_ms'] for x in filas),
    'filas': filas,
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in resumen.items() if k != 'filas'}, ensure_ascii=False, indent=2))
