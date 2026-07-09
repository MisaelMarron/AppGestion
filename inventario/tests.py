from django.core.management import call_command
from django.test import TestCase

from inventario.models import MateriaPrima, ProductoTerminado
from produccion.models import FormulaProducto


class SeedProductosDemoTest(TestCase):
    def test_seed_crea_productos_y_formulas(self):
        call_command('seed_productos_demo')

        self.assertTrue(ProductoTerminado.objects.filter(nombre='Galleta de Maíz').exists())
        self.assertTrue(MateriaPrima.objects.filter(nombre='Harina de maíz').exists())
        self.assertEqual(ProductoTerminado.objects.count(), 4)
        self.assertGreaterEqual(FormulaProducto.objects.count(), 4)
