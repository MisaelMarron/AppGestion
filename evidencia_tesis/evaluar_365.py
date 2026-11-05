"""Evaluación cronológica externa de pronósticos sobre una base aislada.

Ejemplo: OPERA_DB_PATH=/ruta/tesis_demo_365.sqlite3 python evidencia_tesis/evaluar_365.py
"""
import argparse
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if not os.environ.get('OPERA_DB_PATH'):
    raise SystemExit('Defina OPERA_DB_PATH para utilizar una base de prueba aislada.')
parser = argparse.ArgumentParser(description='Evaluar 365 días con partición temporal anidada.')
parser.add_argument('--output', type=Path, default=ROOT/'evidencia_tesis'/'resultados'/'evaluacion_365.json')
args = parser.parse_args()
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from inventario.models import MateriaPrima
from produccion.services.forecasting.preprocessing import preparar
from produccion.services.forecasting.models import ajustar, predecir, PARAMETROS
from produccion.services.forecasting.evaluation import metricas, seleccionar
rows=[]
for mp in MateriaPrima.objects.order_by('codigo'):
    serie, calidad=preparar(mp)
    if len(serie)<90 or int((serie>0).sum())<30:
        rows.append({'codigo':mp.codigo,'insumo':mp.nombre,'dias':len(serie),'registros_positivos':int((serie>0).sum()),'estado':'sin umbral para evaluación externa'})
        continue
    cut=int(len(serie)*.8)
    train,test=serie.iloc[:cut],serie.iloc[cut:]
    inner=int(len(train)*.8)
    train_in,val=train.iloc[:inner],train.iloc[inner:]
    cand=[]
    for name in PARAMETROS:
        try:
            fit,_=ajustar(name,train_in)
            y=predecir(name,fit,train_in,len(val))
            cand.append({'modelo':name,'metricas':metricas(val,y)})
        except Exception as ex:
            cand.append({'modelo':name,'error':str(ex)[:120]})
    best=seleccionar(cand)
    if not best:
        rows.append({'codigo':mp.codigo,'estado':'sin candidato evaluable'});continue
    try:
        fitted,_=ajustar(best['modelo'],train)
        y=predecir(best['modelo'],fitted,train,len(test))
        outcome=metricas(test,y)
        basefit,_=ajustar('Promedio móvil',train)
        base=metricas(test,predecir('Promedio móvil',basefit,train,len(test)))
        rows.append({'codigo':mp.codigo,'insumo':mp.nombre,'dias':len(serie),'train_dias':len(train),'test_dias':len(test),'modelo_elegido_solo_en_train':best['modelo'],'rmse_test':round(outcome['rmse'],4),'mae_test':round(outcome['mae'],4),'mape_test':None if outcome['mape'] is None else round(outcome['mape'],2),'rmse_base':round(base['rmse'],4),'mae_base':round(base['mae'],4),'mejora_rmse_pct':None if base['rmse']==0 else round((base['rmse']-outcome['rmse'])/base['rmse']*100,2),'inner':cand})
    except Exception as ex:rows.append({'codigo':mp.codigo,'insumo':mp.nombre,'estado':'error en evaluación','error':str(ex)[:150]})
valid=[x for x in rows if 'rmse_test' in x]
summary={'evaluados':len(valid),'insumos_totales':len(rows),'mejor_que_base':sum(x['rmse_test']<x['rmse_base'] for x in valid),'igual_base':sum(x['rmse_test']==x['rmse_base'] for x in valid),'peor_que_base':sum(x['rmse_test']>x['rmse_base'] for x in valid),'rmse_medio':round(sum(x['rmse_test'] for x in valid)/len(valid),4) if valid else None,'rmse_base_medio':round(sum(x['rmse_base'] for x in valid)/len(valid),4) if valid else None,'dataset':'escenario de prueba generado con semilla 42; no corresponde a registros de empresa','filas':rows}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(summary,ensure_ascii=False,indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='filas'},ensure_ascii=False,indent=2))
for x in rows:print(x['codigo'],x.get('modelo_elegido_solo_en_train',x.get('estado')),x.get('rmse_test'),x.get('rmse_base'))
