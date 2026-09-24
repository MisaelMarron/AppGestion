from decimal import Decimal
from django import forms
from inventario.models import MateriaPrimaProveedor, MateriaPrima
from produccion.models import OrdenProduccion


class StyledForm:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-check-input' if isinstance(f.widget,forms.CheckboxInput) else 'form-control'


class OfertaForm(StyledForm, forms.ModelForm):
    class Meta:
        model = MateriaPrimaProveedor
        fields = ['materia_prima','proveedor','precio','lead_time_dias','moq','multiplo','presentacion','activo']

    def clean_multiplo(self):
        n = self.cleaned_data['multiplo']
        if n <= 0:
            raise forms.ValidationError('El múltiplo debe ser positivo.')
        return n

    def clean(self):
        data = super().clean()
        if self.instance.pk:
            old = MateriaPrimaProveedor.objects.get(pk=self.instance.pk)
            if data.get('materia_prima') != old.materia_prima or data.get('proveedor') != old.proveedor:
                raise forms.ValidationError('No cambie la identidad de una oferta existente; cree otra oferta y desactive la anterior.')
        return data


class PoliticaForm(StyledForm, forms.ModelForm):
    class Meta:
        model = MateriaPrima
        fields = ['nivel_servicio','cobertura_dias','gestionar_lotes']

    def clean_cobertura_dias(self):
        n = self.cleaned_data['cobertura_dias']
        if not 1 <= n <= 180:
            raise forms.ValidationError('Use entre 1 y 180 días.')
        return n

    def clean(self):
        data = super().clean()
        if data.get('gestionar_lotes') and not MateriaPrima.objects.get(pk=self.instance.pk).gestionar_lotes:
            from django.db.models import Sum
            total = self.instance.lotes.aggregate(n=Sum('cantidad_disponible'))['n'] or Decimal(0)
            if total != self.instance.stock_actual:
                raise forms.ValidationError('Registre primero los lotes de apertura hasta conciliar su saldo con el stock físico.')
        return data


class PlanForm(StyledForm, forms.ModelForm):
    class Meta:
        model = OrdenProduccion
        fields = ['producto_terminado','formula','cantidad_producida','fecha_planificada','observacion']
        help_texts = {'formula':'Opcional: sin selección se utiliza la receta vigente del producto.'}
        widgets = {'fecha_planificada':forms.DateInput(attrs={'type':'date'}),'observacion':forms.Textarea(attrs={'rows':2})}

    def clean(self):
        data = super().clean()
        from django.utils import timezone
        if data.get('cantidad_producida',0) <= 0:
            raise forms.ValidationError('La cantidad debe ser positiva.')
        if data.get('formula') and data.get('producto_terminado') and data['formula'].producto_terminado != data['producto_terminado']:
            raise forms.ValidationError('La fórmula pertenece a otro producto.')
        if not data.get('fecha_planificada') or data['fecha_planificada'] < timezone.localdate():
            raise forms.ValidationError('Indique una fecha planificada desde hoy.')
        return data


class HistorialForm(StyledForm, forms.Form):
    materia = forms.ModelChoiceField(queryset=MateriaPrima.objects.all(),required=False)
    desde = forms.DateField(required=False,widget=forms.DateInput(attrs={'type':'date'}))
    hasta = forms.DateField(required=False,widget=forms.DateInput(attrs={'type':'date'}))
    frecuencia = forms.ChoiceField(choices=[('D','Diario'),('W','Semanal'),('MS','Mensual')],required=False)

    def clean(self):
        data = super().clean()
        if data.get('desde') and data.get('hasta') and data['desde'] > data['hasta']:
            raise forms.ValidationError('El inicio no puede superar el fin.')
        return data


class LoteAperturaForm(StyledForm, forms.Form):
    materia = forms.ModelChoiceField(queryset=MateriaPrima.objects.filter(gestionar_lotes=False))
    numero = forms.CharField(max_length=100)
    cantidad = forms.DecimalField(max_digits=12,decimal_places=5,min_value=Decimal('.00001'))
    vencimiento = forms.DateField(required=False,widget=forms.DateInput(attrs={'type':'date'}))
