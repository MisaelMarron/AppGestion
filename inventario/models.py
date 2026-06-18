from django.db import models
from django.conf import settings


class Proveedor(models.Model):
    """Modelo que representa un proveedor de materias primas."""

    nombre = models.CharField('nombre', max_length=200)
    ruc = models.CharField('RUC', max_length=20, blank=True)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    correo = models.EmailField('correo electrónico', blank=True)
    direccion = models.CharField('dirección', max_length=300, blank=True)
    activo = models.BooleanField('activo', default=True)

    class Meta:
        verbose_name = 'proveedor'
        verbose_name_plural = 'proveedores'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class MateriaPrima(models.Model):
    """Modelo que representa una materia prima en inventario."""

    class UnidadMedida(models.TextChoices):
        KG = 'kg', 'Kilogramos'
        G = 'g', 'Gramos'
        L = 'l', 'Litros'
        ML = 'ml', 'Mililitros'
        UNIDAD = 'unidad', 'Unidad'

    nombre = models.CharField('nombre', max_length=200)
    descripcion = models.TextField('descripción', blank=True)
    unidad_medida = models.CharField(
        'unidad de medida',
        max_length=10,
        choices=UnidadMedida.choices,
        default=UnidadMedida.UNIDAD,
    )
    stock_actual = models.DecimalField('stock actual', max_digits=12, decimal_places=2, default=0)
    stock_minimo = models.DecimalField('stock mínimo', max_digits=12, decimal_places=2, default=0)
    costo_unitario = models.DecimalField(
        'costo unitario',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='materias_primas',
        verbose_name='proveedor',
    )
    activo = models.BooleanField('activo', default=True)
    fecha_creacion = models.DateTimeField('fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'materia prima'
        verbose_name_plural = 'materias primas'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.stock_actual} {self.unidad_medida})'

    def necesita_reposicion(self):
        """Devuelve True cuando stock_actual <= stock_minimo."""
        return self.stock_actual <= self.stock_minimo


class ProductoTerminado(models.Model):
    """Modelo que representa un producto terminado."""

    class UnidadMedida(models.TextChoices):
        KG = 'kg', 'Kilogramos'
        G = 'g', 'Gramos'
        L = 'l', 'Litros'
        ML = 'ml', 'Mililitros'
        UNIDAD = 'unidad', 'Unidad'

    nombre = models.CharField('nombre', max_length=200)
    descripcion = models.TextField('descripción', blank=True)
    unidad_medida = models.CharField(
        'unidad de medida',
        max_length=10,
        choices=UnidadMedida.choices,
        default=UnidadMedida.UNIDAD,
    )
    stock_actual = models.DecimalField('stock actual', max_digits=12, decimal_places=2, default=0)
    activo = models.BooleanField('activo', default=True)
    fecha_creacion = models.DateTimeField('fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'producto terminado'
        verbose_name_plural = 'productos terminados'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.stock_actual} {self.unidad_medida})'


class MovimientoInventario(models.Model):
    """Modelo que registra los movimientos de inventario."""

    class TipoMovimiento(models.TextChoices):
        ENTRADA = 'ENTRADA', 'Entrada'
        SALIDA = 'SALIDA', 'Salida'
        AJUSTE = 'AJUSTE', 'Ajuste'
        PRODUCCION = 'PRODUCCION', 'Producción'

    tipo = models.CharField(
        'tipo',
        max_length=15,
        choices=TipoMovimiento.choices,
    )
    materia_prima = models.ForeignKey(
        MateriaPrima,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos',
        verbose_name='materia prima',
    )
    producto_terminado = models.ForeignKey(
        ProductoTerminado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos',
        verbose_name='producto terminado',
    )
    cantidad = models.DecimalField('cantidad', max_digits=12, decimal_places=2)
    descripcion = models.TextField('descripción', blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='movimientos',
        verbose_name='usuario',
    )
    fecha = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'movimiento de inventario'
        verbose_name_plural = 'movimientos de inventario'
        ordering = ['-fecha']

    def __str__(self):
        item = self.materia_prima or self.producto_terminado or '—'
        return f'{self.get_tipo_display()} · {item} · {self.cantidad}'
