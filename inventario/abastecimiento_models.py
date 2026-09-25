"""Entidades de aprovisionamiento que amplían los catálogos existentes."""
import uuid
from django.utils import timezone
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder


def quantity(default=0):
    return models.DecimalField(max_digits=20, decimal_places=5, default=default,
                               validators=[MinValueValidator(Decimal('0'))])


class MateriaPrimaProveedor(models.Model):
    materia_prima = models.ForeignKey('inventario.MateriaPrima', on_delete=models.PROTECT, related_name='ofertas')
    proveedor = models.ForeignKey('inventario.Proveedor', on_delete=models.PROTECT, related_name='ofertas')
    precio = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    lead_time_dias = models.PositiveIntegerField('tiempo de entrega estimado (días)', default=3, validators=[MaxValueValidator(180)])
    moq = quantity()
    multiplo = quantity(1)
    presentacion = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)
    ultima_compra = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['materia_prima', 'proveedor'], name='oferta_unica'),
                       models.CheckConstraint(condition=models.Q(multiplo__gt=0, moq__gte=0, precio__gte=0), name='oferta_valores_validos')]

    def __str__(self):
        return f'{self.materia_prima.nombre} / {self.proveedor.nombre}'


class ReservaInventario(models.Model):
    orden = models.ForeignKey('produccion.OrdenProduccion', on_delete=models.PROTECT, related_name='reservas')
    materia_prima = models.ForeignKey('inventario.MateriaPrima', on_delete=models.PROTECT, related_name='reservas')
    cantidad = quantity()
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['orden', 'materia_prima'], name='reserva_orden_insumo'),
                       models.CheckConstraint(condition=models.Q(cantidad__gt=0), name='reserva_positiva')]


class SugerenciaCompra(models.Model):
    materia_prima = models.ForeignKey('inventario.MateriaPrima', on_delete=models.PROTECT, related_name='sugerencias')
    oferta = models.ForeignKey(MateriaPrimaProveedor, on_delete=models.PROTECT)
    pronostico = models.ForeignKey('produccion.Pronostico', on_delete=models.PROTECT)
    cantidad = quantity()
    cantidad_editada = models.DecimalField(
        'cantidad editada por usuario',
        max_digits=20, decimal_places=5,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00001'))],
        help_text='Si se especifica, esta cantidad reemplaza la calculada al generar la orden.'
    )
    calculo = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    explicacion = models.TextField()
    estado = models.CharField(max_length=12, default='PENDIENTE', choices=[(x,x) for x in ['PENDIENTE','APROBADA','RECHAZADA','OBSOLETA']])
    fecha = models.DateTimeField(auto_now_add=True)

    @property
    def cantidad_final(self):
        """Retorna la cantidad editada si existe, sino la calculada."""
        return self.cantidad_editada if self.cantidad_editada else self.cantidad

    class Meta:
        constraints = [models.UniqueConstraint(fields=['materia_prima'], condition=models.Q(estado='PENDIENTE'), name='una_sugerencia_pendiente')]


class OrdenCompra(models.Model):
    codigo = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    proveedor = models.ForeignKey('inventario.Proveedor', on_delete=models.PROTECT)
    sugerencia = models.OneToOneField(SugerenciaCompra, on_delete=models.PROTECT, null=True, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_pedido = models.DateField('fecha del pedido', default=timezone.localdate)
    observacion = models.TextField(blank=True)
    fecha_estimada = models.DateField()
    fecha_recepcion = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=15, default='APROBADA', choices=[('APROBADA','Pendiente de llegada'),('ENVIADA','Enviada'),('CONFIRMADA','Confirmada'),('EN_TRANSITO','En tránsito'),('RECIBIDA','Recibida'),('CERRADA','Cerrada')])

    def __str__(self):
        return f'OC-{str(self.codigo)[:8]}'


class DetalleOrdenCompra(models.Model):
    orden = models.ForeignKey(OrdenCompra, on_delete=models.PROTECT, related_name='detalles')
    oferta = models.ForeignKey(MateriaPrimaProveedor, on_delete=models.PROTECT)
    cantidad = quantity()
    precio = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(cantidad__gt=0, precio__gte=0), name='detalle_compra_valido')]


class LeadTimeReal(models.Model):
    detalle = models.OneToOneField(DetalleOrdenCompra, on_delete=models.PROTECT, related_name='entrega')
    dias = models.PositiveIntegerField()
    fecha = models.DateField()


class LoteMateriaPrima(models.Model):
    materia_prima = models.ForeignKey('inventario.MateriaPrima', on_delete=models.PROTECT, related_name='lotes')
    proveedor = models.ForeignKey('inventario.Proveedor', on_delete=models.PROTECT, null=True, blank=True)
    numero = models.CharField(max_length=100)
    cantidad_inicial = quantity()
    cantidad_disponible = quantity()
    fecha_recepcion = models.DateField()
    fecha_vencimiento = models.DateField(null=True, blank=True)
    costo = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    class Meta:
        constraints = [models.UniqueConstraint(fields=['materia_prima','numero'], name='lote_unico'),
                       models.CheckConstraint(condition=models.Q(cantidad_disponible__gte=0, cantidad_disponible__lte=models.F('cantidad_inicial')), name='lote_saldo_valido')]


class ConsumoLote(models.Model):
    consumo = models.ForeignKey('produccion.ConsumoMateriaPrima', on_delete=models.PROTECT, related_name='lotes')
    lote = models.ForeignKey(LoteMateriaPrima, on_delete=models.PROTECT)
    cantidad = quantity()


class Auditoria(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=80)
    fecha = models.DateTimeField(auto_now_add=True)
    entidad = models.CharField(max_length=120)
    anterior = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    nuevo = models.JSONField(default=dict, encoder=DjangoJSONEncoder)

    class Meta:
        ordering = ['-fecha']
