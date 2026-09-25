"""
Agrega 2 proveedores peruanos reales con datos simulados en Soles (S/)
y los vincula a todas las materias primas demo. Elimina/desactiva proveedores anteriores innecesarios.
Requiere OPERASTOCK_DEMO=1.
"""
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Crea 2 proveedores peruanos (Soles S/) y limpia proveedores demo antiguos.'

    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError('Requiere OPERASTOCK_DEMO=1.')

        from inventario.models import Proveedor, MateriaPrima, MateriaPrimaProveedor

        self.stdout.write('Limpiando y configurando proveedores peruanos...')

        # Desactivar o limpiar proveedores viejos genéricos
        Proveedor.objects.exclude(nombre__icontains='San Jorge').exclude(nombre__icontains='Corporación de Insumos').update(activo=False)

        # Proveedor 1: Distribuidora Agroindustrial San Jorge S.A.C.
        prov_a, created_a = Proveedor.objects.get_or_create(
            nombre='Distribuidora Agroindustrial San Jorge S.A.C.',
            defaults={
                'ruc': '20601234567',
                'telefono': '+51 987 654 321',
                'whatsapp': '51987654321',
                'correo': 'ventas@sanjorgeperu.com',
                'direccion': 'Av. Argentina 2450, Lima, Perú',
                'tiempo_entrega_dias': 3,
                'activo': True,
            }
        )
        if not created_a:
            prov_a.activo = True
            prov_a.ruc = '20601234567'
            prov_a.telefono = '+51 987 654 321'
            prov_a.whatsapp = '51987654321'
            prov_a.correo = 'ventas@sanjorgeperu.com'
            prov_a.direccion = 'Av. Argentina 2450, Lima, Perú'
            prov_a.tiempo_entrega_dias = 3
            prov_a.save()

        # Proveedor 2: Corporación de Insumos del Perú E.I.R.L.
        prov_b, created_b = Proveedor.objects.get_or_create(
            nombre='Corporación de Insumos del Perú E.I.R.L.',
            defaults={
                'ruc': '20509876543',
                'telefono': '+51 912 345 678',
                'whatsapp': '51912345678',
                'correo': 'contacto@insumosperu.com.pe',
                'direccion': 'Calle Mercaderes 112, Arequipa, Perú',
                'tiempo_entrega_dias': 5,
                'activo': True,
            }
        )
        if not created_b:
            prov_b.activo = True
            prov_b.ruc = '20509876543'
            prov_b.telefono = '+51 912 345 678'
            prov_b.whatsapp = '51912345678'
            prov_b.correo = 'contacto@insumosperu.com.pe'
            prov_b.direccion = 'Calle Mercaderes 112, Arequipa, Perú'
            prov_b.tiempo_entrega_dias = 5
            prov_b.save()

        self.stdout.write(f'  [OK] Proveedor 1: {prov_a.nombre} (Lima)')
        self.stdout.write(f'  [OK] Proveedor 2: {prov_b.nombre} (Arequipa)')

        # Tarifario de ofertas en Soles (S/)
        precios_peru = {
            'Harina de maíz': (Decimal('3.50'), Decimal('3.80')),
            'Avena': (Decimal('4.20'), Decimal('4.50')),
            'Miel': (Decimal('18.50'), Decimal('19.20')),
            'Esencia de Vainilla': (Decimal('25.00'), Decimal('27.00')),
            'Chispas de Chocolate': (Decimal('14.50'), Decimal('15.80')),
        }

        materias = MateriaPrima.objects.all()
        for mp in materias:
            p1, p2 = precios_peru.get(mp.nombre, (Decimal('5.00'), Decimal('5.50')))
            
            # Oferta principal con San Jorge
            off1, _ = MateriaPrimaProveedor.objects.update_or_create(
                materia_prima=mp,
                proveedor=prov_a,
                defaults={
                    'precio': p1,
                    'lead_time_dias': 3,
                    'moq': Decimal('20.00'),
                    'multiplo': Decimal('5.00'),
                    'presentacion': 'Saco / Envase industrial',
                    'activo': True
                }
            )
            # Oferta alternativa con Corp Insumos Perú
            off2, _ = MateriaPrimaProveedor.objects.update_or_create(
                materia_prima=mp,
                proveedor=prov_b,
                defaults={
                    'precio': p2,
                    'lead_time_dias': 5,
                    'moq': Decimal('15.00'),
                    'multiplo': Decimal('5.00'),
                    'presentacion': 'Caja / Galón',
                    'activo': True
                }
            )

            # Asignar proveedor principal a la materia prima si no tiene
            mp.proveedor = prov_a
            mp.save(update_fields=['proveedor'])

            self.stdout.write(f'  [OK] Materia {mp.nombre}: San Jorge S/{p1} | Corp Insumos S/{p2}')

        self.stdout.write(self.style.SUCCESS('\nProveedores simulados de Perú (Soles S/) configurados con éxito.'))
