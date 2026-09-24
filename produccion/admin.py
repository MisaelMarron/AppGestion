from django.contrib import admin
from .models import FormulaProducto, DetalleFormula, OrdenProduccion
from inventario.admin import RegistroOperativoAdmin
from inventario.services import auditar


class DetalleFormulaInline(admin.TabularInline):
    """Inline para editar detalles dentro de la fórmula."""
    model = DetalleFormula
    extra = 1


@admin.register(FormulaProducto)
class FormulaProductoAdmin(admin.ModelAdmin):
    """Administración del modelo FormulaProducto."""

    list_display = ('nombre', 'producto_terminado', 'cantidad_resultante', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'producto_terminado__nombre')
    inlines = [DetalleFormulaInline]
    ordering = ('nombre',)

    def save_model(self, request, obj, form, change):
        antes = {'nombre':form.initial.get('nombre'), 'cantidad_resultante':form.initial.get('cantidad_resultante')}
        super().save_model(request,obj,form,change)
        auditar(request.user,'MODIFICAR_FORMULA',obj,antes,
                {'nombre':obj.nombre,'cantidad_resultante':obj.cantidad_resultante})

    def save_formset(self, request, form, formset, change):
        antes = list(form.instance.detalles.values('materia_prima_id','cantidad_requerida'))
        super().save_formset(request,form,formset,change)
        auditar(request.user,'MODIFICAR_FORMULA_DETALLES',form.instance,{'detalles':antes},
                {'detalles':list(form.instance.detalles.values('materia_prima_id','cantidad_requerida'))})


@admin.register(DetalleFormula)
class DetalleFormulaAdmin(RegistroOperativoAdmin):
    """Administración del modelo DetalleFormula."""

    list_display = ('formula', 'materia_prima', 'cantidad_requerida')
    list_filter = ()
    search_fields = ('formula__nombre', 'materia_prima__nombre')


@admin.register(OrdenProduccion)
class OrdenProduccionAdmin(RegistroOperativoAdmin):
    """Administración del modelo OrdenProduccion."""

    list_display = ('__str__', 'producto_terminado', 'formula', 'cantidad_producida', 'usuario', 'fecha')
    list_filter = ('fecha',)
    search_fields = ('producto_terminado__nombre', 'observacion')
    ordering = ('-fecha',)


from .models import Produccion, ConsumoMateriaPrima, Entrenamiento, Pronostico, EvaluacionPronostico
for model in [Produccion, ConsumoMateriaPrima, Entrenamiento, Pronostico, EvaluacionPronostico]:
    admin.site.register(model,RegistroOperativoAdmin)
