from django.contrib import admin
from .models import Proveedor, MateriaPrima, ProductoTerminado, MovimientoInventario


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    """Administración del modelo Proveedor."""

    list_display = ('nombre', 'ruc', 'telefono', 'whatsapp', 'correo', 'tiempo_entrega_dias', 'activo')
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
    readonly_fields = ('stock_actual', 'gestionar_lotes')


@admin.register(ProductoTerminado)
class ProductoTerminadoAdmin(admin.ModelAdmin):
    """Administración del modelo ProductoTerminado."""

    list_display = ('nombre', 'unidad_medida', 'stock_actual', 'activo')
    list_filter = ('activo', 'unidad_medida')
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)
    readonly_fields = ('stock_actual',)


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    """Administración del modelo MovimientoInventario."""

    list_display = ('tipo', 'materia_prima', 'producto_terminado', 'cantidad', 'usuario', 'fecha')
    list_filter = ('tipo', 'fecha')
    search_fields = ('descripcion',)
    ordering = ('-fecha',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class RegistroOperativoAdmin(admin.ModelAdmin):
    """Las mutaciones pasan por las pantallas transaccionales, no por CRUD genérico."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from .models import (Auditoria, OrdenCompra, DetalleOrdenCompra, SugerenciaCompra,
                    ReservaInventario, LoteMateriaPrima, LeadTimeReal, MateriaPrimaProveedor)
for model in [Auditoria, OrdenCompra, DetalleOrdenCompra, SugerenciaCompra,
              ReservaInventario, LoteMateriaPrima, LeadTimeReal, MateriaPrimaProveedor]:
    admin.site.register(model, RegistroOperativoAdmin)
