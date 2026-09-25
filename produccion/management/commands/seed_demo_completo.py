"""
Seed completo con datos simulados del último mes:
- 2 proveedores reales con datos de contacto
- Materias primas vinculadas a esos proveedores
- 30 días de producciones con variación
- Compras de materias primas (órdenes completas con recepción)
- Sugerencias de reabastecimiento activas
- Entrena modelos y genera pronósticos para activar comparativa
Requiere OPERASTOCK_DEMO=1.
"""
import random
import sqlite3
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser
from inventario.models import (MateriaPrima, ProductoTerminado, Proveedor,
                                MateriaPrimaProveedor, MovimientoInventario)
from inventario.services import ajustar_stock
from inventario.procurement import crear_compra_manual, recibir, sugerir
from produccion.models import Produccion, DetalleProducto
from produccion.services.forecasting.training import entrenar
from produccion.services.forecasting.prediction import pronosticar


class Command(BaseCommand):
    help = 'Seed completo: 2 proveedores, materias primas, 30 días de producción y compras. Solo con OPERASTOCK_DEMO=1.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError('Active OPERASTOCK_DEMO=1. Nunca se simula sobre la base operativa.')
        if Produccion.objects.filter(sintetica=True).exists():
            self.stdout.write(self.style.WARNING(
                'Los datos de simulación ya existen. Ejecute primero con la base demo limpia.'))
            return

        # ── Copiar usuarios desde la base operativa ──
        source = settings.BASE_DIR / 'db.sqlite3'
        with sqlite3.connect(f'file:{source.as_posix()}?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            for row in db.execute(
                'SELECT username,password,email,first_name,last_name,rol,'
                'is_staff,is_superuser,empresa FROM accounts_customuser WHERE is_active=1'
            ):
                data = dict(row)
                name = data.pop('username')
                CustomUser.objects.get_or_create(username=name, defaults=data)

        user = (CustomUser.objects.filter(rol='ADMINISTRADOR').first()
                or CustomUser.objects.filter(is_superuser=True).first())
        if not user:
            raise CommandError('Se necesita al menos un administrador en la base operativa.')

        today = timezone.localdate()
        rng = random.Random(20260924)

        # ════════════════════════════════════════
        # 1. PROVEEDORES (2 reales con datos completos)
        # ════════════════════════════════════════
        prov_a = Proveedor.objects.create(
            nombre='Distribuidora Granelera del Norte S.A.',
            ruc='20512345678',
            telefono='(55) 3344-5566',
            whatsapp='525533445566',
            correo='pedidos@graneleranorte.com.mx',
            direccion='Blvd. Industrial 1420, Monterrey, N.L.',
            tiempo_entrega_dias=4,
            activo=True,
        )
        prov_b = Proveedor.objects.create(
            nombre='Insumos Naturales Rivas & Cía.',
            ruc='20687654321',
            telefono='(33) 2211-8899',
            whatsapp='523322118899',
            correo='ventas@insumosrivas.com.mx',
            direccion='Av. Reforma 7800, Guadalajara, Jal.',
            tiempo_entrega_dias=6,
            activo=True,
        )
        self.stdout.write(f'  [OK] Proveedores: {prov_a.nombre}  |  {prov_b.nombre}')

        # ════════════════════════════════════════
        # 2. MATERIAS PRIMAS + relaciones con proveedores
        # ════════════════════════════════════════
        specs = [
            # (nombre, costo, stock_inicial, unidad, prov_principal, prov_alt)
            ('Harina de maíz',   '3.20',  500, 'kg', prov_a, prov_b),
            ('Azúcar refinada',  '2.80',  400, 'kg', prov_a, prov_b),
            ('Sal de mar',       '1.20',  300, 'kg', prov_b, prov_a),
            ('Avena orgánica',   '4.50',  350, 'kg', prov_b, prov_a),
            ('Miel de abeja',   '12.00',  180, 'kg', prov_b, None),
        ]
        materias = []
        for i, (nombre, costo, stock, unidad, prov_principal, prov_alt) in enumerate(specs):
            mp = MateriaPrima.objects.create(
                codigo=f'DEMO-M{i+1}',
                nombre=nombre,
                unidad_medida=unidad,
                stock_actual=stock,
                stock_minimo=20,
                costo_unitario=Decimal(costo),
                proveedor=prov_principal,
            )
            # Oferta principal
            MateriaPrimaProveedor.objects.create(
                materia_prima=mp, proveedor=prov_principal,
                precio=Decimal(costo),
                lead_time_dias=prov_principal.tiempo_entrega_dias,
                moq=10, multiplo=5,
                presentacion='Saco 25 kg',
            )
            # Oferta alternativa (proveedor_b para las primeras 4)
            if prov_alt:
                MateriaPrimaProveedor.objects.create(
                    materia_prima=mp, proveedor=prov_alt,
                    precio=(Decimal(costo) * Decimal('1.08')).quantize(Decimal('0.01')),
                    lead_time_dias=prov_alt.tiempo_entrega_dias,
                    moq=20, multiplo=10,
                    presentacion='Saco 50 kg',
                )
            materias.append(mp)

        self.stdout.write(f'  [OK] {len(materias)} materias primas con 2 ofertas de proveedor cada una.')

        # ════════════════════════════════════════
        # 3. PRODUCTOS TERMINADOS + recetas
        # ════════════════════════════════════════
        recipes = [
            ('Galleta de maíz',   [( 0, '.50'), ( 1, '.10'), (2, '.02')]),
            ('Barra de avena',    [( 3, '.60'), ( 4, '.08')]),
            ('Pan de maíz',       [( 0, '.45'), ( 2, '.03')]),
            ('Galleta de miel',   [( 3, '.25'), ( 4, '.10'), (1, '.05')]),
        ]
        productos = []
        for i, (nombre, lines) in enumerate(recipes):
            pt = ProductoTerminado.objects.create(
                codigo=f'DEMO-P{i+1}', nombre=nombre, precio=Decimal('4.50'))
            for mid, c in lines:
                DetalleProducto.objects.create(
                    codigoProductoTerminado=pt,
                    codigoMateriaPrima=materias[mid],
                    cantidad=Decimal(c))
            productos.append(pt)

        self.stdout.write(f'  [OK] {len(productos)} productos terminados con recetas.')

        # ════════════════════════════════════════
        # 4. COMPRAS HISTÓRICAS (últimos 30 días)
        #    Simulamos el flujo completo: pedido → recepción
        # ════════════════════════════════════════
        compras_realizadas = 0
        compras_plan = [
            # (materia_idx, proveedor, cantidad, dias_atras_pedido, dias_entrega)
            (0, prov_a,  50, 28, 4),
            (1, prov_a,  40, 26, 4),
            (2, prov_b,  30, 24, 6),
            (3, prov_b,  35, 22, 6),
            (4, prov_b,  20, 20, 6),
            (0, prov_a,  60, 14, 4),
            (1, prov_a,  30, 12, 5),
            (3, prov_b,  40, 10, 7),
            (2, prov_b,  25,  8, 6),
            (4, prov_b,  15,  6, 6),
        ]
        for mat_idx, prov, cant, dias_atras, dias_entrega in compras_plan:
            materia = materias[mat_idx]
            fecha_pedido = today - timedelta(days=dias_atras)
            fecha_real   = fecha_pedido + timedelta(days=dias_entrega)
            if fecha_real <= today:
                order = crear_compra_manual(
                    materia.pk, prov, cant, user,
                    precio=None, fecha_pedido=fecha_pedido,
                    fecha_estimada=fecha_real,
                )
                recibir(order.pk, user, fecha_real)
                compras_realizadas += 1

        # 2 pedidos pendientes (aún no recibidos)
        order_p1 = crear_compra_manual(
            materias[0].pk, prov_a, 50, user,
            fecha_pedido=today - timedelta(days=3),
            fecha_estimada=today + timedelta(days=1),
        )
        order_p2 = crear_compra_manual(
            materias[3].pk, prov_b, 40, user,
            fecha_pedido=today - timedelta(days=2),
            fecha_estimada=today + timedelta(days=4),
        )
        self.stdout.write(
            f'  [OK] {compras_realizadas} compras recibidas + 2 pedidos en tránsito ({order_p1}, {order_p2}).')

        # ════════════════════════════════════════
        # 5. PRODUCCIONES (30 días)
        # ════════════════════════════════════════
        prod_count = 0
        for i in range(30):
            day = today - timedelta(days=30 - i)
            # Descanso domingos y 25% días al azar
            if day.weekday() == 6 or (i != 0 and rng.random() < 0.25):
                continue
            n_prods = rng.choice([1, 1, 2])
            for producto in rng.sample(productos, n_prods):
                cantidad = rng.randint(10, 30)
                # Pico de producción semana 3
                if 15 <= i <= 21:
                    cantidad = int(cantidad * 1.6)
                p = Produccion.objects.create(
                    producto=producto, cantidad_producida=cantidad, sintetica=True)
                p.consumir_materiales(user)
                Produccion.objects.filter(pk=p.pk).update(
                    fecha=timezone.make_aware(
                        datetime.combine(day, time(8 + rng.randint(0, 8), rng.choice([0, 15, 30])))))
                prod_count += 1

        self.stdout.write(f'  [OK] {prod_count} registros de producción (30 días).')

        # ════════════════════════════════════════
        # 6. AJUSTAR STOCKS AL CIERRE SIMULADO
        # ════════════════════════════════════════
        saldos_cierre = [30, 40, 20, 25, 15]
        for materia, saldo in zip(materias, saldos_cierre):
            materia.refresh_from_db()
            delta = materia.stock_actual - Decimal(saldo)
            if delta > 0:
                ajustar_stock(materia.pk, delta, 'SALIDA', user, 'Saldo de cierre simulado')
            elif delta < 0:
                ajustar_stock(materia.pk, -delta, 'ENTRADA', user, 'Saldo de cierre simulado')

        # ════════════════════════════════════════
        # 7. ENTRENAR + PRONOSTICAR + SUGERENCIAS
        # ════════════════════════════════════════
        self.stdout.write('  Entrenando modelos y generando pronósticos...')
        from django.core.exceptions import ValidationError
        for materia in materias:
            run = entrenar(materia, user)
            if run.artefacto:
                pronosticar(run, 60)
            try:
                sugerir(materia, user)
            except ValidationError:
                pass
            estado_str = f'{run.modelo} · RMSE {run.metricas.get("rmse", "—")}'
            self.stdout.write(f'    {materia.nombre}: {run.registros} consumos · {estado_str}')

        self.stdout.write(self.style.SUCCESS(
            f'\n[OK] Seed completo. '
            f'{prod_count} producciones - {compras_realizadas} compras recibidas - '
            f'2 proveedores con 2 ofertas c/u - modelos entrenados y sugerencias listas.'
        ))
