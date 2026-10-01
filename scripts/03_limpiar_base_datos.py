"""Vacía los datos de la base configurada, conservando esquema y migraciones."""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.conf import settings
from django.core.management import call_command
from django.db import connection


def main():
    print(f"Base de datos que se vaciará: {connection.settings_dict['NAME']}")
    print('Se eliminarán también usuarios, sesiones, producciones y movimientos.')
    if '--force' not in sys.argv and '-y' not in sys.argv:
        if input('Escriba SI para continuar: ').strip() != 'SI':
            print('Operación cancelada.')
            return
    call_command('flush', interactive=False, verbosity=1)
    modelos_dir = Path(settings.MODEL_STORAGE)
    if modelos_dir.exists():
        for item in modelos_dir.iterdir():
            if item.is_file():
                item.unlink()
    print('Base de datos limpia.')


if __name__ == '__main__':
    main()
