from decimal import Decimal
from datetime import timedelta
from django.db.models import Sum
from django.utils import timezone
from inventario.models import MateriaPrima
from produccion.models import ConsumoMateriaPrima
from .forecasting.preprocessing import preparar


def clasificar():
    """ABC: valor consumido últimos 365 días, umbrales acumulados 80/95 %.
    XYZ: CV diario <= .5 / <= 1 / > 1. No modifica políticas de compra.
    """
    materias = list(MateriaPrima.objects.filter(activo=True))
    rows = []
    hasta = timezone.localdate()
    desde = hasta-timedelta(days=365)
    for materia in materias:
        consumido = ConsumoMateriaPrima.objects.filter(materia_prima=materia,produccion__anulada=False, produccion__sintetica=False,
            produccion__fecha__date__gte=desde,produccion__fecha__date__lt=hasta).aggregate(n=Sum('cantidad_usada'))['n'] or Decimal(0)
        serie,_ = preparar(materia)
        serie = serie.tail(365)
        cv = float(serie.std(ddof=0)/serie.mean()) if len(serie) and serie.mean()>0 else None
        rows.append({'materia':materia,'valor':consumido*(materia.costo_unitario or Decimal(0)),
                     'cv':cv,'xyz':'SIN_DATOS' if cv is None else 'X' if cv<=.5 else 'Y' if cv<=1 else 'Z'})
    rows.sort(key=lambda r:r['valor'],reverse=True)
    total = sum((r['valor'] for r in rows),Decimal(0))
    acumulado = Decimal(0)
    for row in rows:
        row['abc'] = 'SIN_DATOS' if total==0 or row['materia'].costo_unitario is None else ('A' if acumulado/total<Decimal('.8') else 'B' if acumulado/total<Decimal('.95') else 'C')
        acumulado += row['valor']
    return rows
