from django.urls import path
from . import views

app_name = 'inventario'

urlpatterns = [
    # ── Materias Primas ──
    path('materias-primas/', views.materia_prima_list, name='materia_prima_list'),
    path('materias-primas/nueva/', views.materia_prima_create, name='materia_prima_create'),
    path('materias-primas/<int:pk>/editar/', views.materia_prima_edit, name='materia_prima_edit'),
    path('materias-primas/<int:pk>/eliminar/', views.materia_prima_delete, name='materia_prima_delete'),
    path('materias-primas/<int:pk>/ajuste/', views.materia_prima_ajuste, name='materia_prima_ajuste'),

    # ── Productos Terminados ──
    path('productos-terminados/', views.producto_terminado_list, name='producto_terminado_list'),
    path('productos-terminados/nuevo/', views.producto_terminado_create, name='producto_terminado_create'),
    path('productos-terminados/<int:pk>/editar/', views.producto_terminado_edit, name='producto_terminado_edit'),
    path('productos-terminados/<int:pk>/eliminar/', views.producto_terminado_delete, name='producto_terminado_delete'),

    # ── Proveedores ──
    path('proveedores/', views.proveedor_list, name='proveedor_list'),
    path('proveedores/nuevo/', views.proveedor_create, name='proveedor_create'),
    path('proveedores/<int:pk>/editar/', views.proveedor_edit, name='proveedor_edit'),
    path('proveedores/<int:pk>/eliminar/', views.proveedor_delete, name='proveedor_delete'),
]
