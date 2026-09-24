"""Un mes de operaciones intermitentes en la base DEMO independiente."""
import random
import sqlite3
from datetime import datetime, time, timedelta
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from accounts.models import CustomUser
from inventario.models import MateriaPrima, ProductoTerminado, Proveedor, MateriaPrimaProveedor
from inventario.services import ajustar_stock
from inventario.procurement import crear_compra_manual, recibir, sugerir
from produccion.models import Produccion, DetalleProducto
from produccion.services.forecasting.training import entrenar
from produccion.services.forecasting.prediction import pronosticar


class Command(BaseCommand):
    help = 'Crea 30 días de producción intermitente y pedidos únicamente con OPERASTOCK_DEMO=1.'

    @transaction.atomic
    def handle(self,*args,**options):
        if not settings.DEMO_MODE:
            raise CommandError('Active OPERASTOCK_DEMO=1. Nunca se simula sobre la base operativa.')
        if Produccion.objects.exists():
            self.stdout.write('La simulación ya existe. No se duplicó ni se alteró.')
            return
        # Reuse local account password hashes without exposing them or changing credentials.
        source = settings.BASE_DIR/'db.sqlite3'
        with sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True) as db:
            db.row_factory = sqlite3.Row
            for row in db.execute('SELECT username,password,email,first_name,last_name,rol,is_staff,is_superuser,empresa FROM accounts_customuser WHERE is_active=1'):
                data = dict(row)
                name = data.pop('username')
                CustomUser.objects.get_or_create(username=name,defaults=data)
        user = CustomUser.objects.filter(rol='ADMINISTRADOR').first() or CustomUser.objects.filter(is_superuser=True).first()
        if not user:
            raise CommandError('Se necesita un administrador existente para utilizar la simulación con su acceso habitual.')
        today = timezone.localdate()
        rng = random.Random(24102026)
        materias = []
        for i,(nombre,costo) in enumerate([('Harina de maíz','3.20'),('Azúcar','2.80'),('Sal','1.20'),('Avena','4.50'),('Miel','12.00')]):
            proveedor = Proveedor.objects.create(nombre=f'Proveedor demo {i+1}',tiempo_entrega_dias=3+i%3)
            materia = MateriaPrima.objects.create(codigo=f'DEMO-M{i+1}',nombre=nombre,unidad_medida='kg',
                stock_actual=500,stock_minimo=10,costo_unitario=Decimal(costo),proveedor=proveedor)
            MateriaPrimaProveedor.objects.create(materia_prima=materia,proveedor=proveedor,precio=Decimal(costo),
                lead_time_dias=proveedor.tiempo_entrega_dias,moq=5,multiplo=5)
            materias.append(materia)
            for n,days in enumerate([2+i%3,4+i%2]):
                pedido = today-timedelta(days=26-n*12)
                order = crear_compra_manual(materia.pk,proveedor,20,user,fecha_pedido=pedido)
                recibir(order.pk,user,pedido+timedelta(days=days))
        recipes = [('Galleta de maíz',[(0,'.5'),(1,'.1'),(2,'.02')]),
                   ('Barra de avena',[(3,'.6'),(4,'.08')]),
                   ('Pan de maíz',[(0,'.45'),(2,'.03')]),
                   ('Galleta de miel',[(3,'.25'),(4,'.1'),(1,'.05')])]
        productos=[]
        for i,(nombre,lines) in enumerate(recipes):
            producto = ProductoTerminado.objects.create(codigo=f'DEMO-P{i+1}',nombre=nombre,precio=Decimal('4.00'))
            for mid,c in lines:
                DetalleProducto.objects.create(codigoProductoTerminado=producto,codigoMateriaPrima=materias[mid],cantidad=Decimal(c))
            productos.append(producto)
        count = 0
        for i in range(30):
            day = today-timedelta(days=30-i)
            if i != 0 and (rng.random()<.28 or day.weekday()==6):
                continue
            # Random subset, not every product/ingredient on each production day.
            for producto in rng.sample(productos,rng.choice([1,1,2])):
                cantidad = rng.randint(8,28)
                if i == 21:
                    cantidad *= 2
                p = Produccion.objects.create(producto=producto,cantidad_producida=cantidad,sintetica=True)
                p.consumir_materiales(user)
                Produccion.objects.filter(pk=p.pk).update(fecha=timezone.make_aware(datetime.combine(day,time(10+rng.randint(0,6),0))))
                count += 1
        for materia,saldo in zip(materias,[15,35,20,10,25]):
            materia.refresh_from_db()
            delta = materia.stock_actual-Decimal(saldo)
            if delta>0:
                ajustar_stock(materia.pk,delta,'SALIDA',user,'Saldo de cierre del escenario sintético')
            run = entrenar(materia,user)
            if run.artefacto:
                pronosticar(run,60)
        order = crear_compra_manual(materias[0].pk,materias[0].proveedor,20,user,fecha_pedido=today-timedelta(days=2),fecha_estimada=today+timedelta(days=1))
        for materia in materias:
            try:
                sugerir(materia,user)
            except Exception as exc:
                from django.core.exceptions import ValidationError
                if not isinstance(exc,ValidationError):
                    raise
        self.stdout.write(self.style.SUCCESS(f'Simulación separada: {count} producciones, 30 días, 10 recepciones y 1 pedido pendiente ({order}).'))
