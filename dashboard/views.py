from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone
from inventario.models import MateriaPrima, ProductoTerminado, Proveedor, OrdenCompra, SugerenciaCompra, MovimientoInventario
from inventario.procurement import analizar
from produccion.models import Produccion


@login_required
def dashboard_home(request):
    hoy = timezone.localdate()
    desde = hoy-timedelta(days=29)
    materias = list(MateriaPrima.objects.filter(activo=True))
    rows = [{'materia':m,'a':analizar(m)} for m in materias]
    rows.sort(key=lambda r: {'CRITICO':0,'ATENCION':1,'ESTABLE':2}.get(r['a']['riesgo'],3))
    producciones = Produccion.objects.filter(ejecutada=True,anulada=False)
    counts = {r['dia'].isoformat():r['total'] for r in producciones.filter(fecha__date__gte=desde).annotate(dia=TruncDate('fecha')).values('dia').annotate(total=Count('pk'))}
    serie = [{'fecha':(desde+timedelta(days=i)).isoformat(),'producciones':counts.get((desde+timedelta(days=i)).isoformat(),0)} for i in range(30)]
    proveedores = Proveedor.objects.filter(activo=True).annotate(promedio_entrega=Avg('ofertas__detalleordencompra__entrega__dias'),entregas=Count('ofertas__detalleordencompra__entrega',distinct=True))
    risk = {state:sum(r['a']['riesgo']==state for r in rows) for state in ['ESTABLE','ATENCION','CRITICO','SIN_DATOS']}
    return render(request,'dashboard/dashboard.html',{
        'total_materias_primas':len(materias),'total_productos':ProductoTerminado.objects.filter(activo=True).count(),
        'total_proveedores':proveedores.count(),'producciones_mes':producciones.filter(fecha__date__gte=desde).count(),
        'proveedores':proveedores[:5],'ultimas_producciones':producciones.select_related('producto','usuario')[:6],
        'pedidos':OrdenCompra.objects.exclude(estado__in=['RECIBIDA','CERRADA']).select_related('proveedor').order_by('fecha_estimada')[:5],
        'compras_pendientes':OrdenCompra.objects.exclude(estado__in=['RECIBIDA','CERRADA']).count(),
        'ultimos_movimientos':MovimientoInventario.objects.select_related('materia_prima','producto_terminado','usuario')[:5],
        'serie':serie,'risk':risk,'prioridades':rows[:6],'hoy':hoy})
