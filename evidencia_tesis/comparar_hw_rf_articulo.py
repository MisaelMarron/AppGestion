"""Reproduce la comparación del artículo con una base SQLite aislada.

OPERA_DB_PATH=/ruta/tesis_demo_365.sqlite3 python evidencia_tesis/comparar_hw_rf_articulo.py
El corte es fijo: solo se usan consumos hasta el 4 de noviembre de 2026.
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if not os.environ.get('OPERA_DB_PATH'):
    raise SystemExit('Defina OPERA_DB_PATH para usar una base aislada.')

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT/'evidencia_tesis/resultados/comparacion_articulo_365.json')
args = parser.parse_args()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

import numpy as np
from inventario.models import MateriaPrima
from produccion.services.forecasting.preprocessing import preparar
from produccion.services.forecasting.models import ajustar, predecir, PARAMETROS
from produccion.services.forecasting.evaluation import metricas

CUTOFF = date(2026, 11, 5)
MODELOS = ('Holt-Winters', 'Random Forest', 'Promedio móvil')

def evaluar(nombre, entrenamiento, prueba):
    if nombre == 'Ingenuo estacional':
        semana = entrenamiento.iloc[-7:].to_numpy(dtype=float)
        predicho = np.resize(semana, len(prueba))
    else:
        modelo, _ = ajustar(nombre, entrenamiento)
        predicho = predecir(nombre, modelo, entrenamiento, len(prueba))
    return metricas(prueba, predicho)

filas = []
for mp in MateriaPrima.objects.order_by('codigo'):
    serie, _ = preparar(mp, corte=CUTOFF)
    if len(serie) < 90 or int((serie > 0).sum()) < 30:
        continue
    corte = int(len(serie) * .8)
    entrenamiento, prueba = serie.iloc[:corte], serie.iloc[corte:]
    principal = {m: evaluar(m, entrenamiento, prueba) for m in MODELOS}
    principal['Ingenuo estacional'] = evaluar('Ingenuo estacional', entrenamiento, prueba)
    origenes = []
    for retroceso in (84, 56, 28):
        inicio = len(serie)-retroceso
        tr, te = serie.iloc[:inicio], serie.iloc[inicio:inicio+28]
        if len(tr) < 90 or len(te) != 28:
            raise ValueError(f'Ventana insuficiente para {mp.codigo}')
        origenes.append({'fin_entrenamiento':tr.index[-1].date().isoformat(),
                         'inicio_prueba':te.index[0].date().isoformat(),
                         'fin_prueba':te.index[-1].date().isoformat(),
                         'rmse':{m:round(evaluar(m,tr,te)['rmse'],6)
                                 for m in (*MODELOS,'Ingenuo estacional')}})
    filas.append({'codigo':mp.codigo,'insumo':mp.nombre,'dias':len(serie),
                  'dias_entrenamiento':len(entrenamiento),'dias_prueba':len(prueba),
                  'ceros_pct':round(float((serie == 0).mean()*100),2),
                  'principal':{m:{'rmse':round(v['rmse'],6),'mae':round(v['mae'],6)}
                               for m,v in principal.items()},'origenes_28d':origenes})

def promedio(xs): return sum(xs)/len(xs)
def errores(modelo, periodo='principal'):
    return [f[periodo][modelo]['rmse'] for f in filas]

hw,rf=errores('Holt-Winters'),errores('Random Forest')
pm=errores('Promedio móvil')
est=errores('Ingenuo estacional')
dif=np.array(hw)-np.array(rf)
azar=np.random.default_rng(42)
bootstrap=np.mean(azar.choice(dif, size=(10000,len(dif)), replace=True), axis=1)
por_origen=[]
for i in range(3):
    por_origen.append({'origen':i+1,
        'victorias_hw':sum(f['origenes_28d'][i]['rmse']['Holt-Winters'] < f['origenes_28d'][i]['rmse']['Random Forest'] for f in filas),
        'victorias_rf':sum(f['origenes_28d'][i]['rmse']['Random Forest'] < f['origenes_28d'][i]['rmse']['Holt-Winters'] for f in filas),
        'rmse_medio':{m:round(promedio([f['origenes_28d'][i]['rmse'][m] for f in filas]),4)
                      for m in (*MODELOS,'Ingenuo estacional')}})
resumen={'corte_exclusivo':CUTOFF.isoformat(),
         'protocolo_principal':'Primer 80 % para ajuste, último 20 % como prueba multihorizonte, idéntico para los cuatro métodos.',
         'protocolo_sensibilidad':'Tres orígenes no superpuestos de 28 días al final de cada serie; los modelos se reajustan con todos los días anteriores a cada origen.',
         'parametros':{m:PARAMETROS[m] for m in MODELOS},
         'insumos':len(filas),
         'rmse_medio':{m:round(promedio(errores(m)),4) for m in (*MODELOS,'Ingenuo estacional')},
         'mae_medio':{m:round(promedio([f['principal'][m]['mae'] for f in filas]),4) for m in (*MODELOS,'Ingenuo estacional')},
         'victorias_hw_vs_rf':sum(a<b for a,b in zip(hw,rf)),
         'victorias_rf_vs_hw':sum(b<a for a,b in zip(hw,rf)),
         'mejora_frente_pm':{m:sum(a<b for a,b in zip(errores(m),pm)) for m in ('Holt-Winters','Random Forest')},
         'mejora_frente_estacional':{m:sum(a<b for a,b in zip(errores(m),est)) for m in ('Holt-Winters','Random Forest')},
         'diferencia_media_hw_menos_rf':round(float(dif.mean()),4),
         'ic_bootstrap_95_diferencia_media':[round(float(x),4) for x in np.percentile(bootstrap,[2.5,97.5])],
         'bootstrap':'Remuestreo de 13 diferencias por insumo, 10 000 repeticiones, semilla 42; intervalo descriptivo del escenario.',
         'origenes_28d':por_origen,'filas':filas}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(resumen,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in resumen.items() if k!='filas'},ensure_ascii=False,indent=2))
