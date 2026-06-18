from django.db import models
from django.conf import settings


class FormulaProducto(models.Model):
    """Fórmula de producción que define la receta de un producto terminado."""

    producto_terminado = models.ForeignKey(
        'inventario.ProductoTerminado',
        on_delete=models.CASCADE,
        related_name='formulas',
        verbose_name='producto terminado',
    )
    nombre = models.CharField('nombre', max_length=200)
    cantidad_resultante = models.DecimalField(
        'cantidad resultante',
        max_digits=12,
        decimal_places=2,
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
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='fórmula',
    )
    materia_prima = models.ForeignKey(
        'inventario.MateriaPrima',
        on_delete=models.CASCADE,
        related_name='detalles_formula',
        verbose_name='materia prima',
    )
    cantidad_requerida = models.DecimalField(
        'cantidad requerida',
        max_digits=12,
        decimal_places=2,
    )

    class Meta:
        verbose_name = 'detalle de fórmula'
        verbose_name_plural = 'detalles de fórmula'

    def __str__(self):
        return f'{self.materia_prima.nombre} × {self.cantidad_requerida}'


class OrdenProduccion(models.Model):
    """Orden de producción que registra la fabricación de un producto."""

    producto_terminado = models.ForeignKey(
        'inventario.ProductoTerminado',
        on_delete=models.CASCADE,
        related_name='ordenes_produccion',
        verbose_name='producto terminado',
    )
    formula = models.ForeignKey(
        FormulaProducto,
        on_delete=models.CASCADE,
        related_name='ordenes',
        verbose_name='fórmula',
    )
    cantidad_producida = models.DecimalField(
        'cantidad producida',
        max_digits=12,
        decimal_places=2,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ordenes_produccion',
        verbose_name='usuario',
    )
    observacion = models.TextField('observación', blank=True)
    fecha = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'orden de producción'
        verbose_name_plural = 'órdenes de producción'
        ordering = ['-fecha']

    def __str__(self):
        return f'OP-{self.pk} · {self.producto_terminado.nombre} × {self.cantidad_producida}'

    def producir(self):
        """
        Ejecuta la producción según la fórmula asociada.

        TODO — Siguiente avance:
        1. Recorrer cada DetalleFormula de self.formula.
        2. Calcular la cantidad proporcional de cada materia prima:
           cantidad_necesaria = detalle.cantidad_requerida
                                * (self.cantidad_producida / self.formula.cantidad_resultante)
        3. Verificar que el stock_actual de cada materia prima sea suficiente.
        4. Descontar stock_actual de cada materia prima utilizada.
        5. Registrar un MovimientoInventario de tipo PRODUCCION (SALIDA) por cada
           materia prima consumida.
        6. Aumentar el stock_actual del producto terminado en self.cantidad_producida.
        7. Registrar un MovimientoInventario de tipo PRODUCCION (ENTRADA) para el
           producto terminado.
        8. Manejar errores si el stock es insuficiente (lanzar excepción descriptiva).
        """
        pass
