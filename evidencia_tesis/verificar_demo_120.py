"""Verifica la base aislada usada para capturas y pruebas de 120 días."""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

db = os.environ.get('OPERA_DB_PATH')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if not db or Path(db).name != 'tesis_demo_120.sqlite3':
    raise SystemExit('Establezca OPERA_DB_PATH con la base aislada tesis_demo_120.sqlite3.')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.utils import timezone
from produccion.models import ConsumoMateriaPrima, Entrenamiento, Produccion, Pronostico
from inventario.models import MateriaPrima

hoy = timezone.localdate()
inicio, fin = hoy - timedelta(days=120), hoy - timedelta(days=1)
producciones = Produccion.objects.filter(fecha__date__range=(inicio, fin))
observado = {
    'inicio': inicio.isoformat(), 'fin': fin.isoformat(), 'dias_calendario': 120,
    'dias_con_produccion': producciones.datetimes('fecha', 'day').count(),
    'producciones_sinteticas': producciones.filter(sintetica=True).count(),
    'consumos': ConsumoMateriaPrima.objects.count(),
    'insumos': MateriaPrima.objects.count(),
    'entrenamientos': Entrenamiento.objects.count(),
    'pronosticos': Pronostico.objects.count(),
}
assert producciones.count() == observado['producciones_sinteticas'] > 0
assert not Produccion.objects.exclude(pk__in=producciones.values('pk')).exists()
assert observado['pronosticos'] > 0
print(json.dumps(observado, ensure_ascii=False, indent=2))
