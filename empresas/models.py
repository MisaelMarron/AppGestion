from django.db import models


class Empresa(models.Model):
    """Modelo que representa una empresa registrada en el sistema."""

    nombre = models.CharField('nombre', max_length=200)
    ruc = models.CharField('RUC', max_length=20, blank=True)
    direccion = models.CharField('dirección', max_length=300, blank=True)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    correo = models.EmailField('correo electrónico', blank=True)
    activo = models.BooleanField('activo', default=True)
    fecha_creacion = models.DateTimeField('fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'empresa'
        verbose_name_plural = 'empresas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
