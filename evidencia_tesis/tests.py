"""Casos reproducibles del capítulo IV; usan la base temporal de Django."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from django.urls import reverse

from inventario.abastecimiento_models import DetalleOrdenCompra, MateriaPrimaProveedor, OrdenCompra, SugerenciaCompra
from inventario.models import MateriaPrima, MovimientoInventario, ProductoTerminado, Proveedor
from inventario.services import ajustar_stock
from inventario.procurement import recibir
from produccion.forecast_models import Entrenamiento, Pronostico
from produccion.services.forecasting.evaluation import metricas, seleccionar
from produccion.services.forecasting.preprocessing import preparar_filas
from produccion.services.forecasting.models import ajustar, predecir
from produccion.models import ConsumoMateriaPrima, DetalleProducto, Produccion
from produccion.services.operaciones import ejecutar_produccion


class CalculosTesisTest(SimpleTestCase):
    def test_cp04_metricas_con_cero(self):
        result = metricas([2, 0, 4], [1, 1, 5])
        self.assertEqual(result['mae'], 1)
        self.assertEqual(result['rmse'], 1)
        self.assertEqual(result['mape'], 37.5)
        self.assertEqual(result['ceros_excluidos_mape'], 1)

    def test_cp04_seleccion_por_rmse_y_mae(self):
        runs = [
            {'modelo': 'A', 'metricas': {'rmse': 2, 'mae': 1}},
            {'modelo': 'B', 'metricas': {'rmse': 1, 'mae': 2}},
            {'modelo': 'C', 'metricas': {'rmse': 1, 'mae': 1}},
            {'modelo': 'FALLIDO', 'metricas': None},
        ]
        self.assertEqual(seleccionar(runs)['modelo'], 'C')

    def test_cp04_corte_temporal_y_dias_vacios(self):
        rows = [
            {'id': 1, 'cantidad_usada': 2, 'produccion__fecha': '2026-01-01T12:00:00-05:00', 'excluido_entrenamiento': False},
            {'id': 1, 'cantidad_usada': 2, 'produccion__fecha': '2026-01-01T12:00:00-05:00', 'excluido_entrenamiento': False},
            {'id': 2, 'cantidad_usada': 99, 'produccion__fecha': '2026-01-04T12:00:00-05:00', 'excluido_entrenamiento': False},
        ]
        series, log = preparar_filas(rows, date(2026, 1, 4))
        self.assertEqual(series.tolist(), [2, 0, 0])
        self.assertEqual(log['duplicados_id'], 1)

    def test_cp05_historial_sintetico_120_dias(self):
        inicio = date(2026, 7, 7)
        rows = [
            {'id': i + 1, 'cantidad_usada': 0 if (inicio + timedelta(days=i)).weekday() == 6 else 2 + i % 4,
             'produccion__fecha': (inicio + timedelta(days=i)).isoformat() + 'T12:00:00-05:00',
             'excluido_entrenamiento': False}
            for i in range(120)
        ]
        serie, _ = preparar_filas(rows, inicio + timedelta(days=120))
        self.assertEqual(len(serie), 120)
        train, test = serie.iloc[:96], serie.iloc[96:]
        fitted, _ = ajustar('Promedio móvil', train)
        result = metricas(test, predecir('Promedio móvil', fitted, train, len(test)))
        self.assertEqual(len(test), 24)
        self.assertGreaterEqual(result['mae'], 0)


class FlujosTesisTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            username='admin_tesis', email='admin_tesis@example.test', password='x', rol='ADMINISTRADOR')
        cls.operador = get_user_model().objects.create_user(
            username='operador_tesis', email='operador_tesis@example.test', password='x', rol='OPERADOR')
        cls.materia = MateriaPrima.objects.create(nombre='Harina tesis', codigo='HAR-T', unidad_medida='kg', stock_actual=Decimal('10'), stock_minimo=Decimal('5'))
        cls.proveedor = Proveedor.objects.create(nombre='Proveedor tesis')
        cls.oferta = MateriaPrimaProveedor.objects.create(materia_prima=cls.materia, proveedor=cls.proveedor, precio=Decimal('2'), lead_time_dias=3)
        cls.entrenamiento = Entrenamiento.objects.create(materia_prima=cls.materia, estado='COMPLETADO', modelo='BASELINE')
        hoy = timezone.localdate()
        valores = [{'fecha': (hoy + timedelta(days=i)).isoformat(), 'consumo': 1} for i in range(3)]
        cls.pronostico = Pronostico.objects.create(materia_prima=cls.materia, entrenamiento=cls.entrenamiento, inicio=hoy, horizonte=3, valores=valores, total=Decimal('3'))

    def test_cp03_salida_excesiva_no_cambia_stock(self):
        with self.assertRaises(ValidationError):
            ajustar_stock(self.materia.pk, 11, 'SALIDA', self.admin)
        self.materia.refresh_from_db()
        self.assertEqual(self.materia.stock_actual, 10)
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_cp03_entrada_y_salida_trazables(self):
        ajustar_stock(self.materia.pk, 5, 'ENTRADA', self.admin)
        ajustar_stock(self.materia.pk, 2, 'SALIDA', self.admin)
        self.materia.refresh_from_db()
        self.assertEqual(self.materia.stock_actual, 13)
        self.assertCountEqual(list(MovimientoInventario.objects.values_list('tipo', flat=True)), ['ENTRADA', 'SALIDA'])

    def test_cp02_consumo_receta_y_prevencion_duplicado(self):
        azucar = MateriaPrima.objects.create(nombre='Azúcar tesis', codigo='AZ-T', stock_actual=Decimal('4'), unidad_medida='kg')
        producto = ProductoTerminado.objects.create(nombre='Galleta tesis', codigo='PT-T', unidad_medida='kg')
        DetalleProducto.objects.create(codigoProductoTerminado=producto, codigoMateriaPrima=self.materia, cantidad=Decimal('0.6'))
        DetalleProducto.objects.create(codigoProductoTerminado=producto, codigoMateriaPrima=azucar, cantidad=Decimal('0.4'))
        p = Produccion.objects.create(producto=producto, cantidad_producida=Decimal('10'))
        ejecutar_produccion(p.pk, self.admin)
        self.materia.refresh_from_db(); azucar.refresh_from_db()
        self.assertEqual((self.materia.stock_actual, azucar.stock_actual), (4, 0))
        self.assertEqual(ConsumoMateriaPrima.objects.filter(produccion=p).count(), 2)
        with self.assertRaises(ValidationError):
            ejecutar_produccion(p.pk, self.admin)
        self.assertEqual(ConsumoMateriaPrima.objects.filter(produccion=p).count(), 2)

    def test_cp02_stock_insuficiente_no_deja_consumo_parcial(self):
        producto = ProductoTerminado.objects.create(nombre='Galleta tesis', codigo='PT-T', unidad_medida='kg')
        DetalleProducto.objects.create(codigoProductoTerminado=producto, codigoMateriaPrima=self.materia, cantidad=Decimal('2'))
        p = Produccion.objects.create(producto=producto, cantidad_producida=Decimal('10'))
        with self.assertRaises(ValidationError):
            ejecutar_produccion(p.pk, self.admin)
        self.materia.refresh_from_db()
        self.assertEqual(self.materia.stock_actual, 10)
        self.assertFalse(ConsumoMateriaPrima.objects.filter(produccion=p).exists())

    def test_cp08_operador_no_puede_rechazar_sugerencia(self):
        s = SugerenciaCompra.objects.create(materia_prima=self.materia, oferta=self.oferta, pronostico=self.pronostico, cantidad=Decimal('5'))
        self.client.force_login(self.operador)
        self.client.post(reverse('produccion:decision', args=[s.pk, 'rechazar']))
        s.refresh_from_db()
        self.assertEqual(s.estado, 'PENDIENTE')

    def test_cp07_rechazo_conserva_trazabilidad(self):
        s = SugerenciaCompra.objects.create(materia_prima=self.materia, oferta=self.oferta, pronostico=self.pronostico, cantidad=Decimal('5'))
        self.client.force_login(self.admin)
        self.client.post(reverse('produccion:decision', args=[s.pk, 'rechazar']))
        self.assertEqual(SugerenciaCompra.objects.get(pk=s.pk).estado, 'RECHAZADA')

    def test_cp07_cantidad_editada_pasa_a_orden(self):
        calculo = {
            'cantidad': 5, 'oferta_id': self.oferta.pk, 'pronostico_id': self.pronostico.pk,
            'disponible': 10, 'utilizable': 10, 'transito': 0, 'rop': 12,
            'fecha_pedido': '2026-01-01', 'precio': 2, 'moq': 0,
            'multiplo': 1, 'lead_time': 3,
        }
        s = SugerenciaCompra.objects.create(materia_prima=self.materia, oferta=self.oferta,
            pronostico=self.pronostico, cantidad=Decimal('5'), calculo=calculo)
        self.client.force_login(self.admin)
        self.client.post(reverse('produccion:editar_cantidad_sugerencia', args=[s.pk]), {'cantidad_editada': '7'})
        with patch('inventario.procurement.analizar', return_value=calculo):
            self.client.post(reverse('produccion:decision', args=[s.pk, 'aprobar']))
        s.refresh_from_db()
        self.assertEqual(s.estado, 'APROBADA')
        self.assertEqual(OrdenCompra.objects.filter(sugerencia=s).count(), 1)
        self.assertEqual(DetalleOrdenCompra.objects.get(orden__sugerencia=s).cantidad, 7)

    def test_cp07_recepcion_unica(self):
        order = OrdenCompra.objects.create(proveedor=self.proveedor, usuario=self.admin,
            fecha_estimada=timezone.localdate() + timedelta(days=3))
        DetalleOrdenCompra.objects.create(orden=order, oferta=self.oferta, cantidad=Decimal('5'), precio=Decimal('2'))
        recibir(order.pk, self.admin)
        self.materia.refresh_from_db()
        self.assertEqual(self.materia.stock_actual, 15)
        with self.assertRaises(ValidationError):
            recibir(order.pk, self.admin)
        self.materia.refresh_from_db()
        self.assertEqual(self.materia.stock_actual, 15)

    def test_cp06_interfaz_no_publica_metricas_inventadas(self):
        self.client.force_login(self.operador)
        response = self.client.get(reverse('produccion:analisis', args=[self.materia.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Comparativa de los 4 Modelos Predictivos')
        self.assertNotContains(response, '92.5%')
        self.assertNotContains(response, 'RMSE')

    def test_cp06_csv_sin_entrenamiento_no_inventa_precision(self):
        self.pronostico.delete()
        self.entrenamiento.delete()
        self.client.force_login(self.admin)
        response = self.client.get(reverse('produccion:exportar_csv_analisis', args=[self.materia.pk]))
        self.assertEqual(response.status_code, 200)
        csv = response.content.decode('utf-8-sig')
        for fabricated in ('93.2%', '78.5%', '86.4%'):
            self.assertNotIn(fabricated, csv)
