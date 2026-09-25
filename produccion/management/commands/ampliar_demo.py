"""Amplía la demo a 120 días para activar la comparación de los cuatro modelos."""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser
from inventario.models import MateriaPrima, ProductoTerminado
from inventario.services import ajustar_stock
from inventario.procurement import sugerir
from produccion.models import Produccion
from produccion.services.forecasting.training import entrenar
from produccion.services.forecasting.prediction import pronosticar


class Command(BaseCommand):
    help = 'Añade 90 días anteriores de producción irregular a la demo mensual y compara modelos.'

    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError('Este comando requiere OPERASTOCK_DEMO=1.')
        today = timezone.localdate()
        materias = list(MateriaPrima.objects.filter(codigo__startswith='DEMO-M').order_by('codigo'))
        productos = list(ProductoTerminado.objects.filter(codigo__startswith='DEMO-P').order_by('codigo'))
        if len(materias) != 5 or len(productos) != 4 or not Produccion.objects.filter(sintetica=True).exists():
            raise CommandError('Primero ejecute simular_mes en la base demo.')
        if Produccion.objects.filter(sintetica=True,fecha__date__lt=today-timedelta(days=30)).exists():
            self.stdout.write('La demo ampliada ya existe; no se duplicaron producciones.')
            return
        user = CustomUser.objects.filter(rol='ADMINISTRADOR').first() or CustomUser.objects.filter(is_superuser=True).first()
        if not user:
            raise CommandError('La demo requiere un administrador.')

        rng = random.Random(120092026)
        initial = {m.pk:m.stock_actual for m in materias}
        count = 0
        with transaction.atomic():
            # The temporary stock belongs only to the demo. Restore exact closing balances
            # after replaying production, so a comparison does not change today's decision.
            for materia in materias:
                ajustar_stock(materia.pk, Decimal('1000'), 'ENTRADA', user,
                    'Existencia temporal para histórico simulado')
            for i in range(90):
                day = today-timedelta(days=120-i)
                if day.weekday() == 6 or rng.random() < .26:
                    continue
                for producto in rng.sample(productos, rng.choice([1,2,2,3])):
                    cantidad = rng.randint(7,30)
                    if rng.random() < .09:
                        cantidad += rng.randint(15,30)
                    p = Produccion.objects.create(producto=producto,
                        cantidad_producida=cantidad, sintetica=True)
                    p.consumir_materiales(user)
                    Produccion.objects.filter(pk=p.pk).update(fecha=timezone.make_aware(
                        datetime.combine(day,time(8+rng.randint(0,8),rng.choice([0,15,30])))))
                    count += 1
            for materia in materias:
                materia.refresh_from_db()
                delta = materia.stock_actual-initial[materia.pk]
                if delta:
                    ajustar_stock(materia.pk, abs(delta), 'SALIDA' if delta > 0 else 'ENTRADA',
                        user, 'Restablecer saldo de cierre del escenario simulado')

        results = []
        for materia in materias:
            run = entrenar(materia,user)
            if run.artefacto:
                pronosticar(run,60)
            try:
                sugerir(materia,user)
            except Exception as exc:
                from django.core.exceptions import ValidationError
                if not isinstance(exc,ValidationError):
                    raise
            results.append(f'{materia.nombre}: {run.registros} consumos, {run.modelo}, {run.estado}')
        self.stdout.write(self.style.SUCCESS(f'{count} producciones añadidas a intervalos irregulares.'))
        for row in results:
            self.stdout.write(row)
