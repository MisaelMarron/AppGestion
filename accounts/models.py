from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """Modelo de usuario personalizado para OperaStock."""

    class Rol(models.TextChoices):
        ADMINISTRADOR = 'ADMINISTRADOR', 'Administrador'
        OPERADOR = 'OPERADOR', 'Operador'

    email = models.EmailField('correo electrónico', unique=True)
    rol = models.CharField(
        'rol',
        max_length=20,
        choices=Rol.choices,
        default=Rol.OPERADOR,
    )
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    fecha_creacion = models.DateTimeField('fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'{self.username} ({self.get_rol_display()})'

    @property
    def es_admin(self):
        """Devuelve True si el usuario es superuser o tiene rol ADMINISTRADOR."""
        return self.is_superuser or self.rol == self.Rol.ADMINISTRADOR


class UserSession(models.Model):
    """Modelo para rastrear sesiones activas de usuarios."""

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='sesiones',
        verbose_name='usuario',
    )
    session_key = models.CharField('clave de sesión', max_length=40, unique=True)
    ip_address = models.GenericIPAddressField('dirección IP', null=True, blank=True)
    user_agent = models.TextField('agente de usuario', blank=True)
    created_at = models.DateTimeField('fecha de creación', auto_now_add=True)
    last_activity = models.DateTimeField('última actividad', auto_now=True)
    is_active = models.BooleanField('activa', default=True)

    class Meta:
        verbose_name = 'sesión de usuario'
        verbose_name_plural = 'sesiones de usuario'
        ordering = ['-last_activity']

    def __str__(self):
        estado = 'Activa' if self.is_active else 'Inactiva'
        return f'{self.user.username} — {estado} — {self.session_key[:8]}…'

    @property
    def session_key_partial(self):
        """Devuelve los primeros 8 caracteres de la clave de sesión."""
        return f'{self.session_key[:8]}…' if self.session_key else '—'

    @property
    def user_agent_short(self):
        """Devuelve una versión resumida del user agent."""
        if not self.user_agent:
            return '—'
        # Extraer solo la parte principal
        if len(self.user_agent) > 60:
            return self.user_agent[:60] + '…'
        return self.user_agent
