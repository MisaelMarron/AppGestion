from django.contrib import admin
from .models import FormulaProducto, DetalleFormula, OrdenProduccion


class DetalleFormulaInline(admin.TabularInline):
    """Inline para editar detalles dentro de la fórmula."""
    model = DetalleFormula
    extra = 1


@admin.register(FormulaProducto)
class FormulaProductoAdmin(admin.ModelAdmin):
    """Administración del modelo FormulaProducto."""

    list_display = ('nombre', 'empresa', 'producto_terminado', 'cantidad_resultante', 'activo')
    list_filter = ('activo', 'empresa')
    search_fields = ('nombre', 'producto_terminado__nombre')
    inlines = [DetalleFormulaInline]
    ordering = ('nombre',)


@admin.register(DetalleFormula)
class DetalleFormulaAdmin(admin.ModelAdmin):
    """Administración del modelo DetalleFormula."""

    list_display = ('formula', 'materia_prima', 'cantidad_requerida')
    list_filter = ('formula__empresa',)
    search_fields = ('formula__nombre', 'materia_prima__nombre')


@admin.register(OrdenProduccion)
class OrdenProduccionAdmin(admin.ModelAdmin):
    """Administración del modelo OrdenProduccion."""

    list_display = ('__str__', 'empresa', 'producto_terminado', 'formula', 'cantidad_producida', 'usuario', 'fecha')
    list_filter = ('empresa', 'fecha')
    search_fields = ('producto_terminado__nombre', 'observacion')
    ordering = ('-fecha',)
