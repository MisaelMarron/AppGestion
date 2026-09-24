import uuid
from django.db import models


class Entrenamiento(models.Model):
    materia_prima = models.ForeignKey('inventario.MateriaPrima', on_delete=models.PROTECT, related_name='entrenamientos')
    obsoleto = models.BooleanField(default=False)
    version = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fecha = models.DateTimeField(auto_now_add=True)
    inicio = models.DateField(null=True)
    fin = models.DateField(null=True)
    registros = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=30)
    modelo = models.CharField(max_length=40, blank=True)
    metricas = models.JSONField(default=dict)
    comparacion = models.JSONField(default=list)
    parametros = models.JSONField(default=dict)
    calidad = models.JSONField(default=dict)
    validacion = models.JSONField(default=list)
    artefacto = models.CharField(max_length=200, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['-fecha']


class Pronostico(models.Model):
    materia_prima = models.ForeignKey('inventario.MateriaPrima', on_delete=models.PROTECT, related_name='pronosticos')
    entrenamiento = models.ForeignKey(Entrenamiento, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    inicio = models.DateField()
    horizonte = models.PositiveIntegerField()
    valores = models.JSONField(default=list)
    total = models.DecimalField(max_digits=20, decimal_places=5)

    class Meta:
        ordering = ['-fecha']


class EvaluacionPronostico(models.Model):
    pronostico = models.ForeignKey(Pronostico, on_delete=models.PROTECT, related_name='evaluaciones')
    fecha = models.DateField()
    real = models.FloatField()
    predicho = models.FloatField()
    error_absoluto = models.FloatField()
    error_porcentual = models.FloatField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['pronostico','fecha'], name='evaluacion_fecha_unica')]
