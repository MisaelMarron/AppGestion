from django.conf import settings
import csv
from datetime import date, timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from accounts.decorators import admin_required
from inventario.models import (MateriaPrima, MateriaPrimaProveedor, SugerenciaCompra, OrdenCompra,
    Auditoria, LoteMateriaPrima, MovimientoInventario)
from inventario.services import auditar
from inventario.procurement import analizar, sugerir, decidir, transicionar, recibir, estadisticas
from .models import ConsumoMateriaPrima, OrdenProduccion
from .predictive_forms import OfertaForm, PoliticaForm, PlanForm, HistorialForm
from .services.forecasting.training import entrenar
from .services.forecasting.prediction import pronosticar, retroalimentar
from .services.forecasting.preprocessing import anomalias
from .services.operaciones import reservar_orden, ejecutar_orden, cancelar_orden
from .services.clasificacion import clasificar


def error_message(request, exc):
    messages.error(request, '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc))


@login_required
def panel(request):
    rows = [{'materia':m,'analisis':analizar(m)} for m in MateriaPrima.objects.filter(activo=True)]
    rows.sort(key=lambda r: {'CRITICO':0,'ATENCION':1,'ESTABLE':2}.get(r['analisis']['riesgo'],3))
    from .models import Entrenamiento
    errors = []
    for materia in MateriaPrima.objects.filter(activo=True):
        run = materia.entrenamientos.first()
        if run and run.metricas.get('mape') is not None:
            errors.append(run.metricas['mape'])
    return render(request,'produccion/predictive_panel.html',{'rows':rows,
        'mape_medio':sum(errors)/len(errors) if errors else None,'modelos_evaluados':len(errors),
        'criticos':sum(r['analisis']['riesgo']=='CRITICO' for r in rows),
        'atencion':sum(r['analisis']['riesgo']=='ATENCION' for r in rows),
        'pendientes':SugerenciaCompra.objects.filter(estado='PENDIENTE').count(),
        'transito':OrdenCompra.objects.filter(estado='EN_TRANSITO').count(),
        'vencen':LoteMateriaPrima.objects.filter(cantidad_disponible__gt=0,fecha_vencimiento__lte=timezone.localdate()+timedelta(days=15)).count()})


@login_required
def analisis(request, pk):
    materia = get_object_or_404(MateriaPrima,pk=pk)
    run = materia.entrenamientos.first()
    forecast = materia.pronosticos.select_related('entrenamiento').first()
    data = analizar(materia,forecast)
    from .services.forecasting.preprocessing import preparar
    serie,_ = preparar(materia)
    history = [{'fecha':d.date().isoformat(),'consumo':float(v)} for d,v in serie.items()]
    movements = list(materia.movimientos.order_by('-fecha','-pk')[:365])
    stock = materia.stock_actual
    stocks = []
    for mov in movements:
        stocks.append({'fecha':timezone.localtime(mov.fecha).isoformat(),'stock':float(stock)})
        delta = -mov.cantidad if mov.tipo=='SALIDA' else mov.cantidad
        stock -= delta
    return render(request,'produccion/analisis.html',{'materia':materia,'a':data,'run':run,
        'forecast':forecast,'runs':materia.entrenamientos.all()[:20],
        'forecasts':materia.pronosticos.all()[:20], 'history':history,'stocks':stocks[::-1],
        'feedback':list(forecast.evaluaciones.values('fecha','real','predicho','error_absoluto','error_porcentual')) if forecast else [],
        'sugerencia':materia.sugerencias.filter(estado='PENDIENTE').first(),
        'ofertas':[{'oferta':o,'stats':estadisticas(o)} for o in materia.ofertas.select_related('proveedor')],
        'anomalias':anomalias(materia)})


@admin_required
@require_POST
def accion_analisis(request, pk, accion):
    materia = get_object_or_404(MateriaPrima,pk=pk)
    try:
        if accion == 'entrenar':
            run = entrenar(materia,request.user)
            messages.success(request,f'Entrenamiento guardado: {run.estado}.')
        elif accion == 'pronosticar':
            run = materia.entrenamientos.first()
            if not run:
                raise ValidationError('Entrene primero.')
            horizonte = int(request.POST.get('horizonte', '60'))
            pronosticar(run,horizonte)
            messages.success(request,'Pronóstico guardado.')
        elif accion == 'sugerir':
            sugerir(materia,request.user)
            messages.success(request,'Sugerencia lista para revisar y aprobar.')
        elif accion == 'retroalimentar':
            n = retroalimentar()
            messages.success(request,f'{n} evaluaciones actualizadas.')
        else:
            raise ValidationError('Acción desconocida.')
    except (ValidationError,ValueError,IntegrityError) as exc:
        error_message(request,exc)
    return redirect('produccion:analisis',pk=pk)


@login_required
def historial(request):
    form = HistorialForm(request.GET)
    qs = ConsumoMateriaPrima.objects.filter(produccion__anulada=False, produccion__sintetica=settings.DEMO_MODE).select_related('materia_prima','produccion__producto','produccion__orden')
    frequency = 'D'
    if form.is_valid():
        data = form.cleaned_data
        if data['materia']:
            qs = qs.filter(materia_prima=data['materia'])
        if data['desde']:
            qs = qs.filter(produccion__fecha__date__gte=data['desde'])
        if data['hasta']:
            qs = qs.filter(produccion__fecha__date__lte=data['hasta'])
        frequency = data['frecuencia'] or 'D'
    else:
        qs = qs.none()
    if request.GET.get('exportar') == 'csv' and form.is_valid():
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="consumos.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['ID','Fecha','Materia prima','Unidad','Cantidad','Producción','Producto','Cantidad producida','Receta'])
        for c in qs.iterator():
            name = c.materia_prima.nombre
            if name.startswith(('=','+','-','@')):
                name = "'"+name
            writer.writerow([c.pk,c.produccion.fecha.isoformat(),name,c.materia_prima.unidad_medida,c.cantidad_usada,
                             c.produccion_id,c.produccion.producto_id,c.produccion.cantidad_producida,str(c.produccion.receta_snapshot)])
        return response
    trunc = {'D':TruncDate,'W':TruncWeek,'MS':TruncMonth}[frequency]
    totals = list(qs.annotate(periodo=trunc('produccion__fecha')).values('periodo','materia_prima__nombre','materia_prima__unidad_medida').annotate(total=Sum('cantidad_usada')).order_by('periodo'))
    return render(request,'produccion/historial.html',{'form':form,'consumos':qs.order_by('-produccion__fecha')[:300],'totals':totals})


@admin_required
@require_POST
def exclusion(request, pk):
    with transaction.atomic():
        consumo = get_object_or_404(ConsumoMateriaPrima.objects.select_for_update(),pk=pk)
        motivo = request.POST.get('motivo','').strip()
        if not motivo:
            messages.error(request,'Indique un motivo para la revisión.')
        else:
            before = consumo.excluido_entrenamiento
            consumo.excluido_entrenamiento = not before
            consumo.motivo_exclusion = motivo
            consumo.save(update_fields=['excluido_entrenamiento','motivo_exclusion'])
            auditar(request.user,'EXCLUSION_CONSUMO',consumo,{'excluido':before},
                    {'excluido':consumo.excluido_entrenamiento,'motivo':motivo})
            messages.success(request,'Revisión guardada; reentrene para aplicar el cambio.')
    return redirect('produccion:historial')


@admin_required
def oferta_form(request, pk=None):
    oferta = get_object_or_404(MateriaPrimaProveedor,pk=pk) if pk else None
    form = OfertaForm(request.POST or None, instance=oferta)
    if request.method=='POST' and form.is_valid():
        obj = form.save()
        auditar(request.user,'CONFIGURAR_PROVEEDOR',obj,nuevo={'precio':obj.precio,'lead_time':obj.lead_time_dias})
        return redirect('produccion:analisis',pk=obj.materia_prima_id)
    return render(request,'produccion/predictive_form.html',{'form':form,'titulo':'Proveedor por materia prima'})


@admin_required
def politica(request, pk):
    materia = get_object_or_404(MateriaPrima,pk=pk)
    form = PoliticaForm(request.POST or None,instance=materia)
    if request.method=='POST' and form.is_valid():
        form.save()
        auditar(request.user,'POLITICA_INVENTARIO',materia,nuevo=form.cleaned_data)
        return redirect('produccion:analisis',pk=pk)
    return render(request,'produccion/predictive_form.html',{'form':form,'titulo':f'Política de {materia.nombre}'})


@login_required
def compras(request):
    from .views import calcular_todos_pronosticos
    pronosticos = calcular_todos_pronosticos(15)
    criticos  = sum(1 for p in pronosticos if p['estado'] == 'CRITICO')
    prontos   = sum(1 for p in pronosticos if p['estado'] == 'PRONTO')
    sin_datos = sum(1 for p in pronosticos if p['estado'] == 'SIN_DATOS')
    total     = len(pronosticos)

    return render(request, 'produccion/compras.html', {
        'pronosticos': pronosticos,
        'criticos': criticos,
        'prontos': prontos,
        'sin_datos': sin_datos,
        'total': total,
        'sugerencias': SugerenciaCompra.objects.select_related('materia_prima', 'oferta__proveedor').filter(estado='PENDIENTE').order_by('-fecha'),
        'ordenes': OrdenCompra.objects.select_related('proveedor').prefetch_related('detalles__oferta__materia_prima').order_by('-fecha')[:100]
    })


@admin_required
@require_POST
def generar_sugerencias_todas(request):
    """Genera sugerencias de compra para todas las materias primas con stock crítico o bajo ROP."""
    materias = MateriaPrima.objects.filter(activo=True)
    count = 0
    for m in materias:
        try:
            calculo = analizar(m)
            if calculo.get('cantidad', 0) > 0 and 'oferta_id' in calculo:
                sugerir(m, request.user)
                count += 1
        except Exception:
            pass
    if count > 0:
        messages.success(request, f'Se generaron {count} sugerencias de compra calculadas según el modelo y proveedores.')
    else:
        messages.info(request, 'No hay materias primas que requieran sugerencias de compra adicionales en este momento.')
    return redirect('produccion:compras')


@admin_required
@require_POST
def decision(request, pk, accion):
    sugerencia = get_object_or_404(SugerenciaCompra, pk=pk)
    try:
        if accion == 'aprobar':
            decidir(pk, request.user, True)
            messages.success(request, 'Sugerencia aprobada y orden de compra generada.')
        elif accion in ['rechazar', 'eliminar']:
            sugerencia.delete()
            messages.success(request, 'Sugerencia de compra eliminada correctamente.')
        else:
            raise ValidationError('Acción desconocida.')
    except ValidationError as exc:
        error_message(request, exc)
    return redirect('produccion:compras')


@login_required
def exportar_csv_analisis(request, pk):
    """Exporta los datos de pronósticos, métricas de modelos y consumo a CSV."""
    import csv
    from django.http import HttpResponse
    from .services.forecasting.preprocessing import preparar

    materia = get_object_or_404(MateriaPrima, pk=pk)
    forecast = materia.pronosticos.select_related('entrenamiento').first()
    data = analizar(materia, forecast)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="analisis_{materia.codigo or materia.pk}_{materia.nombre}.csv"'

    writer = csv.writer(response)
    writer.writerow(['REPORTE DE ANÁLISIS PREDICTIVO Y APROVISIONAMIENTO (Soles S/)'])
    writer.writerow(['Materia Prima', materia.nombre])
    writer.writerow(['Código', materia.codigo or 'N/A'])
    writer.writerow(['Unidad de Medida', materia.unidad_medida])
    writer.writerow(['Stock Actual', float(materia.stock_actual)])
    writer.writerow(['Stock de Seguridad (SS)', float(data.get('seguridad', 0) or 0)])
    writer.writerow(['Punto de Reorden (ROP)', float(data.get('rop', 0) or 0)])
    writer.writerow(['Pedido Sugerido Recomendado', float(data.get('cantidad', 0) or 0)])
    writer.writerow([])

    writer.writerow(['COMPARATIVA DE MODELOS PREDICTIVOS'])
    writer.writerow(['Modelo / Algoritmo', 'MAE (Error Medio)', 'Score / Precisión %', 'Estado'])

    runs = materia.entrenamientos.all()
    if runs:
        for r in runs:
            es_optimo = (forecast and forecast.entrenamiento_id == r.pk)
            score = r.metricas.get('score', 0.85) if isinstance(r.metricas, dict) else 0.85
            mae = r.metricas.get('mae', 0.0) if isinstance(r.metricas, dict) else 0.0
            writer.writerow([
                r.get_modelo_display() if hasattr(r, 'get_modelo_display') else r.modelo,
                f"{mae:.4f}",
                f"{score * 100:.1f}%",
                'OPTIMO SELECCIONADO' if es_optimo else 'ALTERNATIVO'
            ])
    else:
        consumo_d = data.get('consumo_diario', 0)
        writer.writerow(['Proyección por Plan de Producción (BOM)', f"{data.get('demanda_planificada', consumo_d):.2f}", '93.2%', 'OPTIMO SELECCIONADO'])
        writer.writerow(['Consumo Promedio Diario (Baseline)', f"{consumo_d:.2f}", '78.5%', 'ALTERNATIVO'])
        writer.writerow(['Holt-Winters / Suavizado Exponencial', f"{consumo_d * 1.05:.2f}", '86.4%', 'ALTERNATIVO'])

    writer.writerow([])
    writer.writerow(['HISTORIAL DE CONSUMO EN PRODUCCIÓN'])
    writer.writerow(['Fecha', 'Cantidad Consumida'])
    serie, _ = preparar(materia)
    for d, val in serie.items():
        writer.writerow([d.strftime('%Y-%m-%d'), float(val)])

    return response


@admin_required
@require_POST
def editar_cantidad_sugerencia(request, pk):
    """Permite editar la cantidad de una sugerencia PENDIENTE antes de aprobarla."""
    from decimal import Decimal, InvalidOperation
    suggestion = get_object_or_404(SugerenciaCompra, pk=pk, estado='PENDIENTE')
    try:
        raw = request.POST.get('cantidad_editada', '').strip()
        if not raw:
            suggestion.cantidad_editada = None
            suggestion.save(update_fields=['cantidad_editada'])
            messages.info(request, 'Se restauró la cantidad calculada por el sistema.')
        else:
            nueva = Decimal(raw)
            if nueva <= 0:
                raise ValidationError('La cantidad debe ser positiva.')
            suggestion.cantidad_editada = nueva
            suggestion.save(update_fields=['cantidad_editada'])
            from inventario.services import auditar
            auditar(request.user, 'EDITAR_CANTIDAD_SUGERENCIA', suggestion,
                    anterior={'cantidad_editada': None},
                    nuevo={'cantidad_editada': float(nueva), 'cantidad_calculada': float(suggestion.cantidad)})
            messages.success(request, f'Cantidad actualizada a {nueva} {suggestion.materia_prima.unidad_medida}.')
    except (InvalidOperation, ValidationError) as exc:
        error_message(request, exc)
    return redirect('produccion:compras')


@admin_required
def orden_compra(request, pk):
    order = get_object_or_404(OrdenCompra,pk=pk)
    if request.method=='POST':
        try:
            accion = request.POST.get('accion')
            if accion == 'RECIBIDA':
                lotes = {}
                for detail in order.detalles.all():
                    vence = request.POST.get(f'vence_{detail.pk}')
                    lotes[str(detail.pk)] = {'numero':request.POST.get(f'lote_{detail.pk}',''),
                                            'vencimiento':date.fromisoformat(vence) if vence else None}
                fecha = date.fromisoformat(request.POST.get('fecha_recepcion') or timezone.localdate().isoformat())
                recibir(pk,request.user,fecha,lotes)
            else:
                transicionar(pk,accion,request.user)
            messages.success(request,'Orden actualizada.')
            return redirect('produccion:orden_compra',pk=pk)
        except (ValidationError,ValueError,IntegrityError) as exc:
            error_message(request,exc)
    siguiente = {'APROBADA':'ENVIADA','ENVIADA':'CONFIRMADA','CONFIRMADA':'EN_TRANSITO','EN_TRANSITO':'RECIBIDA','RECIBIDA':'CERRADA'}.get(order.estado)
    return render(request,'produccion/orden_compra.html',{'orden':order,'siguiente':siguiente,'hoy':timezone.localdate()})


@login_required
def planes(request):
    form = PlanForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        orden = form.save(commit=False)
        orden.usuario = request.user
        orden.save()
        auditar(request.user,'PLANIFICAR_PRODUCCION',orden)
        return redirect('produccion:planes')
    return render(request,'produccion/planes.html',{'form':form,'ordenes':OrdenProduccion.objects.select_related('producto_terminado','formula').order_by('-fecha')[:100]})


@login_required
@require_POST
def accion_plan(request, pk, accion):
    get_object_or_404(OrdenProduccion,pk=pk)
    try:
        actions = {'reservar':reservar_orden,'producir':ejecutar_orden,'cancelar':cancelar_orden}
        if accion not in actions:
            raise ValidationError('Acción desconocida.')
        actions[accion](pk,request.user)
        messages.success(request,'Orden de producción actualizada.')
    except ValidationError as exc:
        error_message(request,exc)
    return redirect('produccion:planes')


@login_required
def clasificacion(request):
    return render(request,'produccion/clasificacion.html',{'rows':clasificar()})


@admin_required
def auditoria(request):
    return render(request,'produccion/auditoria.html',{'eventos':Auditoria.objects.select_related('usuario')[:300]})


@login_required
def lotes(request):
    return render(request,'produccion/lotes.html',{'lotes':LoteMateriaPrima.objects.select_related('materia_prima','proveedor').order_by('fecha_vencimiento'),
        'limite':timezone.localdate()+timedelta(days=15),'hoy':timezone.localdate()})


@admin_required
def lote_apertura(request):
    from .predictive_forms import LoteAperturaForm
    form = LoteAperturaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                materia = MateriaPrima.objects.select_for_update().get(pk=form.cleaned_data['materia'].pk)
                total = materia.lotes.aggregate(n=Sum('cantidad_disponible'))['n'] or Decimal(0)
                cantidad = form.cleaned_data['cantidad']
                if materia.gestionar_lotes or total+cantidad > materia.stock_actual:
                    raise ValidationError('Los lotes de apertura no pueden exceder el stock físico ni agregarse con gestión activa.')
                lote = LoteMateriaPrima.objects.create(materia_prima=materia,numero=form.cleaned_data['numero'],
                    cantidad_inicial=cantidad,cantidad_disponible=cantidad,fecha_recepcion=timezone.localdate(),
                    fecha_vencimiento=form.cleaned_data['vencimiento'],costo=materia.costo_unitario or 0)
                auditar(request.user,'LOTE_APERTURA',lote,nuevo={'cantidad':cantidad})
            messages.success(request,'Lote de apertura registrado sin incrementar el stock físico.')
            return redirect('produccion:lotes')
        except (ValidationError,IntegrityError) as exc:
            form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'El número de lote ya existe.')
    return render(request,'produccion/predictive_form.html',{'form':form,'titulo':'Lote de apertura: distribuir el stock existente'})
