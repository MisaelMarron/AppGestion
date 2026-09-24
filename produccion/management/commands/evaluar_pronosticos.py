from django.core.management.base import BaseCommand
from produccion.services.forecasting.prediction import retroalimentar


class Command(BaseCommand):
    help = 'Compara pronósticos guardados con consumos de días completos.'

    def handle(self,*args,**options):
        self.stdout.write(f'Evaluaciones actualizadas: {retroalimentar()}')
