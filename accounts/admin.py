from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Administración del modelo CustomUser."""

    list_display = ('username', 'email', 'rol', 'telefono', 'is_active', 'fecha_creacion')
    list_filter = ('rol', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'telefono')
    ordering = ('-fecha_creacion',)

    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {
            'fields': ('rol', 'telefono'),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información adicional', {
            'fields': ('email', 'rol', 'telefono'),
        }),
    )
