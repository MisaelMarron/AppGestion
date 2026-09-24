from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import hashlib
import joblib
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from produccion.models import Pronostico, EvaluacionPronostico, ConsumoMateriaPrima
from django.db.models import Sum
from .models import predecir


def pronosticar(run, horizonte=30):
    if not 1 <= horizonte <= 365:
        raise ValidationError('El horizonte debe ser de 1 a 365 días.')
    if run.obsoleto:
        raise ValidationError('El histórico cambió. Reentrene el modelo antes de pronosticar.')
    if not run.artefacto:
        raise ValidationError('No hay datos históricos para pronosticar.')
    root = Path(settings.MODEL_STORAGE).resolve()
    path = (root/run.artefacto).resolve()
    if path.parent != root or path.name != f'{run.version}.joblib':
        raise ValidationError('Ruta de modelo inválida.')
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != run.sha256:
        raise ValidationError('Artefacto ausente o modificado. Reentrene el modelo.')
    # Only locally generated, integrity-checked artifacts are loaded; never user uploads.
    artifact = joblib.load(path)
    hoy = timezone.localdate()
    gap = (hoy-run.fin).days-1
    if gap < 0 or gap > 30:
        raise ValidationError('Modelo fuera de vigencia. Reentrene antes de pronosticar.')
    values = predecir(run.modelo,artifact['modelo'],artifact['serie'],horizonte+gap)[gap:]
    return Pronostico.objects.create(materia_prima=run.materia_prima,entrenamiento=run,
        inicio=hoy,horizonte=horizonte,total=Decimal(str(sum(values))),
        valores=[{'fecha':(hoy+timedelta(days=i)).isoformat(),'consumo':v} for i,v in enumerate(values)])


def retroalimentar():
    hoy = timezone.localdate()
    count = 0
    for forecast in Pronostico.objects.filter(inicio__lt=hoy).iterator():
        for value in forecast.valores:
            if value['fecha'] >= hoy.isoformat():
                continue
            real = float(ConsumoMateriaPrima.objects.filter(materia_prima=forecast.materia_prima,
                produccion__anulada=False, produccion__sintetica=False,produccion__fecha__date=value['fecha']).aggregate(n=Sum('cantidad_usada'))['n'] or 0)
            error = abs(real-value['consumo'])
            EvaluacionPronostico.objects.update_or_create(pronostico=forecast,fecha=value['fecha'],
                defaults={'real':real,'predicho':value['consumo'],'error_absoluto':error,
                          'error_porcentual':error/abs(real)*100 if real else None})
            count += 1
    return count
