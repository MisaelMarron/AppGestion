from decimal import Decimal

from django.core.management.base import BaseCommand

from inventario.models import MateriaPrima, ProductoTerminado
from produccion.models import ConsumoMateriaPrima, DetalleFormula, DetalleProducto, FormulaProducto, Produccion


class Command(BaseCommand):
    help = 'Crea productos de prueba con fórmulas, precios y producción de ejemplo.'

    def handle(self, *args, **options):
        productos = [
            {
                'codigo': 'GMAZ-001',
                'nombre': 'Galleta de Maíz',
                'descripcion': 'Producto de prueba con fórmula base.',
                'unidad_medida': 'unidad',
                'stock_actual': Decimal('50'),
                'precio': Decimal('2.50'),
                'formula': [
                    ('Harina de maíz', Decimal('0.50')),
                    ('Azúcar', Decimal('0.10')),
                    ('Sal', Decimal('0.02')),
                ],
            },
            {
                'codigo': 'BAV-002',
                'nombre': 'Biscocho de Avena',
                'descripcion': 'Producto de prueba con avena y miel.',
                'unidad_medida': 'unidad',
                'stock_actual': Decimal('40'),
                'precio': Decimal('3.20'),
                'formula': [
                    ('Avena', Decimal('0.60')),
                    ('Azúcar', Decimal('0.15')),
                    ('Miel', Decimal('0.05')),
                ],
            },
            {
                'codigo': 'BCE-003',
                'nombre': 'Barra de Cereal',
                'descripcion': 'Producto de prueba para mezcla de cereal.',
                'unidad_medida': 'unidad',
                'stock_actual': Decimal('35'),
                'precio': Decimal('4.00'),
                'formula': [
                    ('Harina de maíz', Decimal('0.40')),
                    ('Avena', Decimal('0.30')),
                    ('Miel', Decimal('0.10')),
                ],
            },
            {
                'codigo': 'MPA-004',
                'nombre': 'Mini Pan',
                'descripcion': 'Producto de prueba tipo pan pequeño.',
                'unidad_medida': 'unidad',
                'stock_actual': Decimal('30'),
                'precio': Decimal('2.80'),
                'formula': [
                    ('Harina de maíz', Decimal('0.45')),
                    ('Azúcar', Decimal('0.08')),
                    ('Sal', Decimal('0.03')),
                ],
            },
        ]

        materias = {}
        for nombre, codigo in {
            'Harina de maíz': 'MAT-001',
            'Azúcar': 'MAT-002',
            'Sal': 'MAT-003',
            'Avena': 'MAT-004',
            'Miel': 'MAT-005',
        }.items():
            materia, _ = MateriaPrima.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre': nombre,
                    'descripcion': f'Materia prima de prueba: {nombre}',
                    'unidad_medida': 'kg',
                    'stock_actual': Decimal('100'),
                    'stock_minimo': Decimal('10'),
                    'costo_unitario': Decimal('1.00'),
                },
            )
            if materia.nombre != nombre:
                materia.nombre = nombre
                materia.save(update_fields=['nombre'])
            materias[nombre] = materia

        for payload in productos:
            producto, _ = ProductoTerminado.objects.get_or_create(
                codigo=payload['codigo'],
                defaults={
                    'nombre': payload['nombre'],
                    'descripcion': payload['descripcion'],
                    'unidad_medida': payload['unidad_medida'],
                    'stock_actual': payload['stock_actual'],
                    'precio': payload['precio'],
                    'activo': True,
                },
            )
            if Produccion.objects.filter(producto=producto).exists():
                continue  # No borrar consumos ni restablecer existencias de productos ya usados.
            producto.nombre = payload['nombre']
            producto.descripcion = payload['descripcion']
            producto.unidad_medida = payload['unidad_medida']
            producto.stock_actual = payload['stock_actual']
            producto.precio = payload['precio']
            producto.activo = True
            producto.save()

            formula, _ = FormulaProducto.objects.get_or_create(
                producto_terminado=producto,
                defaults={
                    'nombre': f'Fórmula {producto.nombre}',
                    'cantidad_resultante': Decimal('1'),
                    'activo': True,
                },
            )
            if formula.nombre != f'Fórmula {producto.nombre}':
                formula.nombre = f'Fórmula {producto.nombre}'
                formula.save(update_fields=['nombre'])

            DetalleFormula.objects.filter(formula=formula).delete()
            DetalleProducto.objects.filter(codigoProductoTerminado=producto).delete()
            for nombre, cantidad in payload['formula']:
                DetalleFormula.objects.create(
                    formula=formula,
                    materia_prima=materias[nombre],
                    cantidad_requerida=cantidad,
                )
                DetalleProducto.objects.create(
                    codigoMateriaPrima=materias[nombre],
                    codigoProductoTerminado=producto,
                    cantidad=cantidad,
                )

            produccion = Produccion.objects.create(
                producto=producto,
                cantidad_producida=Decimal('10'),
                sintetica=True,
            )
            produccion.consumir_materiales()

        self.stdout.write(self.style.SUCCESS('Productos de prueba creados correctamente.'))
