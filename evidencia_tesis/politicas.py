"""Reproducción contrafactual de políticas de compra sobre demanda conocida.

Se usa únicamente para la evaluación de la tesis; no altera compras reales.
"""
from decimal import Decimal
from statistics import mean

from inventario.procurement import redondear_compra


def simular(demanda, pronostico, *, plazo, cobertura, inventario_inicial,
            precio, moq=0, multiplo=1, costo_pedido=0,
            costo_mantenimiento=0.02, costo_faltante=5):
    """Evalúa una política objetivo S con pronóstico fijado antes del tramo de prueba."""
    if plazo < 1 or cobertura < 1 or len(pronostico) < len(demanda) + plazo + cobertura:
        raise ValueError('La proyección debe cubrir prueba, entrega y cobertura.')
    if min(demanda, default=0) < 0 or min(pronostico, default=0) < 0:
        raise ValueError('La demanda no puede ser negativa.')
    stock = Decimal(str(inventario_inicial))
    precio = Decimal(str(precio))
    pendientes = []
    faltantes = Decimal(0)
    atendido = Decimal(0)
    inventarios = []
    compras = Decimal(0)
    ordenes = 0
    dias_quiebre = 0
    for dia, valor in enumerate(demanda):
        stock += sum((cantidad for llegada, cantidad in pendientes if llegada == dia), Decimal(0))
        pendientes = [(llegada, cantidad) for llegada, cantidad in pendientes if llegada > dia]
        real = Decimal(str(valor))
        vendido = min(stock, real)
        atendido += vendido
        faltantes += real - vendido
        dias_quiebre += int(vendido < real)
        stock -= vendido
        inventarios.append(stock)
        objetivo = sum((Decimal(str(x)) for x in pronostico[dia + 1:dia + 1 + plazo + cobertura]), Decimal(0))
        posicion = stock + sum((cantidad for _, cantidad in pendientes), Decimal(0))
        cantidad = redondear_compra(objetivo - posicion, Decimal(str(moq)), Decimal(str(multiplo)))
        if cantidad > 0:
            pendientes.append((dia + plazo, cantidad))
            compras += cantidad
            ordenes += 1
    total = sum((Decimal(str(x)) for x in demanda), Decimal(0))
    inventario_medio = mean(inventarios)
    costo = (compras * precio + Decimal(ordenes) * Decimal(str(costo_pedido))
             + sum(inventarios, Decimal(0)) * Decimal(str(costo_mantenimiento))
             + faltantes * Decimal(str(costo_faltante)))
    return {
        'dias_quiebre': dias_quiebre,
        'demanda_total': float(total),
        'atendida': float(atendido),
        'faltante': float(faltantes),
        'nivel_atencion_pct': float(atendido / total * 100) if total else 100.0,
        'inventario_medio': float(inventario_medio),
        'compras': float(compras),
        'ordenes': ordenes,
        'costo_simulado': float(costo),
    }
