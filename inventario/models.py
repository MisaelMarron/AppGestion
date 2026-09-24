from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Proveedor(models.Model):
    """Modelo que representa un proveedor de materias primas."""

    nombre = models.CharField('nombre', max_length=200)
    ruc = models.CharField('RUC', max_length=20, blank=True)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    whatsapp = models.CharField(
        'WhatsApp',
        max_length=20,
        blank=True,
        help_text='Número con código de país sin + ni espacios. Ej: 51987654321',
    )
    correo = models.EmailField('correo electrónico', blank=True)
    direccion = models.CharField('dirección', max_length=300, blank=True)
    tiempo_entrega_dias = models.PositiveIntegerField(
        'tiempo de entrega (días)',
        default=3,
        help_text='Días que tarda el proveedor en entregar un pedido.',
    )
    activo = models.BooleanField('activo', default=True)

    class Meta:
        verbose_name = 'proveedor'
        verbose_name_plural = 'proveedores'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def whatsapp_link(self):
        """Genera el link de WhatsApp (wa.me) si tiene número configurado."""
        if self.whatsapp:
            numero = self.whatsapp.replace('+', '').replace(' ', '').replace('-', '')
            return f'https://wa.me/{numero}'
        return None


class MateriaPrima(models.Model):
    """Modelo que representa una materia prima en inventario."""

    class UnidadMedida(models.TextChoices):
        KG = 'kg', 'Kilogramos'
        G = 'g', 'Gramos'
        L = 'l', 'Litros'
        ML = 'ml', 'Mililitros'
        UNIDAD = 'unidad', 'Unidad'

    codigo = models.CharField('código', max_length=20, unique=True, blank=True)
    nombre = models.CharField('nombre', max_length=200)
    descripcion = models.TextField('descripción', blank=True)
    unidad_medida = models.CharField(
        'unidad de medida',
        max_length=10,
        choices=UnidadMedida.choices,
        default=UnidadMedida.UNIDAD,
    )
    stock_actual = models.DecimalField('stock actual', max_digits=12, decimal_places=5, default=0)
    nivel_servicio = models.DecimalField(max_digits=4, decimal_places=3, default='0.950', choices=[(Decimal('0.900'), '90 %'), (Decimal('0.950'), '95 %'), (Decimal('0.975'), '97.5 %'), (Decimal('0.990'), '99 %')])
    cobertura_dias = models.PositiveIntegerField(default=30)
    gestionar_lotes = models.BooleanField(default=False)
    proveedores = models.ManyToManyField(Proveedor, through='MateriaPrimaProveedor', related_name='insumos')
    stock_minimo = models.DecimalField('stock mínimo', max_digits=12, decimal_places=5, default=0)
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
    ultima_vez_actualizado = models.DateTimeField('última vez actualizado', auto_now=True)

    class Meta:
        verbose_name = 'materia prima'
        verbose_name_plural = 'materias primas'
        ordering = ['nombre']
        constraints = [models.CheckConstraint(condition=models.Q(stock_actual__gte=0), name='%(class)s_stock_no_negativo')]

    def __str__(self):
        return f'{self.nombre} ({self.stock_actual} {self.unidad_medida})'

    def clean(self):
        super().clean()
        if self.stock_actual < 0:
            raise ValidationError({'stock_actual': 'La cantidad debe ser positiva'})
        if self.stock_minimo < 0:
            raise ValidationError({'stock_minimo': 'El stock mínimo no puede ser negativo'})
        if not self.codigo:
            self.codigo = self.nombre.strip().lower().replace(' ', '-')[:20]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def stock_reservado(self):
        from .services import reservado
        return reservado(self)

    @property
    def stock_disponible(self):
        return self.stock_actual - self.stock_reservado

    @property
    def posicion_inventario(self):
        from .services import posicion
        return posicion(self)

    @property
    def cantidad(self):
        return self.stock_actual

    @cantidad.setter
    def cantidad(self, value):
        self.stock_actual = value

    @property
    def unidad(self):
        return self.unidad_medida

    @unidad.setter
    def unidad(self, value):
        self.unidad_medida = value

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

    codigo = models.CharField('código', max_length=20, unique=True, blank=True)
    nombre = models.CharField('nombre', max_length=200)
    descripcion = models.TextField('descripción', blank=True)
    unidad_medida = models.CharField(
        'unidad de medida',
        max_length=10,
        choices=UnidadMedida.choices,
        default=UnidadMedida.UNIDAD,
    )
    stock_actual = models.DecimalField('stock actual', max_digits=12, decimal_places=5, default=0)
    precio = models.DecimalField('precio', max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField('activo', default=True)
    fecha_creacion = models.DateTimeField('fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'producto terminado'
        verbose_name_plural = 'productos terminados'
        ordering = ['nombre']
        constraints = [models.CheckConstraint(condition=models.Q(stock_actual__gte=0), name='%(class)s_stock_no_negativo')]

    def __str__(self):
        return f'{self.nombre} ({self.stock_actual} {self.unidad_medida})'

    def clean(self):
        super().clean()
        if self.stock_actual < 0:
            raise ValidationError({'stock_actual': 'El stock no puede ser negativo'})
        if self.precio < 0:
            raise ValidationError({'precio': 'El precio no puede ser negativo'})
        if not self.codigo:
            self.codigo = self.nombre.strip().lower().replace(' ', '-')[:20]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


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
    cantidad = models.DecimalField('cantidad', max_digits=20, decimal_places=5)
    descripcion = models.TextField('descripción', blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
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

from .abastecimiento_models import (MateriaPrimaProveedor, ReservaInventario, SugerenciaCompra, OrdenCompra, DetalleOrdenCompra, LeadTimeReal, LoteMateriaPrima, ConsumoLote, Auditoria)
