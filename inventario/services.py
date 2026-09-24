from datetime import timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from .models import (MateriaPrima, MovimientoInventario, ReservaInventario,
                     LoteMateriaPrima, Auditoria)

ZERO = Decimal('0')


def auditar(usuario, accion, objeto, anterior=None, nuevo=None):
    return Auditoria.objects.create(usuario=usuario, accion=accion,
        entidad=f'{objeto._meta.label}:{objeto.pk}', anterior=anterior or {}, nuevo=nuevo or {})


def reservado(materia, excluir_orden=None):
    qs = ReservaInventario.objects.filter(materia_prima=materia, activa=True)
    if excluir_orden:
        qs = qs.exclude(orden_id=excluir_orden)
    return qs.aggregate(n=Sum('cantidad'))['n'] or ZERO


def disponible(materia, excluir_orden=None):
    return materia.stock_actual - reservado(materia, excluir_orden)


def vencido(materia):
    if not materia.gestionar_lotes:
        return ZERO
    return materia.lotes.filter(fecha_vencimiento__lt=timezone.localdate()).aggregate(n=Sum('cantidad_disponible'))['n'] or ZERO


def utilizable(materia, excluir_orden=None):
    return max(ZERO, disponible(materia, excluir_orden)-vencido(materia))


def recepciones(materia):
    from .models import DetalleOrdenCompra
    return DetalleOrdenCompra.objects.filter(oferta__materia_prima=materia,
        orden__estado__in=['APROBADA','ENVIADA','CONFIRMADA','EN_TRANSITO']).select_related('orden')


def posicion(materia):
    return disponible(materia) + sum((d.cantidad for d in recepciones(materia)), ZERO)


def consumir_lotes(materia, cantidad, consumo=None):
    if not materia.gestionar_lotes:
        return
    from .models import ConsumoLote
    restante = cantidad
    lotes = LoteMateriaPrima.objects.select_for_update().filter(materia_prima=materia,
        cantidad_disponible__gt=0).filter(
        models_q_vigentes()).order_by(F('fecha_vencimiento').asc(nulls_last=True), 'fecha_recepcion', 'pk')
    for lote in lotes:
        usado = min(restante, lote.cantidad_disponible)
        lote.cantidad_disponible -= usado
        lote.save(update_fields=['cantidad_disponible'])
        if consumo:
            ConsumoLote.objects.create(consumo=consumo, lote=lote, cantidad=usado)
        restante -= usado
        if restante == 0:
            break
    if restante > 0:
        raise ValidationError(f'Lotes vigentes insuficientes de {materia.nombre}.')


def models_q_vigentes():
    from django.db.models import Q
    return Q(fecha_vencimiento__isnull=True) | Q(fecha_vencimiento__gte=timezone.localdate())


@transaction.atomic
def ajustar_stock(pk, cantidad, tipo, usuario, descripcion='', numero_lote='', vencimiento=None):
    materia = MateriaPrima.objects.select_for_update().get(pk=pk)
    cantidad = Decimal(cantidad)
    if cantidad <= 0 or tipo not in ['ENTRADA','SALIDA']:
        raise ValidationError('Movimiento inválido.')
    antes = materia.stock_actual
    if tipo == 'SALIDA':
        if disponible(materia) < cantidad:
            raise ValidationError('Stock disponible insuficiente; existen reservas o falta inventario.')
        consumir_lotes(materia, cantidad)
        materia.stock_actual -= cantidad
    else:
        if materia.gestionar_lotes:
            if not numero_lote:
                raise ValidationError('Debe indicar el número de lote para esta entrada.')
            if vencimiento and vencimiento < timezone.localdate():
                raise ValidationError('El lote no puede ingresar vencido.')
            LoteMateriaPrima.objects.create(materia_prima=materia, numero=numero_lote,
                cantidad_inicial=cantidad, cantidad_disponible=cantidad,
                fecha_recepcion=timezone.localdate(), fecha_vencimiento=vencimiento,
                costo=materia.costo_unitario or ZERO)
        materia.stock_actual += cantidad
    materia.save(update_fields=['stock_actual','ultima_vez_actualizado'])
    MovimientoInventario.objects.create(materia_prima=materia, tipo=tipo, cantidad=cantidad,
                                        usuario=usuario, descripcion=descripcion)
    auditar(usuario,'AJUSTE_STOCK',materia,{'stock':antes},{'stock':materia.stock_actual,'motivo':descripcion})
    return materia
