from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import MateriaPrima, ProductoTerminado, MovimientoInventario
from .forms import MateriaPrimaForm, AjusteStockForm, ProductoTerminadoForm


# ══════════════════════════════════════════════
#  MATERIAS PRIMAS
# ══════════════════════════════════════════════

@login_required
def materia_prima_list(request):
    """Lista todas las materias primas activas con búsqueda."""
    query = request.GET.get('q', '').strip()
    materias = MateriaPrima.objects.filter(activo=True)
    if query:
        materias = materias.filter(
            Q(nombre__icontains=query) | Q(codigo__icontains=query)
        )
    materias = materias.order_by('nombre')
    return render(request, 'inventario/materia_prima_list.html', {
        'materias': materias,
        'query': query,
    })


@login_required
def materia_prima_create(request):
    """Crea una nueva materia prima."""
    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST)
        if form.is_valid():
            mp = form.save()
            messages.success(request, f'Materia prima «{mp.nombre}» creada correctamente.')
            return redirect('inventario:materia_prima_list')
    else:
        form = MateriaPrimaForm()
    return render(request, 'inventario/materia_prima_form.html', {
        'form': form,
        'titulo': 'Nueva materia prima',
        'accion': 'Crear',
    })


@login_required
def materia_prima_edit(request, pk):
    """Edita una materia prima existente."""
    mp = get_object_or_404(MateriaPrima, pk=pk, activo=True)
    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, instance=mp)
        if form.is_valid():
            mp = form.save()
            messages.success(request, f'Materia prima «{mp.nombre}» actualizada.')
            return redirect('inventario:materia_prima_list')
    else:
        form = MateriaPrimaForm(instance=mp)
    return render(request, 'inventario/materia_prima_form.html', {
        'form': form,
        'titulo': f'Editar — {mp.nombre}',
        'accion': 'Guardar cambios',
        'mp': mp,
    })


@login_required
def materia_prima_delete(request, pk):
    """Elimina (desactiva) una materia prima."""
    mp = get_object_or_404(MateriaPrima, pk=pk, activo=True)
    if request.method == 'POST':
        mp.activo = False
        mp.save(update_fields=['activo'])
        messages.success(request, f'Materia prima «{mp.nombre}» eliminada.')
        return redirect('inventario:materia_prima_list')
    return render(request, 'inventario/confirmar_eliminar.html', {
        'objeto': mp,
        'tipo': 'materia prima',
        'cancel_url': 'inventario:materia_prima_list',
    })


@login_required
def materia_prima_ajuste(request, pk):
    """Ajusta el stock de una materia prima (entrada o salida)."""
    mp = get_object_or_404(MateriaPrima, pk=pk, activo=True)
    if request.method == 'POST':
        form = AjusteStockForm(request.POST)
        if form.is_valid():
            tipo = form.cleaned_data['tipo']
            cantidad = form.cleaned_data['cantidad']
            descripcion = form.cleaned_data.get('descripcion', '')

            if tipo == 'SALIDA':
                if mp.stock_actual < cantidad:
                    messages.error(
                        request,
                        f'Stock insuficiente. Stock actual: {mp.stock_actual} {mp.get_unidad_medida_display()}.'
                    )
                    return render(request, 'inventario/ajuste_stock.html', {'form': form, 'mp': mp})
                mp.stock_actual -= cantidad
            else:
                mp.stock_actual += cantidad

            mp.save(update_fields=['stock_actual', 'ultima_vez_actualizado'])

            # Registrar movimiento
            MovimientoInventario.objects.create(
                tipo=tipo,
                materia_prima=mp,
                cantidad=cantidad,
                descripcion=descripcion,
                usuario=request.user,
            )

            accion = 'sumado al' if tipo == 'ENTRADA' else 'restado del'
            messages.success(
                request,
                f'{cantidad} {mp.get_unidad_medida_display()} {accion} stock de «{mp.nombre}». '
                f'Nuevo stock: {mp.stock_actual}.'
            )
            return redirect('inventario:materia_prima_list')
    else:
        form = AjusteStockForm()
    return render(request, 'inventario/ajuste_stock.html', {'form': form, 'mp': mp})


# ══════════════════════════════════════════════
#  PRODUCTOS TERMINADOS
# ══════════════════════════════════════════════

@login_required
def producto_terminado_list(request):
    """Lista todos los productos terminados activos con búsqueda."""
    query = request.GET.get('q', '').strip()
    productos = ProductoTerminado.objects.filter(activo=True)
    if query:
        productos = productos.filter(
            Q(nombre__icontains=query) | Q(codigo__icontains=query)
        )
    productos = productos.order_by('nombre')
    return render(request, 'inventario/producto_terminado_list.html', {
        'productos': productos,
        'query': query,
    })


@login_required
def producto_terminado_create(request):
    """Crea un nuevo producto terminado."""
    if request.method == 'POST':
        form = ProductoTerminadoForm(request.POST)
        if form.is_valid():
            pt = form.save()
            messages.success(request, f'Producto «{pt.nombre}» creado correctamente.')
            return redirect('inventario:producto_terminado_list')
    else:
        form = ProductoTerminadoForm()
    return render(request, 'inventario/producto_terminado_form.html', {
        'form': form,
        'titulo': 'Nuevo producto terminado',
        'accion': 'Crear',
    })


@login_required
def producto_terminado_edit(request, pk):
    """Edita un producto terminado. El código se mantiene fijo."""
    pt = get_object_or_404(ProductoTerminado, pk=pk, activo=True)
    if request.method == 'POST':
        form = ProductoTerminadoForm(request.POST, instance=pt)
        if form.is_valid():
            pt = form.save()
            messages.success(request, f'Producto «{pt.nombre}» actualizado.')
            return redirect('inventario:producto_terminado_list')
    else:
        form = ProductoTerminadoForm(instance=pt)
        # Bloquear el campo código en edición
        form.fields['codigo'].widget.attrs['readonly'] = True
        form.fields['codigo'].help_text = 'El código no se puede cambiar para no romper referencias.'
    return render(request, 'inventario/producto_terminado_form.html', {
        'form': form,
        'titulo': f'Editar — {pt.nombre}',
        'accion': 'Guardar cambios',
        'pt': pt,
        'es_edicion': True,
    })


@login_required
def producto_terminado_delete(request, pk):
    """Elimina (desactiva) un producto terminado."""
    pt = get_object_or_404(ProductoTerminado, pk=pk, activo=True)
    if request.method == 'POST':
        pt.activo = False
        pt.save(update_fields=['activo'])
        messages.success(request, f'Producto «{pt.nombre}» eliminado.')
        return redirect('inventario:producto_terminado_list')
    return render(request, 'inventario/confirmar_eliminar.html', {
        'objeto': pt,
        'tipo': 'producto terminado',
        'cancel_url': 'inventario:producto_terminado_list',
    })
