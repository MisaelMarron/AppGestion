"""Renderiza una vista de QA con datos sintéticos en una base temporal de Django.
No toca la base operativa. Ejecutar desde la raíz: python scripts/preview_predictivo.py
"""
import os
import sys
import tempfile
from pathlib import Path
from datetime import timedelta
from decimal import Decimal

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.test.utils import setup_databases, teardown_databases, setup_test_environment
from django.test import Client, override_settings
from django.utils import timezone
from accounts.models import CustomUser
from inventario.models import MateriaPrima, ProductoTerminado, Proveedor, MateriaPrimaProveedor
from produccion.models import Produccion, ConsumoMateriaPrima
from produccion.services.forecasting.training import entrenar
from produccion.services.forecasting.prediction import pronosticar

setup_test_environment()
old_config = setup_databases(verbosity=0,interactive=False)
try:
    user = CustomUser.objects.create_user(username='DEMO',email='demo@example.invalid',rol='ADMINISTRADOR')
    materia = MateriaPrima.objects.create(codigo='DEMO',nombre='DEMO · Harina de trigo',unidad_medida='kg',stock_actual=100)
    producto = ProductoTerminado.objects.create(codigo='DEMO',nombre='DEMO · Pan')
    proveedor = Proveedor.objects.create(nombre='DEMO · Proveedor Andino')
    MateriaPrimaProveedor.objects.create(materia_prima=materia,proveedor=proveedor,precio=Decimal('3.20'),lead_time_dias=4,moq=25,multiplo=5)
    for i in range(90):
        produccion = Produccion.objects.create(producto=producto,cantidad_producida=10,ejecutada=True)
        Produccion.objects.filter(pk=produccion.pk).update(fecha=timezone.now()-timedelta(days=90-i))
        ConsumoMateriaPrima.objects.create(produccion=produccion,materia_prima=materia,cantidad_usada=Decimal(14+i%7)+Decimal(i)/100)
    with tempfile.TemporaryDirectory() as directory,override_settings(MODEL_STORAGE=directory):
        run = entrenar(materia)
        pronosticar(run,60)
        client = Client()
        client.force_login(user)
        target = ROOT/'var'/'ui'
        target.mkdir(parents=True,exist_ok=True)
        for name,url in [('analisis',f'/produccion/analisis/{materia.pk}/'),('panel','/produccion/inteligencia/')]:
            response = client.get(url)
            assert response.status_code == 200
            content = response.content.decode().replace('<body>','<body><div class="alert alert-warning text-center">VISTA DE PRUEBA · DATOS SINTÉTICOS · NO SON RESULTADOS DE INVESTIGACIÓN</div>')
            (target/f'{name}.html').write_text(content,encoding='utf-8')
        destination = target/'static'/'js'
        destination.mkdir(parents=True,exist_ok=True)
        (destination/'predictive.js').write_bytes((ROOT/'static'/'js'/'predictive.js').read_bytes())
        print(f'Vista QA: {target}')
finally:
    teardown_databases(old_config,verbosity=0)
