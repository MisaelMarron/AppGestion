from django.db import models
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from inventario.models import MateriaPrima, ProductoTerminado, MovimientoInventario
from produccion.models import OrdenProduccion, Produccion


@login_required
def dashboard_home(request):
    """Vista principal del dashboard con indicadores clave."""

    total_materias_primas = MateriaPrima.objects.filter(activo=True).count()
    total_productos = ProductoTerminado.objects.filter(activo=True).count()

    # Materias primas con stock crítico (stock_actual <= stock_minimo)
    materias_criticas = MateriaPrima.objects.filter(
        activo=True,
        stock_actual__lte=models.F('stock_minimo'),
    )
    total_stock_critico = materias_criticas.count()

    # Últimas 5 producciones
    ultimas_producciones = Produccion.objects.filter(ejecutada=True).select_related('producto').order_by('-fecha')[:5]

    # Últimos 5 movimientos de inventario
    ultimos_movimientos = MovimientoInventario.objects.select_related(
        'materia_prima', 'producto_terminado', 'usuario',
    ).order_by('-fecha')[:5]

    from inventario.procurement import analizar
    from inventario.models import SugerenciaCompra, OrdenCompra, LoteMateriaPrima
    from django.utils import timezone
    from datetime import timedelta
    analisis = [analizar(m) for m in MateriaPrima.objects.filter(activo=True)]
    context = {
        'predictivo_criticos': sum(a['riesgo'] == 'CRITICO' for a in analisis),
        'predictivo_atencion': sum(a['riesgo'] == 'ATENCION' for a in analisis),
        'compras_pendientes': SugerenciaCompra.objects.filter(estado='PENDIENTE').count(),
        'ordenes_transito': OrdenCompra.objects.filter(estado='EN_TRANSITO').count(),
        'lotes_vencer': LoteMateriaPrima.objects.filter(cantidad_disponible__gt=0, fecha_vencimiento__lte=timezone.localdate()+timedelta(days=15)).count(),
        'total_materias_primas': total_materias_primas,
        'total_productos':       total_productos,
        'total_stock_critico':   total_stock_critico,
        'ultimas_producciones':  ultimas_producciones,
        'ultimos_movimientos':   ultimos_movimientos,
    }
    return render(request, 'dashboard/dashboard.html', context)
