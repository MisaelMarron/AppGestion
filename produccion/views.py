from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from inventario.models import ProductoTerminado, MateriaPrima
from produccion.models import DetalleProducto, Produccion
from produccion.forms import DetalleProductoFormSet, ProduccionForm
from produccion.prediccion import calcular_todos_pronosticos, ESTADO_CRITICO, ESTADO_PRONTO


# ══════════════════════════════════════════════
#  FÓRMULAS / RECETAS
# ══════════════════════════════════════════════

@login_required
def formula_list(request):
    """Lista todos los productos y sus fórmulas."""
    productos = ProductoTerminado.objects.filter(activo=True).prefetch_related('detalles_producto__codigoMateriaPrima')
    return render(request, 'produccion/formula_list.html', {'productos': productos})


@login_required
def formula_edit(request, pk):
    """Edita la fórmula (receta) de un producto terminado."""
    producto = get_object_or_404(ProductoTerminado, pk=pk, activo=True)

    if request.method == 'POST':
        formset = DetalleProductoFormSet(
            request.POST,
            instance=producto,
            queryset=DetalleProducto.objects.filter(codigoProductoTerminado=producto),
        )
        if formset.is_valid():
            # Validar que no haya materias primas repetidas
            mps_vistas = set()
            hay_duplicados = False
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    mp = form.cleaned_data.get('codigoMateriaPrima')
                    if mp:
                        if mp.pk in mps_vistas:
                            hay_duplicados = True
                            break
                        mps_vistas.add(mp.pk)

            if hay_duplicados:
                messages.error(request, 'No puedes repetir la misma materia prima en la fórmula.')
            else:
                instances = formset.save(commit=False)
                for instance in instances:
                    instance.codigoProductoTerminado = producto
                    instance.save()
                for obj in formset.deleted_objects:
                    obj.delete()
                messages.success(request, f'Fórmula de «{producto.nombre}» actualizada correctamente.')
                return redirect('produccion:formula_list')
    else:
        formset = DetalleProductoFormSet(
            instance=producto,
            queryset=DetalleProducto.objects.filter(codigoProductoTerminado=producto),
        )

    return render(request, 'produccion/formula_form.html', {
        'producto': producto,
        'formset': formset,
    })


# ══════════════════════════════════════════════
#  PRODUCCIÓN — PREVISUALIZACIÓN Y CONFIRMACIÓN
# ══════════════════════════════════════════════

@login_required
def produccion_form(request):
    """Formulario para elegir producto y cantidad a producir."""
    form = ProduccionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        producto = form.cleaned_data['producto']
        cantidad = form.cleaned_data['cantidad']
        # Guardar en session para el paso de preview
        request.session['produccion_producto_id'] = producto.pk
        request.session['produccion_cantidad'] = str(cantidad)
        return redirect('produccion:produccion_preview')
    return render(request, 'produccion/produccion_form.html', {'form': form})


@login_required
def produccion_preview(request):
    """Muestra la previsualización: cuánto se necesita vs cuánto hay."""
    producto_id = request.session.get('produccion_producto_id')
    cantidad_str = request.session.get('produccion_cantidad')

    if not producto_id or not cantidad_str:
        messages.warning(request, 'Selecciona un producto y cantidad primero.')
        return redirect('produccion:produccion_form')

    from decimal import Decimal
    producto = get_object_or_404(ProductoTerminado, pk=producto_id, activo=True)
    cantidad = Decimal(cantidad_str)

    detalles = DetalleProducto.objects.filter(
        codigoProductoTerminado=producto
    ).select_related('codigoMateriaPrima')

    if not detalles.exists():
        messages.warning(
            request,
            f'El producto «{producto.nombre}» no tiene fórmula definida. '
            'Define su receta antes de producir.'
        )
        return redirect('produccion:formula_list')

    # Calcular requerimiento vs stock
    lineas = []
    hay_faltante = False
    for d in detalles:
        requerido = d.cantidad * cantidad
        disponible = d.codigoMateriaPrima.stock_actual
        falta = requerido > disponible
        if falta:
            hay_faltante = True
        lineas.append({
            'materia': d.codigoMateriaPrima,
            'requerido': requerido,
            'disponible': disponible,
            'falta': falta,
            'diferencia': disponible - requerido,
        })

    return render(request, 'produccion/produccion_preview.html', {
        'producto': producto,
        'cantidad': cantidad,
        'lineas': lineas,
        'hay_faltante': hay_faltante,
    })


@login_required
def produccion_confirmar(request):
    """Confirma la producción: descuenta stock y registra el evento."""
    if request.method != 'POST':
        return redirect('produccion:produccion_form')

    producto_id = request.session.get('produccion_producto_id')
    cantidad_str = request.session.get('produccion_cantidad')

    if not producto_id or not cantidad_str:
        messages.warning(request, 'Sesión expirada. Vuelve a iniciar la producción.')
        return redirect('produccion:produccion_form')

    from decimal import Decimal
    producto = get_object_or_404(ProductoTerminado, pk=producto_id, activo=True)
    cantidad = Decimal(cantidad_str)

    # Crear el registro de producción y consumir materiales
    produccion = Produccion(producto=producto, cantidad_producida=cantidad)
    produccion.save()

    try:
        produccion.consumir_materiales()
        # Limpiar session
        del request.session['produccion_producto_id']
        del request.session['produccion_cantidad']
        messages.success(
            request,
            f'✅ Producción confirmada: {cantidad} unidades de «{producto.nombre}». '
            'Stock de materias primas actualizado.'
        )
        return redirect('produccion:produccion_form')
    except ValidationError as e:
        produccion.delete()
        messages.error(request, f'Error al producir: {e.message}')
        return redirect('produccion:produccion_preview')


# ══════════════════════════════════════════════
#  PRONÓSTICO DE REPOSICIÓN
# ══════════════════════════════════════════════

@login_required
def pronostico_reposicion(request):
    """
    Vista del módulo predictivo — ventana fija de 15 días.

    Calcula para cada materia prima:
    - Tasa de consumo diaria (basada en historial de producciones)
    - Días de stock restante al ritmo actual
    - Fecha estimada de agotamiento
    - Factor de tendencia (subiendo / estable / bajando)
    - Clasificación de urgencia (CRÍTICO / PRONTO / PLANIFICAR / OK / SIN_DATOS)
    """
    VENTANA = 15  # Días fijos de análisis

    pronosticos = calcular_todos_pronosticos(VENTANA)

    # Contadores por estado para el resumen superior
    criticos  = sum(1 for p in pronosticos if p['estado'] == ESTADO_CRITICO)
    prontos   = sum(1 for p in pronosticos if p['estado'] == ESTADO_PRONTO)
    sin_datos = sum(1 for p in pronosticos if p['estado'] == 'SIN_DATOS')
    total     = len(pronosticos)

    return render(request, 'produccion/pronostico.html', {
        'pronosticos': pronosticos,
        'criticos':    criticos,
        'prontos':     prontos,
        'sin_datos':   sin_datos,
        'total':       total,
    })
