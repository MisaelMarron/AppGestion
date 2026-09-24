from django import forms
from .models import MateriaPrima, ProductoTerminado, Proveedor


class ProveedorForm(forms.ModelForm):
    """Formulario para crear/editar un proveedor."""

    class Meta:
        model = Proveedor
        fields = [
            'nombre', 'ruc', 'telefono', 'whatsapp',
            'correo', 'direccion', 'tiempo_entrega_dias',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del proveedor',
                'required': True,
            }),
            'ruc': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'RUC o identificación fiscal',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 01-234-5678',
            }),
            'whatsapp': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 51987654321 (código país + número)',
            }),
            'correo': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'proveedor@email.com',
            }),
            'direccion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Dirección del proveedor',
            }),
            'tiempo_entrega_dias': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '1',
            }),
        }
        labels = {
            'nombre': 'Nombre *',
            'ruc': 'RUC',
            'telefono': 'Teléfono',
            'whatsapp': 'WhatsApp',
            'correo': 'Correo electrónico',
            'direccion': 'Dirección',
            'tiempo_entrega_dias': 'Tiempo de entrega (días)',
        }


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

    numero_lote = forms.CharField(required=False, label='Número de lote (si corresponde)')
    vencimiento = forms.DateField(required=False, widget=forms.DateInput(attrs={'type':'date'}))
    proveedor = forms.ModelChoiceField(queryset=Proveedor.objects.filter(activo=True),required=False,
        empty_label='Sin proveedor: ajuste inmediato',widget=forms.Select(attrs={'class':'form-select'}))
    precio = forms.DecimalField(required=False,min_value=0,max_digits=12,decimal_places=2,
        label='Precio unitario del pedido',widget=forms.NumberInput(attrs={'class':'form-control','step':'.01'}))
    fecha_pedido = forms.DateField(required=False,widget=forms.DateInput(attrs={'class':'form-control','type':'date'}))
    fecha_estimada = forms.DateField(required=False,label='Fecha estimada de llegada',widget=forms.DateInput(attrs={'class':'form-control','type':'date'}))

    def clean(self):
        data = super().clean()
        if data.get('proveedor') and data.get('tipo') != 'ENTRADA':
            raise forms.ValidationError('Seleccione Entrada para registrar una compra a un proveedor.')
        return data

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
