"""
prediccion.py — Servicio de pronóstico de reposición de materias primas.

Calcula, a partir del historial real de consumos (ConsumoMateriaPrima),
cuánto se consume por día de cada materia prima y cuándo se agotará
al ritmo actual, incluyendo análisis de tendencia creciente/decreciente.

No guarda nada en la base de datos: todo se calcula al vuelo, siempre fresco.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from django.db.models import Sum


# ─── Constantes de clasificación ─────────────────────────────────────────────

ESTADO_CRITICO    = 'CRITICO'     # ≤ 7 días
ESTADO_PRONTO     = 'PRONTO'      # ≤ 21 días
ESTADO_PLANIFICAR = 'PLANIFICAR'  # ≤ 45 días
ESTADO_OK         = 'OK'          # > 45 días
ESTADO_SIN_DATOS  = 'SIN_DATOS'   # sin historial de consumo

# Orden de urgencia para ordenar la lista final
ORDEN_URGENCIA = {
    ESTADO_CRITICO:    0,
    ESTADO_PRONTO:     1,
    ESTADO_PLANIFICAR: 2,
    ESTADO_OK:         3,
    ESTADO_SIN_DATOS:  4,
}


def _sum_consumo(materia_prima, desde, hasta=None):
    """Suma la cantidad_usada de ConsumoMateriaPrima en un rango de fechas."""
    from produccion.models import ConsumoMateriaPrima

    qs = ConsumoMateriaPrima.objects.filter(
        materia_prima=materia_prima,
        produccion__fecha__gte=desde,
    )
    if hasta:
        qs = qs.filter(produccion__fecha__lt=hasta)

    return qs.aggregate(total=Sum('cantidad_usada'))['total'] or Decimal('0')


def calcular_pronostico(materia_prima, ventana_dias=30):
    """
    Calcula el pronóstico de reposición para una sola materia prima.

    Args:
        materia_prima: instancia de inventario.MateriaPrima
        ventana_dias:  número de días históricos a analizar (15, 30 o 60)

    Returns:
        dict con todos los indicadores predictivos:
        {
            'materia'           : instancia MateriaPrima,
            'consumo_diario'    : Decimal — kg/L/unidades por día (ventana completa),
            'consumo_ajustado'  : Decimal — consumo_diario ajustado por tendencia,
            'total_consumido'   : Decimal — total en la ventana,
            'dias_restantes'    : float|None — días hasta agotamiento,
            'fecha_agotamiento' : date|None,
            'factor_tendencia'  : float|None — reciente/anterior (None si sin datos),
            'tendencia_dir'     : 'subiendo'|'estable'|'bajando',
            'estado'            : str — CRITICO / PRONTO / PLANIFICAR / OK / SIN_DATOS,
            'dias_hasta_minimo' : float|None,
            'fecha_alerta'      : date|None — cuando llega al stock_mínimo,
        }
    """
    hoy = timezone.now()
    fecha_inicio = hoy - timedelta(days=ventana_dias)

    # ── 1. Total consumido en la ventana completa ──────────────────────────
    total_consumido = _sum_consumo(materia_prima, desde=fecha_inicio)

    if total_consumido == 0:
        # Sin historial: no se puede predecir nada
        return {
            'materia':           materia_prima,
            'consumo_diario':    Decimal('0'),
            'consumo_ajustado':  Decimal('0'),
            'total_consumido':   Decimal('0'),
            'dias_restantes':    None,
            'fecha_agotamiento': None,
            'factor_tendencia':  None,
            'tendencia_dir':     'estable',
            'estado':            ESTADO_SIN_DATOS,
            'dias_hasta_minimo': None,
            'fecha_alerta':      None,
        }

    # ── 2. Tasa de consumo diario promedio ────────────────────────────────
    consumo_diario = total_consumido / Decimal(ventana_dias)

    # ── 3. Análisis de tendencia (mitad reciente vs mitad anterior) ───────
    mitad = ventana_dias // 2
    fecha_mitad = hoy - timedelta(days=mitad)

    consumo_reciente = _sum_consumo(materia_prima, desde=fecha_mitad)
    consumo_anterior = _sum_consumo(materia_prima, desde=fecha_inicio, hasta=fecha_mitad)

    if consumo_anterior > 0 and mitad > 0:
        factor_tendencia = float(consumo_reciente) / float(consumo_anterior)
    else:
        # Solo hay datos en la mitad reciente → no hay referencia anterior
        factor_tendencia = 1.0

    if factor_tendencia > 1.2:
        tendencia_dir = 'subiendo'
    elif factor_tendencia < 0.8:
        tendencia_dir = 'bajando'
    else:
        tendencia_dir = 'estable'

    # Solo ajustar si la tendencia es creciente (ser conservador en el pronóstico)
    if tendencia_dir == 'subiendo':
        consumo_ajustado = consumo_diario * Decimal(str(round(factor_tendencia, 4)))
    else:
        consumo_ajustado = consumo_diario

    # ── 4. Días restantes y fecha de agotamiento ──────────────────────────
    stock = materia_prima.stock_actual
    if consumo_ajustado > 0:
        dias_restantes = float(stock) / float(consumo_ajustado)
        fecha_agotamiento = (hoy + timedelta(days=dias_restantes)).date()
    else:
        dias_restantes = None
        fecha_agotamiento = None

    # ── 5. Días hasta stock mínimo (alerta temprana) ──────────────────────
    exceso = float(stock) - float(materia_prima.stock_minimo)
    if consumo_ajustado > 0 and exceso > 0:
        dias_hasta_minimo = exceso / float(consumo_ajustado)
        fecha_alerta = (hoy + timedelta(days=dias_hasta_minimo)).date()
    else:
        dias_hasta_minimo = 0.0
        fecha_alerta = hoy.date()

    # ── 6. Clasificación de urgencia ──────────────────────────────────────
    if dias_restantes is None:
        estado = ESTADO_SIN_DATOS
    elif dias_restantes <= 7:
        estado = ESTADO_CRITICO
    elif dias_restantes <= 21:
        estado = ESTADO_PRONTO
    elif dias_restantes <= 45:
        estado = ESTADO_PLANIFICAR
    else:
        estado = ESTADO_OK

    return {
        'materia':           materia_prima,
        'consumo_diario':    consumo_diario.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
        'consumo_ajustado':  consumo_ajustado.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
        'total_consumido':   total_consumido,
        'dias_restantes':    round(dias_restantes, 1) if dias_restantes is not None else None,
        'fecha_agotamiento': fecha_agotamiento,
        'factor_tendencia':  round(factor_tendencia, 2),
        'tendencia_dir':     tendencia_dir,
        'estado':            estado,
        'dias_hasta_minimo': round(dias_hasta_minimo, 1) if dias_hasta_minimo is not None else None,
        'fecha_alerta':      fecha_alerta,
    }


def calcular_todos_pronosticos(ventana_dias=30):
    """
    Calcula el pronóstico para todas las materias primas activas.

    Returns:
        Lista de dicts ordenados por urgencia (críticas primero).
    """
    from inventario.models import MateriaPrima

    materias = MateriaPrima.objects.filter(activo=True).select_related('proveedor')
    pronosticos = [calcular_pronostico(mp, ventana_dias) for mp in materias]

    # Ordenar: primero por estado de urgencia, luego por días restantes (menor = más urgente)
    pronosticos.sort(key=lambda p: (
        ORDEN_URGENCIA.get(p['estado'], 9),
        p['dias_restantes'] if p['dias_restantes'] is not None else 9999,
    ))

    return pronosticos
