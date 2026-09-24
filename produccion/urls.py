from django.urls import path
from . import views

app_name = 'produccion'

urlpatterns = [
    # ── Fórmulas / Recetas ──
    path('formulas/', views.formula_list, name='formula_list'),
    path('formulas/<int:pk>/editar/', views.formula_edit, name='formula_edit'),

    # ── Producción ──
    path('producir/', views.produccion_form, name='produccion_form'),
    path('producir/preview/', views.produccion_preview, name='produccion_preview'),
    path('producir/confirmar/', views.produccion_confirmar, name='produccion_confirmar'),

    # ── Pronóstico de reposición ──
    path('pronosticos/', views.pronostico_reposicion, name='pronostico'),
]

from . import predictive_views as predictive
urlpatterns += [
    path('inteligencia/', predictive.panel, name='panel'),
    path('analisis/<int:pk>/', predictive.analisis, name='analisis'),
    path('analisis/<int:pk>/<str:accion>/', predictive.accion_analisis, name='accion_analisis'),
    path('historial/', predictive.historial, name='historial'),
    path('consumo/<int:pk>/revision/', predictive.exclusion, name='exclusion'),
    path('ofertas/nueva/', predictive.oferta_form, name='oferta_nueva'),
    path('ofertas/<int:pk>/', predictive.oferta_form, name='oferta_editar'),
    path('politica/<int:pk>/', predictive.politica, name='politica'),
    path('compras/', predictive.compras, name='compras'),
    path('compras/<int:pk>/', predictive.orden_compra, name='orden_compra'),
    path('sugerencias/<int:pk>/<str:accion>/', predictive.decision, name='decision'),
    path('planes/', predictive.planes, name='planes'),
    path('planes/<int:pk>/<str:accion>/', predictive.accion_plan, name='accion_plan'),
    path('clasificacion/', predictive.clasificacion, name='clasificacion'),
    path('auditoria/', predictive.auditoria, name='auditoria'),
    path('lotes/', predictive.lotes, name='lotes'),
    path('lotes/apertura/', predictive.lote_apertura, name='lote_apertura'),
]

from . import history_views
urlpatterns += [
    path('historial-producciones/',history_views.listado,name='produccion_list'),
    path('historial-producciones/<int:pk>/<str:accion>/',history_views.modificar,name='produccion_modificar'),
]
