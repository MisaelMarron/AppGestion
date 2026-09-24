import numpy as np


def metricas(real, predicho):
    y,p = np.asarray(real,dtype=float),np.asarray(predicho,dtype=float)
    if len(y) == 0 or len(y) != len(p) or not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError('Evaluación sin datos válidos.')
    error = y-p
    nonzero = y != 0
    return {'mae':float(np.abs(error).mean()),'rmse':float(np.sqrt((error**2).mean())),
            'mape':float((np.abs(error[nonzero]/y[nonzero])).mean()*100) if nonzero.any() else None,
            'mape_n':int(nonzero.sum()), 'ceros_excluidos_mape':int((~nonzero).sum())}


def seleccionar(resultados):
    validos = [r for r in resultados if r.get('metricas')]
    return min(validos, key=lambda r:(r['metricas']['rmse'],r['metricas']['mae'],r['modelo'])) if validos else None
