from django import forms
from django.forms import inlineformset_factory
from produccion.models import DetalleProducto
from inventario.models import ProductoTerminado, MateriaPrima


class DetalleProductoForm(forms.ModelForm):
    """Línea de fórmula: materia prima + cantidad."""

    class Meta:
        model = DetalleProducto
        fields = ['codigoMateriaPrima', 'cantidad']
        widgets = {
            'codigoMateriaPrima': forms.Select(attrs={'class': 'form-select mp-select'}),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.001',
                'step': '0.001',
                'placeholder': '0.000',
            }),
        }
        labels = {
            'codigoMateriaPrima': 'Materia prima',
            'cantidad': 'Cantidad por unidad de producto',
        }


# FormSet para editar múltiples líneas de receta de un producto a la vez
DetalleProductoFormSet = inlineformset_factory(
    ProductoTerminado,
    DetalleProducto,
    form=DetalleProductoForm,
    fk_name='codigoProductoTerminado',
    extra=1,
    can_delete=True,
)


class ProduccionForm(forms.Form):
    """Formulario para iniciar una producción: seleccionar producto y cantidad."""

    producto = forms.ModelChoiceField(
        queryset=ProductoTerminado.objects.filter(activo=True),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_producto'}),
        label='Producto a fabricar',
        empty_label='— Selecciona un producto —',
    )
    cantidad = forms.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=0.001,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0.001',
            'step': '0.001',
            'placeholder': '0.000',
            'id': 'id_cantidad',
        }),
        label='Cantidad a producir',
    )

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que cero.')
        return cantidad
