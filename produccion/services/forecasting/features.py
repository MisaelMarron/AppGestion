import pandas as pd


def caracteristicas(series):
    x = pd.DataFrame(index=series.index)
    past = series.shift(1)
    for lag in [1,7,14,30]:
        x[f'consumo_lag_{lag}'] = series.shift(lag)
    for window in [7,14,30]:
        x[f'promedio_movil_{window}'] = past.rolling(window).mean()
    for window in [7,30]:
        x[f'desviacion_{window}'] = past.rolling(window).std(ddof=0)
    x['dia_semana'] = x.index.dayofweek
    x['dia_mes'] = x.index.day
    x['semana_anio'] = x.index.isocalendar().week.astype(int)
    x['mes'] = x.index.month
    x['trimestre'] = x.index.quarter
    x['tendencia_consumo'] = past.rolling(7).mean()-past.rolling(30).mean()
    x['frecuencia_consumo'] = past.gt(0).rolling(30).mean()
    return x
