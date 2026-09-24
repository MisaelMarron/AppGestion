import hashlib
import os
from pathlib import Path
import joblib
from django.conf import settings
from django.utils import timezone
from inventario.services import auditar
from produccion.models import Entrenamiento
from .preprocessing import preparar
from .models import ajustar, predecir, PARAMETROS
from .evaluation import metricas, seleccionar


def entrenar(materia, usuario=None, corte=None):
    serie, calidad = preparar(materia,corte)
    run = Entrenamiento.objects.create(materia_prima=materia,
        inicio=serie.index[0].date() if len(serie) else None,
        fin=serie.index[-1].date() if len(serie) else None,
        registros=calidad.get('registros_utilizados',0),calidad=calidad, estado='SIN_DATOS')
    if not len(serie) or run.registros == 0:
        auditar(usuario,'ENTRENAMIENTO',run,nuevo={'estado':run.estado})
        return run
    # All candidates share exactly the same chronological holdout; RF forecasts recursively.
    split = int(len(serie)*.8)
    nombres = list(PARAMETROS) if split >= 45 and run.registros >= 30 else ['Promedio móvil']
    resultados = []
    train,test = serie.iloc[:split],serie.iloc[split:]
    for nombre in nombres:
        try:
            if len(train) < 2:
                raise ValueError('Sin suficientes días para evaluar.')
            fitted, avisos = ajustar(nombre,train)
            predicted = predecir(nombre,fitted,train,len(test))
            resultados.append({'modelo':nombre,'metricas':metricas(test,predicted),
                'parametros':PARAMETROS[nombre],'avisos':avisos,
                'validacion':[{'fecha':d.date().isoformat(),'real':float(y),'predicho':p}
                              for d,y,p in zip(test.index,test,predicted)]})
        except Exception as exc:
            # Each candidate is isolated; its failure is retained in the comparison.
            resultados.append({'modelo':nombre,'error':str(exc)})
    best = seleccionar(resultados)
    nombre = best['modelo'] if best else 'Promedio móvil'
    try:
        fitted, avisos = ajustar(nombre,serie)
    except Exception as exc:
        resultados.append({'modelo':nombre,'error':f'Reajuste final falló: {exc}'})
        nombre = 'Promedio móvil'
        best = next((r for r in resultados if r['modelo']==nombre and r.get('metricas')),None)
        fitted, avisos = ajustar(nombre,serie)
    run.modelo = nombre
    run.estado = 'MODELO_DISPONIBLE' if len(nombres)>1 and best else 'DATOS_INSUFICIENTES'
    run.metricas = best['metricas'] if best else {}
    run.comparacion = resultados
    run.validacion = best['validacion'] if best else []
    run.parametros = PARAMETROS[nombre]
    root = Path(settings.MODEL_STORAGE)
    root.mkdir(parents=True,exist_ok=True)
    name = f'{run.version}.joblib'
    target = root/name
    temp = root/f'{name}.tmp'
    joblib.dump({'modelo':fitted,'serie':serie,'nombre':nombre},temp)
    os.replace(temp,target)
    run.artefacto = name
    run.sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
    run.save()
    auditar(usuario,'ENTRENAMIENTO',run,nuevo={'modelo':nombre,'metricas':run.metricas,'estado':run.estado})
    return run
