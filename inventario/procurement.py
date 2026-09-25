"""Política S, ROP y recepción. Cantidades y precios con Decimal."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from math import sqrt, ceil
from statistics import NormalDist, mean, pstdev
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import (MateriaPrima, MateriaPrimaProveedor, SugerenciaCompra, OrdenCompra,
    DetalleOrdenCompra, LeadTimeReal, LoteMateriaPrima, MovimientoInventario)
from .services import disponible, reservado, recepciones, auditar, vencido

D = lambda value: Decimal(str(value))


def estadisticas(oferta):
    history = list(LeadTimeReal.objects.filter(detalle__oferta=oferta).values_list('dias',flat=True))
    return {'promedio':mean(history) if history else oferta.lead_time_dias,
            'desviacion':pstdev(history) if history else 0., 'entregas':len(history),
            'cumplimiento':sum(v <= oferta.lead_time_dias for v in history)/len(history)*100 if history else None}


def elegir_oferta(materia):
    ofertas = list(materia.ofertas.filter(activo=True,proveedor__activo=True).select_related('proveedor'))
    return min(ofertas,key=lambda o:(estadisticas(o)['promedio'],o.precio,o.pk)) if ofertas else None


def seguridad(desviacion, lead_time, nivel):
    if not 0 < float(nivel) < 1 or lead_time < 0 or desviacion < 0:
        raise ValidationError('Parámetros de seguridad inválidos.')
    return D(NormalDist().inv_cdf(float(nivel))*float(desviacion)*sqrt(lead_time))


def redondear_compra(cantidad, moq, multiplo):
    if multiplo <= 0 or moq < 0:
        raise ValidationError('MOQ o múltiplo inválido.')
    if cantidad <= 0:
        return D(0)
    return (max(cantidad,moq)/multiplo).to_integral_value(rounding=ROUND_CEILING)*multiplo


def analizar(materia, pronostico=None, oferta=None):
    from produccion.services.forecasting.preprocessing import preparar
    hoy = timezone.localdate()
    oferta = oferta or elegir_oferta(materia)
    fisico = materia.stock_actual
    reserva = reservado(materia)
    libre = fisico-reserva
    bloqueado = vencido(materia)
    util = max(D(0),libre-bloqueado)
    entradas = list(recepciones(materia))
    transito = sum((d.cantidad for d in entradas),D(0))
    pos = libre+transito
    result = {'fisico':fisico,'reservado':reserva,'disponible':libre,'transito':transito,
        'vencido':bloqueado,'utilizable':util,
        'posicion':pos,'cantidad':D(0),'riesgo':'SIN_DATOS','advertencias':[], 'proyeccion':[],
        'fecha_agotamiento':None,'fecha_seguridad':None,'fecha_pedido':None,
        'fecha_rop':None,'explicacion':'No hay un pronóstico vigente. Entrene y genere un pronóstico.'}
    if bloqueado:
        result['advertencias'].append(f'{bloqueado} unidades vencidas: excluidas del stock utilizable para la proyección y compra.')
    pronostico = pronostico or materia.pronosticos.select_related('entrenamiento').first()
    if not pronostico:
        return result
    if pronostico.entrenamiento.obsoleto:
        result['advertencias'].append('El histórico fue corregido. Reentrene y genere otro pronóstico.')
        return result
    values = [v for v in pronostico.valores if v['fecha'] >= hoy.isoformat()]
    if not values or values[0]['fecha'] != hoy.isoformat():
        result['advertencias'].append('Pronóstico vencido; genere uno nuevo.')
        return result
    result.update({'modelo':pronostico.entrenamiento.modelo,'metricas':pronostico.entrenamiento.metricas,
                   'pronostico_id':pronostico.pk})
    for days in [7,15,30]:
        result[f'consumo_{days}'] = sum(v['consumo'] for v in values[:days]) if len(values)>=days else None
    if pronostico.entrenamiento.estado == 'DATOS_INSUFICIENTES':
        result['advertencias'].append('Datos históricos insuficientes para generar una predicción confiable. Baseline provisional.')
    if not oferta:
        result['advertencias'].append('Configure un proveedor activo para calcular la compra.')
        return result
    lt = ceil(estadisticas(oferta)['promedio'])
    horizon = materia.cobertura_dias
    if len(values) < max(lt+horizon,1):
        result['advertencias'].append(f'Se requieren al menos {lt+horizon} días de pronóstico.')
        return result
    serie,_ = preparar(materia)
    sigma = float(serie.std(ddof=0)) if len(serie) else 0.
    ss = seguridad(sigma,lt,materia.nivel_servicio)
    demanda_lt = sum((D(v['consumo']) for v in values[:lt]),D(0))
    rop = demanda_lt+ss
    objetivo = sum((D(v['consumo']) for v in values[:lt+horizon]),D(0))+ss
    # Late receipts do not fund the coverage target; still shown in total inventory position.
    limite = hoy+timedelta(days=lt+horizon)
    oportuno = sum((d.cantidad for d in entradas if hoy <= d.orden.fecha_estimada < limite),D(0))
    pos_cobertura = util+oportuno
    cantidad = redondear_compra(objetivo-pos_cobertura,oferta.moq,oferta.multiplo)
    scheduled = {}
    for detail in entradas:
        day = detail.orden.fecha_estimada.isoformat()
        if day < hoy.isoformat():
            result['advertencias'].append(f'{detail.orden}: entrega atrasada; no se supone recibida.')
        else:
            scheduled[day] = scheduled.get(day,D(0))+detail.cantidad
    stock = util
    agotamiento = hoy if stock <= 0 else None
    fecha_ss = hoy if stock <= ss else None
    fecha_rop = hoy if stock <= rop else None
    projection = []
    for value in values:
        day = date.fromisoformat(value['fecha'])
        entrada = scheduled.get(value['fecha'],D(0))
        stock = stock+entrada-D(value['consumo'])
        projection.append({'fecha':value['fecha'],'stock':float(stock),'consumo':value['consumo'],
                           'recepcion':float(entrada),'rop':float(rop),'seguridad':float(ss)})
        if agotamiento is None and stock <= 0:
            agotamiento = day
        if fecha_ss is None and stock <= ss:
            fecha_ss = day
        if fecha_rop is None and stock <= rop:
            fecha_rop = day
    # ROP already includes lead time: do not subtract it twice.
    deadline = max(hoy,fecha_ss-timedelta(days=lt)) if fecha_ss else fecha_rop
    pedido = min([d for d in [deadline,fecha_rop] if d],default=None)
    riesgo = 'CRITICO' if util <= ss or (agotamiento and agotamiento <= hoy+timedelta(days=lt)) else ('ATENCION' if pos <= rop or (pedido and pedido <= hoy+timedelta(days=7)) else 'ESTABLE')
    result.update({'oferta_id':oferta.pk,'proveedor':oferta.proveedor.nombre,'lead_time':lt,
        'precio':oferta.precio,'moq':oferta.moq,'multiplo':oferta.multiplo,
        'seguridad':ss,'rop':rop,'demanda_lt':demanda_lt,'objetivo':objetivo,'cantidad':cantidad,
        'posicion_cobertura':pos_cobertura,'sigma':sigma,'nivel_servicio':materia.nivel_servicio,
        'riesgo':riesgo,'fecha_agotamiento':agotamiento,'fecha_seguridad':fecha_ss,'fecha_rop':fecha_rop,
        'fecha_pedido':pedido,'fecha_recepcion':pedido+timedelta(days=lt) if pedido else None,
        'dias_restantes':(agotamiento-hoy).days if agotamiento else None,'proyeccion':projection,
        'modelo':pronostico.entrenamiento.modelo,
        'metricas':pronostico.entrenamiento.metricas,'pronostico_id':pronostico.pk})
    error = pronostico.entrenamiento.metricas.get('rmse')
    error_texto = f'{error:.4f}' if error is not None else 'no disponible'
    result['explicacion'] = (
        f'Se calcula una compra de {cantidad:.3f} {materia.unidad_medida} de {materia.nombre}. '
        f'Stock disponible: {libre:.3f}; utilizable después de vencidos: {util:.3f}; entradas dentro de cobertura: {oportuno:.3f}; '
        f'demanda durante {lt} días de entrega: {demanda_lt:.3f}; seguridad: {ss:.3f}; ROP: {rop:.3f}. '
        f'Objetivo S: {objetivo:.3f}. Q = max(0, S − posición dentro de cobertura), ajustada a MOQ '
        f'{oferta.moq} y múltiplo {oferta.multiplo}. Proveedor: {oferta.proveedor.nombre}, elegido por '
        f'menor tiempo de entrega y luego precio. Modelo: {pronostico.entrenamiento.modelo}; '
        f'RMSE de validación: {error_texto}. '
        f'Fecha de pedido: {pedido or "no alcanzada en el horizonte"}.')
    return result


@transaction.atomic
def sugerir(materia, usuario):
    materia = MateriaPrima.objects.select_for_update().get(pk=materia.pk)
    calculo = analizar(materia)
    if calculo['cantidad'] <= 0 or 'oferta_id' not in calculo:
        raise ValidationError('No hay una cantidad de compra calculable; revise los datos y el horizonte.')
    SugerenciaCompra.objects.filter(materia_prima=materia,estado='PENDIENTE').update(estado='OBSOLETA')
    result = SugerenciaCompra.objects.create(materia_prima=materia,oferta_id=calculo['oferta_id'],
        pronostico_id=calculo['pronostico_id'],cantidad=calculo['cantidad'],calculo=calculo,explicacion=calculo['explicacion'])
    auditar(usuario,'SUGERENCIA',result,nuevo=calculo)
    return result


@transaction.atomic
def decidir(pk, usuario, aprobar):
    suggestion = SugerenciaCompra.objects.select_for_update().get(pk=pk)
    materia = MateriaPrima.objects.select_for_update().get(pk=suggestion.materia_prima_id)
    if suggestion.estado != 'PENDIENTE':
        raise ValidationError('La sugerencia ya fue resuelta.')
    if aprobar:
        fresh = analizar(materia)
        # Si el usuario editó la cantidad manualmente, no comparamos ese campo con el cálculo fresco
        has_edit = bool(suggestion.cantidad_editada)
        keys = ['oferta_id','pronostico_id','disponible','utilizable','transito','rop','fecha_pedido','precio','moq','multiplo']
        if not has_edit:
            keys = ['cantidad'] + keys
        if any(str(fresh.get(k)) != str(suggestion.calculo.get(k)) for k in keys):
            raise ValidationError('El análisis cambió. Genere y revise una nueva sugerencia.')
        cantidad_orden = suggestion.cantidad_final
        order = OrdenCompra.objects.create(proveedor=suggestion.oferta.proveedor,sugerencia=suggestion,
            usuario=usuario,fecha_estimada=timezone.localdate()+timedelta(days=fresh['lead_time']))
        DetalleOrdenCompra.objects.create(orden=order,oferta=suggestion.oferta,cantidad=cantidad_orden,precio=suggestion.oferta.precio)
        suggestion.estado = 'APROBADA'
        auditar(usuario,'APROBAR_COMPRA',order,nuevo={'cantidad':cantidad_orden,'cantidad_editada':has_edit})
    else:
        suggestion.estado = 'RECHAZADA'
        auditar(usuario,'RECHAZAR_COMPRA',suggestion)
    suggestion.save(update_fields=['estado'])


@transaction.atomic
def transicionar(pk, estado, usuario):
    order = OrdenCompra.objects.select_for_update().get(pk=pk)
    next_states = {'APROBADA':'ENVIADA','ENVIADA':'CONFIRMADA','CONFIRMADA':'EN_TRANSITO','RECIBIDA':'CERRADA'}
    if next_states.get(order.estado) != estado:
        raise ValidationError('Transición no permitida.')
    before = order.estado
    order.estado = estado
    order.save(update_fields=['estado'])
    auditar(usuario,'ESTADO_COMPRA',order,{'estado':before},{'estado':estado})


@transaction.atomic
def recibir(pk, usuario, fecha=None, lotes=None):
    order = OrdenCompra.objects.select_for_update().get(pk=pk)
    if order.estado not in ['APROBADA','ENVIADA','CONFIRMADA','EN_TRANSITO']:
        raise ValidationError('Este pedido ya fue recibido o cerrado.')
    fecha = fecha or timezone.localdate()
    fecha_orden = order.fecha_pedido
    if not fecha_orden <= fecha <= timezone.localdate():
        raise ValidationError('Fecha real de recepción inválida.')
    for detail in order.detalles.select_related('oferta').order_by('oferta__materia_prima_id'):
        materia = MateriaPrima.objects.select_for_update().get(pk=detail.oferta.materia_prima_id)
        if materia.gestionar_lotes:
            lote = (lotes or {}).get(str(detail.pk),{})
            numero = lote.get('numero','').strip()
            vence = lote.get('vencimiento')
            if not numero or (vence and vence < fecha):
                raise ValidationError('Número o vencimiento del lote inválido.')
            LoteMateriaPrima.objects.create(materia_prima=materia,proveedor=order.proveedor,numero=numero,
                cantidad_inicial=detail.cantidad,cantidad_disponible=detail.cantidad,fecha_recepcion=fecha,
                fecha_vencimiento=vence,costo=detail.precio)
        materia.stock_actual += detail.cantidad
        materia.save(update_fields=['stock_actual','ultima_vez_actualizado'])
        MovimientoInventario.objects.create(tipo='ENTRADA',materia_prima=materia,cantidad=detail.cantidad,
            usuario=usuario,descripcion=f'Recepción {order}')
        LeadTimeReal.objects.create(detalle=detail,dias=(fecha-fecha_orden).days,fecha=fecha)
        detail.oferta.ultima_compra = fecha
        detail.oferta.save(update_fields=['ultima_compra'])
    order.fecha_recepcion = fecha
    order.estado = 'RECIBIDA'
    order.save(update_fields=['fecha_recepcion','estado'])
    auditar(usuario,'RECEPCION_COMPRA',order,nuevo={'fecha':fecha,'lead_time':(fecha-fecha_orden).days})
    return order


@transaction.atomic
def crear_compra_manual(materia_id, proveedor, cantidad, usuario, precio=None,
                        fecha_pedido=None, fecha_estimada=None, observacion=''):
    materia = MateriaPrima.objects.select_for_update().get(pk=materia_id)
    cantidad = D(cantidad)
    fecha_pedido = fecha_pedido or timezone.localdate()
    if cantidad <= 0 or fecha_pedido > timezone.localdate() or not proveedor.activo:
        raise ValidationError('Cantidad, proveedor o fecha de pedido inválidos.')
    oferta, _ = MateriaPrimaProveedor.objects.get_or_create(materia_prima=materia,proveedor=proveedor,
        defaults={'precio':materia.costo_unitario or 0,'lead_time_dias':proveedor.tiempo_entrega_dias})
    if not oferta.activo:
        raise ValidationError('La oferta de este proveedor está inactiva.')
    precio = D(precio) if precio is not None else oferta.precio
    if precio < 0:
        raise ValidationError('El precio no puede ser negativo.')
    fecha_estimada = fecha_estimada or fecha_pedido+timedelta(days=ceil(estadisticas(oferta)['promedio']))
    if fecha_estimada < fecha_pedido:
        raise ValidationError('La fecha estimada no puede ser anterior al pedido.')
    order = OrdenCompra.objects.create(proveedor=proveedor,usuario=usuario,fecha_pedido=fecha_pedido,
        fecha_estimada=fecha_estimada,observacion=observacion)
    DetalleOrdenCompra.objects.create(orden=order,oferta=oferta,cantidad=cantidad,precio=precio)
    auditar(usuario,'COMPRA_MANUAL_PENDIENTE',order,nuevo={'materia':materia.pk,'cantidad':cantidad,'fecha_pedido':fecha_pedido})
    return order
