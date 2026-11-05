"""Pruebas adicionales del capítulo IV con resultados reproducibles."""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from math import ceil
from unittest.mock import patch

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserSession
from inventario.models import MateriaPrima, Proveedor
from inventario.abastecimiento_models import MateriaPrimaProveedor
from inventario.procurement import analizar
from produccion.forecast_models import Entrenamiento, Pronostico
from produccion.services.forecasting.preprocessing import preparar_filas


class CorteTemporalAmpliadoTest(SimpleTestCase):
    def test_cp09_cambiar_futuro_no_altera_pasado(self):
        inicio = date(2026, 1, 1)
        filas = [
            {'id': i + 1, 'cantidad_usada': 2, 'produccion__fecha':
             datetime.combine(inicio + timedelta(days=i), datetime.min.time(), dt_timezone.utc),
             'excluido_entrenamiento': i == 10}
            for i in range(30)
        ]
        original, _ = preparar_filas(filas, inicio + timedelta(days=30))
        cambiadas = [dict(fila) for fila in filas]
        cambiadas[25]['cantidad_usada'] = 200
        nuevo, _ = preparar_filas(cambiadas, inicio + timedelta(days=30))
        pd.testing.assert_series_equal(original.iloc[:25], nuevo.iloc[:25])
        self.assertNotEqual(original.iloc[25], nuevo.iloc[25])


class FlujosAmpliadosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            username='admin_ampliado', email='admin_ampliado@example.test',
            password='clave-prueba', rol='ADMINISTRADOR')
        cls.operador = get_user_model().objects.create_user(
            username='operador_ampliado', email='operador_ampliado@example.test',
            password='clave-prueba', rol='OPERADOR')

    def test_cp10_reposicion_con_referencia_independiente(self):
        materia = MateriaPrima.objects.create(
            codigo='INS-REF', nombre='Insumo referencia', unidad_medida='kg',
            stock_actual=Decimal('5'), cobertura_dias=7)
        proveedor = Proveedor.objects.create(nombre='Proveedor referencia')
        oferta = MateriaPrimaProveedor.objects.create(
            materia_prima=materia, proveedor=proveedor, precio=Decimal('2'),
            lead_time_dias=3, moq=Decimal('5'), multiplo=Decimal('4'))
        entrenamiento = Entrenamiento.objects.create(
            materia_prima=materia, estado='COMPLETADO', modelo='BASELINE')
        hoy = timezone.localdate()
        valores = [{'fecha': (hoy + timedelta(days=i)).isoformat(), 'consumo': 1}
                   for i in range(40)]
        pronostico = Pronostico.objects.create(
            materia_prima=materia, entrenamiento=entrenamiento,
            inicio=hoy, horizonte=40, valores=valores, total=Decimal('40'))
        with patch('produccion.services.forecasting.preprocessing.preparar',
                   return_value=(pd.Series([1.0] * 40), {})):
            resultado = analizar(materia, pronostico=pronostico, oferta=oferta)
        # Referencia manual: demanda 3 días = 3; objetivo 10;
        # faltante 10 - 5 = 5; se compra en múltiplos de 4: 8.
        self.assertEqual(resultado['seguridad'], 0)
        self.assertEqual(resultado['rop'], 3)
        self.assertEqual(resultado['objetivo'], 10)
        self.assertEqual(resultado['cantidad'], 8)
        self.assertEqual(resultado['fecha_rop'], hoy + timedelta(days=1))
        self.assertEqual(resultado['fecha_pedido'], hoy + timedelta(days=1))

    def test_cp11_cierre_administrativo_invalida_sesion(self):
        operador = Client()
        self.assertTrue(operador.login(username='operador_ampliado', password='clave-prueba'))
        self.assertEqual(operador.get(reverse('dashboard:home')).status_code, 200)
        sesion = UserSession.objects.get(user=self.operador, is_active=True)
        admin = Client()
        admin.force_login(self.admin)
        respuesta = admin.post(reverse('accounts:session_close', args=[sesion.pk]))
        sesion.refresh_from_db()
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(sesion.is_active)
        self.assertEqual(operador.get(reverse('dashboard:home')).status_code, 302)
