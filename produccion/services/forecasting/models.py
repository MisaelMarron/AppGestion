import warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from .features import caracteristicas

PARAMETROS = {
    'Holt-Winters': {'trend':'add','seasonal':'add','seasonal_periods':7},
    'SARIMA': {'order':(1,1,1),'seasonal_order':(1,0,1,7),'maxiter':80},
    'Random Forest': {'n_estimators':100,'max_depth':8,'min_samples_leaf':2,'random_state':42,'n_jobs':1},
    'Promedio móvil': {'ventana':7},
}


def ajustar(nombre, serie, parametros=None):
    params = dict(parametros or PARAMETROS[nombre])
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always')
        if nombre == 'Holt-Winters':
            model = ExponentialSmoothing(serie.to_numpy(),**params).fit(optimized=True)
        elif nombre == 'SARIMA':
            iterations = params.pop('maxiter',80)
            model = SARIMAX(serie.to_numpy(),**params).fit(disp=False,maxiter=iterations)
            if not model.mle_retvals.get('converged',True):
                raise ValueError('SARIMA no convergió; candidato descartado.')
        elif nombre == 'Random Forest':
            x = caracteristicas(serie).dropna()
            if len(x) < 10:
                raise ValueError('Filas insuficientes después de lags.')
            model = RandomForestRegressor(**params).fit(x,serie.loc[x.index])
        else:
            model = float(serie.tail(7).mean())
    return model, [str(w.message) for w in captured]


def predecir(nombre, modelo, serie, horizonte):
    if nombre == 'Random Forest':
        history = serie.copy()
        values = []
        for _ in range(horizonte):
            date = history.index[-1]+pd.Timedelta(days=1)
            history.loc[date] = np.nan
            row = caracteristicas(history).iloc[[-1]]
            value = max(0.,float(modelo.predict(row)[0]))
            history.loc[date] = value
            values.append(value)
    elif nombre == 'Promedio móvil':
        values = [modelo]*horizonte
    else:
        values = modelo.forecast(horizonte)
    result = np.maximum(0,np.asarray(values,dtype=float))
    if not np.isfinite(result).all():
        raise ValueError('El modelo produjo valores no finitos.')
    return result.tolist()
