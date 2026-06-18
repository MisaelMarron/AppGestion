from django.contrib import admin
from .models import Empresa


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    """Administración del modelo Empresa."""

    list_display = ('nombre', 'ruc', 'telefono', 'correo', 'activo', 'fecha_creacion')
    list_filter = ('activo',)
    search_fields = ('nombre', 'ruc', 'correo')
    ordering = ('nombre',)
