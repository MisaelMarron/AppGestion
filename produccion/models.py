from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class FormulaProducto(models.Model):
    """Fórmula de producción que define la receta de un producto terminado."""

    producto_terminado = models.ForeignKey(
        'inventario.ProductoTerminado',
        on_delete=models.PROTECT,
        related_name='formulas',
        verbose_name='producto terminado',
    )
    nombre = models.CharField('nombre', max_length=200)
    cantidad_resultante = models.DecimalField(
        'cantidad resultante',
        max_digits=12,
        decimal_places=5,
    )
    activo = models.BooleanField('activo', default=True)
    fecha_creacion = models.DateTimeField('fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'fórmula de producto'
        verbose_name_plural = 'fórmulas de producto'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} → {self.producto_terminado.nombre}'


class DetalleFormula(models.Model):
    """Detalle de una fórmula: materia prima y cantidad requerida."""

    formula = models.ForeignKey(
        FormulaProducto,
        on_delete=models.PROTECT,
        related_name='detalles',
        verbose_name='fórmula',
    )
    materia_prima = models.ForeignKey(
        'inventario.MateriaPrima',
        on_delete=models.PROTECT,
        related_name='detalles_formula',
        verbose_name='materia prima',
    )
    cantidad_requerida = models.DecimalField(
        'cantidad requerida',
        max_digits=12,
        decimal_places=5,
    )

    class Meta:
        verbose_name = 'detalle de fórmula'
        verbose_name_plural = 'detalles de fórmula'

    def __str__(self):
        return f'{self.materia_prima.nombre} × {self.cantidad_requerida}'


class DetalleProducto(models.Model):
    """Versión simplificada de la receta usando los nombres que ya usaste antes."""

    codigoMateriaPrima = models.ForeignKey(
        'inventario.MateriaPrima',
        on_delete=models.PROTECT,
        related_name='detalle_productos',
        verbose_name='materia prima',
    )
    codigoProductoTerminado = models.ForeignKey(
        'inventario.ProductoTerminado',
        on_delete=models.PROTECT,
        related_name='detalles_producto',
        verbose_name='producto terminado',
    )
    cantidad = models.DecimalField('cantidad', max_digits=20, decimal_places=5)

    class Meta:
        unique_together = ('codigoMateriaPrima', 'codigoProductoTerminado')
        verbose_name = 'detalle de producto'
        verbose_name_plural = 'detalles de producto'

    def clean(self):
        super().clean()
        if self.cantidad <= 0:
            raise ValidationError({'cantidad': 'La cantidad debe ser mayor que cero'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.codigoProductoTerminado.nombre} usa {self.cantidad} de {self.codigoMateriaPrima.nombre}'


class Produccion(models.Model):
    """Registro de producción con consumo automático de materias primas."""

    producto = models.ForeignKey(
        'inventario.ProductoTerminado',
        on_delete=models.PROTECT,
        related_name='producciones',
        verbose_name='producto',
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='producciones_ejecutadas')
    clave_operacion = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    anulada = models.BooleanField(default=False, db_index=True)
    fecha_anulacion = models.DateTimeField(null=True, blank=True)
    ejecutada = models.BooleanField(default=False)
    sintetica = models.BooleanField(default=False)
    receta_snapshot = models.JSONField(default=list, blank=True)
    orden = models.OneToOneField('OrdenProduccion', on_delete=models.PROTECT, null=True, blank=True, related_name='ejecucion')
    cantidad_producida = models.DecimalField('cantidad producida (bulk kg)', max_digits=20, decimal_places=5, default=0)
    unidades_producidas = models.PositiveIntegerField('unidades producidas', default=0)
    fecha = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'producción'
        verbose_name_plural = 'producciones'
        ordering = ['-fecha']

    def clean(self):
        super().clean()
        if self.cantidad_producida <= 0:
            raise ValidationError({'cantidad_producida': 'La cantidad producida debe ser mayor que cero'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'Producción de {self.cantidad_producida} de {self.producto.nombre}'

    def consumir_materiales(self, usuario=None):
        from .services.operaciones import ejecutar_produccion
        return ejecutar_produccion(self.pk, usuario)


class ConsumoMateriaPrima(models.Model):
    """Consumo de materias primas asociado a una producción."""

    produccion = models.ForeignKey(
        Produccion,
        on_delete=models.PROTECT,
        related_name='consumos',
        verbose_name='producción',
    )
    materia_prima = models.ForeignKey(
        'inventario.MateriaPrima',
        on_delete=models.PROTECT,
        related_name='consumos',
        verbose_name='materia prima',
    )
    excluido_entrenamiento = models.BooleanField(default=False)
    motivo_exclusion = models.TextField(blank=True)
    cantidad_usada = models.DecimalField('cantidad usada', max_digits=20, decimal_places=5)

    class Meta:
        verbose_name = 'consumo de materia prima'
        verbose_name_plural = 'consumos de materia prima'

    def __str__(self):
        return f'{self.cantidad_usada} de {self.materia_prima.nombre} en {self.produccion}'


class OrdenProduccion(models.Model):
    """Orden de producción que registra la fabricación de un producto."""

    producto_terminado = models.ForeignKey(
        'inventario.ProductoTerminado',
        on_delete=models.PROTECT,
        related_name='ordenes_produccion',
        verbose_name='producto terminado',
    )
    formula = models.ForeignKey(
        FormulaProducto,
        on_delete=models.PROTECT,
        related_name='ordenes',
        null=True, blank=True,
        verbose_name='fórmula',
    )
    cantidad_producida = models.DecimalField(
        'cantidad producida',
        max_digits=12,
        decimal_places=5,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ordenes_produccion',
        verbose_name='usuario',
    )
    estado = models.CharField(max_length=15, default='PLANIFICADA', choices=[(x,x) for x in ['PLANIFICADA','RESERVADA','COMPLETADA','CANCELADA']])
    fecha_planificada = models.DateField(null=True, blank=True)
    receta_snapshot = models.JSONField(default=list, blank=True)
    observacion = models.TextField('observación', blank=True)
    fecha = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'orden de producción'
        verbose_name_plural = 'órdenes de producción'
        ordering = ['-fecha']

    def __str__(self):
        return f'OP-{self.pk} · {self.producto_terminado.nombre} × {self.cantidad_producida}'

    def producir(self):
        from .services.operaciones import ejecutar_orden
        return ejecutar_orden(self.pk, self.usuario)

from .forecast_models import Entrenamiento, Pronostico, EvaluacionPronostico
