from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import transaction
from inventario.models import MateriaPrima, ProductoTerminado, MovimientoInventario, ReservaInventario
from inventario.services import disponible, utilizable, consumir_lotes, auditar
from produccion.models import Produccion, ConsumoMateriaPrima, OrdenProduccion, DetalleProducto


def receta(producto, cantidad, formula=None):
    if cantidad <= 0:
        raise ValidationError('La cantidad debe ser positiva.')
    if formula:
        if formula.producto_terminado_id != producto.pk or formula.cantidad_resultante <= 0 or not formula.activo:
            raise ValidationError('Fórmula inválida para el producto.')
        detalles = [(d.materia_prima_id, d.cantidad_requerida / formula.cantidad_resultante)
                    for d in formula.detalles.all()]
    else:
        detalles = list(DetalleProducto.objects.filter(codigoProductoTerminado=producto)
                        .values_list('codigoMateriaPrima_id','cantidad'))
    if not detalles or any(c <= 0 for _, c in detalles):
        raise ValidationError('La receta debe contener insumos con cantidades positivas.')
    cantidades = {}
    for pk, c in detalles:
        cantidades[pk] = cantidades.get(pk, Decimal(0)) + c * cantidad
    return [{'materia_id': pk, 'cantidad': str(c.quantize(Decimal('.00001'), rounding=ROUND_HALF_UP))}
            for pk,c in sorted(cantidades.items())]


@transaction.atomic
def ejecutar_produccion(pk, usuario=None):
    produccion = Produccion.objects.select_for_update().get(pk=pk)
    if produccion.anulada or produccion.ejecutada or produccion.consumos.exists():
        raise ValidationError('Esta producción ya fue ejecutada.')
    producto = ProductoTerminado.objects.select_for_update().get(pk=produccion.producto_id)
    lineas = produccion.receta_snapshot or receta(producto, produccion.cantidad_producida)
    for linea in sorted(lineas, key=lambda x: x['materia_id']):
        materia = MateriaPrima.objects.select_for_update().get(pk=linea['materia_id'])
        cantidad = Decimal(linea['cantidad'])
        if cantidad <= 0 or not materia.activo or utilizable(materia, produccion.orden_id) < cantidad:
            raise ValidationError(f'Stock disponible insuficiente de {materia.nombre}.')
        consumo = ConsumoMateriaPrima.objects.create(produccion=produccion, materia_prima=materia, cantidad_usada=cantidad)
        consumir_lotes(materia,cantidad,consumo)
        materia.stock_actual -= cantidad
        materia.save(update_fields=['stock_actual','ultima_vez_actualizado'])
        MovimientoInventario.objects.create(tipo='PRODUCCION', materia_prima=materia,
            cantidad=-cantidad, usuario=usuario, descripcion=f'Producción {produccion.pk}')
    producto.stock_actual += produccion.cantidad_producida
    producto.save(update_fields=['stock_actual'])
    MovimientoInventario.objects.create(tipo='PRODUCCION', producto_terminado=producto,
        cantidad=produccion.cantidad_producida, usuario=usuario, descripcion=f'Producción {produccion.pk}')
    produccion.usuario = usuario
    produccion.ejecutada = True
    produccion.receta_snapshot = lineas
    produccion.save(update_fields=['ejecutada','receta_snapshot','usuario'])
    auditar(usuario,'PRODUCCION',produccion,nuevo={'receta':lineas})
    return produccion


@transaction.atomic
def reservar_orden(pk, usuario):
    orden = OrdenProduccion.objects.select_for_update().get(pk=pk)
    if orden.estado != 'PLANIFICADA':
        raise ValidationError('La orden no está planificada.')
    lineas = receta(orden.producto_terminado, orden.cantidad_producida, orden.formula)
    for linea in lineas:
        materia = MateriaPrima.objects.select_for_update().get(pk=linea['materia_id'])
        cantidad = Decimal(linea['cantidad'])
        if utilizable(materia) < cantidad:
            raise ValidationError(f'Stock insuficiente para reservar {materia.nombre}.')
        ReservaInventario.objects.create(orden=orden,materia_prima=materia,cantidad=cantidad)
    orden.estado = 'RESERVADA'
    orden.receta_snapshot = lineas
    orden.save(update_fields=['estado','receta_snapshot'])
    auditar(usuario,'RESERVA',orden,nuevo={'receta':lineas})
    return orden


@transaction.atomic
def ejecutar_orden(pk, usuario):
    orden = OrdenProduccion.objects.select_for_update().get(pk=pk)
    if orden.estado not in ['PLANIFICADA','RESERVADA']:
        raise ValidationError('La orden ya fue ejecutada o cancelada.')
    lineas = orden.receta_snapshot or receta(orden.producto_terminado,orden.cantidad_producida,orden.formula)
    produccion = Produccion.objects.create(producto=orden.producto_terminado,
        cantidad_producida=orden.cantidad_producida, orden=orden, receta_snapshot=lineas)
    ejecutar_produccion(produccion.pk,usuario)
    orden.reservas.update(activa=False)
    orden.estado = 'COMPLETADA'
    orden.save(update_fields=['estado'])
    return produccion


@transaction.atomic
def cancelar_orden(pk, usuario):
    orden = OrdenProduccion.objects.select_for_update().get(pk=pk)
    if orden.estado not in ['PLANIFICADA','RESERVADA']:
        raise ValidationError('No se puede cancelar esta orden.')
    orden.reservas.update(activa=False)
    orden.estado = 'CANCELADA'
    orden.save(update_fields=['estado'])
    auditar(usuario,'CANCELAR_RESERVA',orden)


@transaction.atomic
def corregir_produccion(pk, usuario, cantidad=None, motivo='', eliminar=False):
    """Reversa contable o corrección proporcional usando el consumo original.

    Mantiene IDs e historial auditado. Nunca usa una receta editada después.
    """
    from inventario.models import LoteMateriaPrima
    from django.utils import timezone
    p = Produccion.objects.select_for_update().get(pk=pk)
    if p.anulada or not p.ejecutada:
        raise ValidationError('La producción ya fue eliminada o no está ejecutada.')
    if not motivo.strip():
        raise ValidationError('Indique el motivo de la corrección.')
    nueva = Decimal(0) if eliminar else Decimal(cantidad)
    if not nueva.is_finite() or (not eliminar and nueva <= 0):
        raise ValidationError('La cantidad debe ser positiva.')
    anterior = p.cantidad_producida
    producto = ProductoTerminado.objects.select_for_update().get(pk=p.producto_id)
    delta_producto = nueva-anterior
    if producto.stock_actual+delta_producto < 0:
        raise ValidationError('No hay suficiente stock del producto terminado para revertir esta cantidad. Parte de la producción ya salió del almacén.')
    consumos = list(p.consumos.select_for_update().order_by('materia_prima_id','pk'))
    if not consumos:
        raise ValidationError('No hay consumos originales para efectuar una reversión verificable.')
    antes = {'cantidad':str(anterior),'consumos':[{'id':c.pk,'cantidad':str(c.cantidad_usada)} for c in consumos]}
    snapshot = []
    for c in consumos:
        materia = MateriaPrima.objects.select_for_update().get(pk=c.materia_prima_id)
        objetivo = (c.cantidad_usada*nueva/anterior).quantize(Decimal('.00001'),rounding=ROUND_HALF_UP)
        delta = objetivo-c.cantidad_usada
        if delta > 0:
            if utilizable(materia) < delta:
                raise ValidationError(f'Stock utilizable insuficiente de {materia.nombre}.')
            consumir_lotes(materia,delta,c)
        elif delta < 0:
            restante = -delta
            for allocation in c.lotes.select_for_update().order_by('-pk'):
                restaurar = min(restante,allocation.cantidad)
                lote = LoteMateriaPrima.objects.select_for_update().get(pk=allocation.lote_id)
                lote.cantidad_disponible += restaurar
                lote.save(update_fields=['cantidad_disponible'])
                allocation.cantidad -= restaurar
                if allocation.cantidad:
                    allocation.save(update_fields=['cantidad'])
                else:
                    allocation.delete()
                restante -= restaurar
                if restante == 0:
                    break
            if materia.gestionar_lotes and restante:
                raise ValidationError(f'El consumo antiguo de {materia.nombre} no tiene trazabilidad completa de lotes. Revise sus lotes antes de revertirlo.')
        materia.stock_actual -= delta
        materia.save(update_fields=['stock_actual','ultima_vez_actualizado'])
        if delta:
            MovimientoInventario.objects.create(tipo='AJUSTE',materia_prima=materia,cantidad=-delta,
                usuario=usuario,descripcion=f'{"Eliminación" if eliminar else "Corrección"} producción {p.pk}: {motivo}')
        if not eliminar:
            c.cantidad_usada = objetivo
            c.save(update_fields=['cantidad_usada'])
        snapshot.append({'materia_id':materia.pk,'cantidad':str(objetivo)})
    producto.stock_actual += delta_producto
    producto.save(update_fields=['stock_actual'])
    MovimientoInventario.objects.create(tipo='AJUSTE',producto_terminado=producto,cantidad=delta_producto,
        usuario=usuario,descripcion=f'{"Eliminación" if eliminar else "Corrección"} producción {p.pk}: {motivo}')
    if eliminar:
        p.anulada = True
        p.fecha_anulacion = timezone.now()
    else:
        p.cantidad_producida = nueva
        p.receta_snapshot = snapshot
    p.save()
    if p.orden_id:
        orden = OrdenProduccion.objects.select_for_update().get(pk=p.orden_id)
        orden.estado = 'CANCELADA' if eliminar else 'COMPLETADA'
        if not eliminar:
            orden.cantidad_producida = nueva
            orden.receta_snapshot = snapshot
        orden.save()
    # Previously fitted artifacts remain as history, but cannot be used as current evidence.
    from produccion.models import Entrenamiento
    ids = [c.materia_prima_id for c in consumos]
    Entrenamiento.objects.filter(materia_prima_id__in=ids).update(obsoleto=True)
    from inventario.models import SugerenciaCompra
    SugerenciaCompra.objects.filter(materia_prima_id__in=ids,estado='PENDIENTE').update(estado='OBSOLETA')
    auditar(usuario,'ELIMINAR_PRODUCCION' if eliminar else 'EDITAR_PRODUCCION',p,antes,
            {'cantidad':str(nueva),'motivo':motivo,'anulada':p.anulada})
    return p
