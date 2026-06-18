from django.db import models
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from inventario.models import MateriaPrima, ProductoTerminado, MovimientoInventario
from produccion.models import OrdenProduccion


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
    ultimas_producciones = OrdenProduccion.objects.select_related(
        'producto_terminado', 'usuario',
    ).order_by('-fecha')[:5]

    # Últimos 5 movimientos de inventario
    ultimos_movimientos = MovimientoInventario.objects.select_related(
        'materia_prima', 'producto_terminado', 'usuario',
    ).order_by('-fecha')[:5]

    context = {
        'total_materias_primas': total_materias_primas,
        'total_productos': total_productos,
        'total_stock_critico': total_stock_critico,
        'materias_criticas': materias_criticas[:5],
        'ultimas_producciones': ultimas_producciones,
        'ultimos_movimientos': ultimos_movimientos,
    }
    return render(request, 'dashboard/dashboard.html', context)
