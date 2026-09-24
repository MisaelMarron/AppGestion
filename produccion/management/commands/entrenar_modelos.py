from django.core.management.base import BaseCommand, CommandError
from inventario.models import MateriaPrima
from produccion.services.forecasting.training import entrenar
from produccion.services.forecasting.prediction import pronosticar


class Command(BaseCommand):
    help = 'Entrena y compara modelos temporalmente; opcionalmente genera pronósticos.'

    def add_arguments(self, parser):
        parser.add_argument('--materia',type=int)
        parser.add_argument('--horizonte',type=int,default=60)
        parser.add_argument('--solo-entrenar',action='store_true')

    def handle(self,*args,**options):
        if not 1 <= options['horizonte'] <= 365:
            raise CommandError('Horizonte permitido: 1–365.')
        qs = MateriaPrima.objects.filter(activo=True)
        if options['materia']:
            qs = qs.filter(pk=options['materia'])
        for materia in qs:
            run = entrenar(materia)
            if run.artefacto and not options['solo_entrenar']:
                pronosticar(run,options['horizonte'])
            self.stdout.write(f'{materia.codigo}: {run.estado} / {run.modelo} / {run.metricas}')
