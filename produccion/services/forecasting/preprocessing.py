from django.conf import settings
"""Datos derivados: días completos anteriores al corte; originales inmutables."""
import numpy as np
import pandas as pd
from django.utils import timezone
from produccion.models import ConsumoMateriaPrima


def preparar(materia, corte=None, frecuencia='D'):
    corte = corte or timezone.localdate()
    rows = list(ConsumoMateriaPrima.objects.filter(materia_prima=materia,
        produccion__fecha__date__lt=corte, produccion__anulada=False, produccion__sintetica=settings.DEMO_MODE)
        .values('id','cantidad_usada','produccion__fecha','excluido_entrenamiento'))
    return preparar_filas(rows, corte, frecuencia)


def preparar_filas(rows, corte, frecuencia='D'):
    if frecuencia not in ['D','W','MS']:
        raise ValueError('Frecuencia no permitida.')
    log = {'originales':len(rows), 'duplicados_id':0, 'invalidos':0, 'excluidos':0,
           'dias_completados':0, 'politica':'Fechas sin operaciones = 0; excluidos = ausente; atípicos conservados.'}
    if not rows:
        return pd.Series(dtype=float), log
    df = pd.DataFrame(rows)
    log['duplicados_id'] = int(df.duplicated('id').sum())
    df = df.drop_duplicates('id').copy()
    df['fecha'] = pd.to_datetime(df['produccion__fecha'], utc=True, errors='coerce').dt.tz_convert('America/Lima').dt.tz_localize(None).dt.normalize()
    df['valor'] = pd.to_numeric(df['cantidad_usada'], errors='coerce')
    invalid = df['fecha'].isna() | ~np.isfinite(df['valor']) | (df['valor'] < 0)
    log['invalidos'] = int(invalid.sum())
    df = df[~invalid & (df['fecha'] < pd.Timestamp(corte))]
    if df.empty:
        return pd.Series(dtype=float), log
    log['excluidos'] = int(df['excluido_entrenamiento'].sum())
    index = pd.date_range(df['fecha'].min(),pd.Timestamp(corte)-pd.Timedelta(days=1),freq='D')
    series = df.groupby('fecha')['valor'].sum().reindex(index, fill_value=0.).astype(float)
    log['dias_completados'] = len(index)-df['fecha'].nunique()
    # An excluded day is unknown, not zero. Causal imputation uses only earlier days.
    excluded_days = df.loc[df['excluido_entrenamiento'],'fecha'].unique()
    for day in sorted(excluded_days):
        previous = series.loc[series.index < day].tail(7)
        series.loc[day] = previous.mean() if len(previous) else np.nan
    series = series.dropna()
    log['registros_utilizados'] = int((~df['excluido_entrenamiento']).sum())
    if frecuencia != 'D':
        series = series.resample(frecuencia).sum()
    return series, log


def anomalias(materia):
    """IQR sobre totales diarios; cada ID del día señalado puede revisarse."""
    series, _ = preparar(materia)
    if len(series) < 8:
        return []
    q1,q3 = series.quantile([.25,.75])
    limite = float(q3+1.5*(q3-q1))
    return [{'fecha':d.date().isoformat(),'consumo':float(v),'limite':limite}
            for d,v in series.items() if v > limite]
