from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserSession


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


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Administración del modelo UserSession."""

    list_display = ('user', 'session_key_partial', 'ip_address', 'created_at', 'last_activity', 'is_active')
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('user__username', 'ip_address', 'session_key')
    readonly_fields = ('user', 'session_key', 'ip_address', 'user_agent', 'created_at', 'last_activity')
    ordering = ('-last_activity',)

    fieldsets = (
        ('Sesión', {
            'fields': ('user', 'session_key', 'user_agent'),
        }),
        ('Acceso', {
            'fields': ('ip_address', 'created_at', 'last_activity'),
        }),
        ('Estado', {
            'fields': ('is_active',),
        }),
    )

    def session_key_partial(self, obj):
        """Muestra solo los primeros 8 caracteres de la clave de sesión."""
        return obj.session_key_partial
    session_key_partial.short_description = 'Clave de sesión'
