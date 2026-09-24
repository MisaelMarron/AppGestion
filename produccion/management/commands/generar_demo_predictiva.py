import csv
from datetime import timedelta
from pathlib import Path
import numpy as np
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Genera CSV sintético separado, sin escribir en tablas operativas.'

    def add_arguments(self,parser):
        parser.add_argument('--salida',default='var/demo/consumo_sintetico.csv')
        parser.add_argument('--dias',type=int,default=180)

    def handle(self,*args,**options):
        n = options['dias']
        if not 60 <= n <= 3650:
            raise CommandError('Use entre 60 y 3650 días.')
        path = Path(options['salida'])
        if path.exists():
            raise CommandError('El archivo ya existe; elija otra ruta.')
        path.parent.mkdir(parents=True,exist_ok=True)
        rng = np.random.default_rng(42)
        with path.open('w',newline='',encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['fecha','materia','consumo','origen'])
            for i in range(n):
                value = max(0,20+i*.05+6*np.sin(i*2*np.pi/7)+rng.normal(0,2))
                if i in [40,90,140]:
                    value *= 3
                writer.writerow([(timezone.localdate()-timedelta(days=n-i)).isoformat(),'DEMO-HARINA',round(value,5),'SINTETICO_NO_INVESTIGACION'])
        self.stdout.write(f'Datos sintéticos separados: {path.resolve()}')
