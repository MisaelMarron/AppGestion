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
