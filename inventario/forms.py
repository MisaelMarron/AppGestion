from django import forms
from .models import MateriaPrima, ProductoTerminado


class MateriaPrimaForm(forms.ModelForm):
    """Formulario para crear/editar una materia prima."""

    class Meta:
        model = MateriaPrima
        fields = ['codigo', 'nombre', 'descripcion', 'unidad_medida', 'stock_minimo', 'costo_unitario', 'proveedor']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: MP-001 (opcional, se genera automático)',
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la materia prima',
                'required': True,
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción opcional...',
            }),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.001',
            }),
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00',
            }),
            'proveedor': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'codigo': 'Código',
            'nombre': 'Nombre *',
            'descripcion': 'Descripción',
            'unidad_medida': 'Unidad de medida *',
            'stock_minimo': 'Stock mínimo',
            'costo_unitario': 'Costo unitario',
            'proveedor': 'Proveedor',
        }


class AjusteStockForm(forms.Form):
    """Formulario para ajustar (sumar o restar) el stock de una materia prima."""

    TIPO_CHOICES = [
        ('ENTRADA', 'Entrada (sumar)'),
        ('SALIDA', 'Salida (restar)'),
    ]

    tipo = forms.ChoiceField(
        choices=TIPO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Tipo de movimiento',
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
        }),
        label='Cantidad',
    )
    descripcion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Motivo del ajuste (opcional)...',
        }),
        label='Descripción / motivo',
    )

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que cero.')
        return cantidad


class ProductoTerminadoForm(forms.ModelForm):
    """Formulario para crear/editar un producto terminado."""

    class Meta:
        model = ProductoTerminado
        fields = ['codigo', 'nombre', 'descripcion', 'unidad_medida', 'precio']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: PT-001 (opcional)',
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del producto terminado',
                'required': True,
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción opcional...',
            }),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'precio': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00',
            }),
        }
        labels = {
            'codigo': 'Código',
            'nombre': 'Nombre *',
            'descripcion': 'Descripción',
            'unidad_medida': 'Unidad de medida *',
            'precio': 'Precio de venta',
        }
