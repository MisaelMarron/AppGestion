from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render, redirect
from accounts.decorators import admin_required
from .models import Produccion
from .services.operaciones import corregir_produccion


class CorreccionForm(forms.Form):
    cantidad = forms.DecimalField(max_digits=12,decimal_places=5,min_value=Decimal('.00001'),
        label='Nueva cantidad producida',widget=forms.NumberInput(attrs={'class':'form-control','step':'.00001'}))
    motivo = forms.CharField(max_length=500,widget=forms.Textarea(attrs={'class':'form-control','rows':2}))


@login_required
def listado(request):
    qs = Produccion.objects.filter(ejecutada=True).select_related('producto','usuario')
    if request.GET.get('anuladas') != '1':
        qs = qs.filter(anulada=False)
    q = request.GET.get('q','').strip()
    if q:
        qs = qs.filter(producto__nombre__icontains=q)
    return render(request,'produccion/produccion_list.html',{'page':Paginator(qs,25).get_page(request.GET.get('page')),'q':q})


@admin_required
def modificar(request, pk, accion):
    p = get_object_or_404(Produccion,pk=pk,ejecutada=True,anulada=False)
    eliminar = accion == 'eliminar'
    if accion not in ['editar','eliminar']:
        return redirect('produccion:produccion_list')
    form = CorreccionForm(request.POST or None,initial={'cantidad':p.cantidad_producida})
    if eliminar:
        form.fields.pop('cantidad')
    if request.method == 'POST' and form.is_valid():
        try:
            corregir_produccion(pk,request.user,form.cleaned_data.get('cantidad'),form.cleaned_data['motivo'],eliminar)
            messages.success(request,'Producción eliminada y stocks revertidos.' if eliminar else 'Cantidades e inventario actualizados.')
            return redirect('produccion:produccion_list')
        except ValidationError as exc:
            form.add_error(None,exc)
    return render(request,'produccion/produccion_corregir.html',{'p':p,'form':form,'eliminar':eliminar})
