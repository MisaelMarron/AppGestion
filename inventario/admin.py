from django.contrib import admin
from .models import Proveedor, MateriaPrima, ProductoTerminado, MovimientoInventario


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    """Administración del modelo Proveedor."""

    list_display = ('nombre', 'ruc', 'telefono', 'correo', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'ruc', 'correo')
    ordering = ('nombre',)


@admin.register(MateriaPrima)
class MateriaPrimaAdmin(admin.ModelAdmin):
    """Administración del modelo MateriaPrima."""

    list_display = (
        'nombre', 'unidad_medida', 'stock_actual',
        'stock_minimo', 'costo_unitario', 'proveedor', 'activo',
    )
    list_filter = ('activo', 'unidad_medida', 'proveedor')
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)


@admin.register(ProductoTerminado)
class ProductoTerminadoAdmin(admin.ModelAdmin):
    """Administración del modelo ProductoTerminado."""

    list_display = ('nombre', 'unidad_medida', 'stock_actual', 'activo')
    list_filter = ('activo', 'unidad_medida')
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    """Administración del modelo MovimientoInventario."""

    list_display = ('tipo', 'materia_prima', 'producto_terminado', 'cantidad', 'usuario', 'fecha')
    list_filter = ('tipo', 'fecha')
    search_fields = ('descripcion',)
    ordering = ('-fecha',)
