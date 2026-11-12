"""Pruebas de regresión de los casos formales CP-01 a CP-12."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserSession
from inventario.abastecimiento_models import (
    DetalleOrdenCompra, LoteMateriaPrima, MateriaPrimaProveedor, OrdenCompra,
    ReservaInventario, LeadTimeReal,
)
from inventario.models import MateriaPrima, MovimientoInventario, ProductoTerminado, Proveedor
from inventario.procurement import analizar, redondear_compra, recibir
from inventario.services import ajustar_stock, utilizable
from produccion.forecast_models import Entrenamiento, Pronostico
from produccion.models import DetalleProducto, OrdenProduccion, Produccion
from produccion.services.forecasting.prediction import pronosticar
from produccion.services.forecasting.training import entrenar
from produccion.services.forecasting.preprocessing import preparar_filas
from produccion.services.operaciones import ejecutar_orden, reservar_orden
from evidencia_tesis.politicas import simular


class SerieTemporalIntegralTest(SimpleTestCase):
    def test_cp09_cambio_futuro_no_altera_pasado(self):
        inicio = date(2026, 7, 1)
        rows = [
            {'id': i + 1, 'cantidad_usada': 2 + i % 3,
             'produccion__fecha': (inicio + timedelta(days=i)).isoformat() + 'T12:00:00-05:00',
             'excluido_entrenamiento': False}
            for i in range(30)
        ]
        original, _ = preparar_filas(rows, inicio + timedelta(days=30))
        rows[25]['cantidad_usada'] = 1000
        alterada, _ = preparar_filas(rows, inicio + timedelta(days=30))
        self.assertEqual(original.iloc[:25].tolist(), alterada.iloc[:25].tolist())
        self.assertNotEqual(original.iloc[25], alterada.iloc[25])

    def test_cp04_exclusion_y_registro_invalido_no_contaminan_serie(self):
        rows = [
            {'id': 1, 'cantidad_usada': 4, 'produccion__fecha': '2026-07-01T12:00:00-05:00', 'excluido_entrenamiento': False},
            {'id': 2, 'cantidad_usada': 99, 'produccion__fecha': '2026-07-02T12:00:00-05:00', 'excluido_entrenamiento': True},
            {'id': 3, 'cantidad_usada': -3, 'produccion__fecha': '2026-07-03T12:00:00-05:00', 'excluido_entrenamiento': False},
        ]
        serie, calidad = preparar_filas(rows, date(2026, 7, 4))
        self.assertEqual(serie.tolist(), [4, 4, 0])
        self.assertEqual(calidad['invalidos'], 1)
        self.assertEqual(calidad['excluidos'], 1)

    def test_cp04_excluido_no_borra_consumo_valido_del_mismo_dia(self):
        rows = [
            {'id': 1, 'cantidad_usada': 4, 'produccion__fecha': '2026-07-01T12:00:00-05:00', 'excluido_entrenamiento': False},
            {'id': 2, 'cantidad_usada': 3, 'produccion__fecha': '2026-07-02T12:00:00-05:00', 'excluido_entrenamiento': False},
            {'id': 3, 'cantidad_usada': 99, 'produccion__fecha': '2026-07-02T14:00:00-05:00', 'excluido_entrenamiento': True},
        ]
        serie, calidad = preparar_filas(rows, date(2026, 7, 3))
        self.assertEqual(serie.tolist(), [4, 3])
        self.assertEqual(calidad['excluidos'], 1)

    def test_cp10_redondeo_moq_y_multiplo(self):
        self.assertEqual(redondear_compra(Decimal('5.1'), Decimal('5'), Decimal('4')), Decimal('8'))
        self.assertEqual(redondear_compra(Decimal('0'), Decimal('5'), Decimal('4')), Decimal('0'))

    def test_cp12_simulacion_usa_demanda_y_costos_iguales(self):
        real = [2] * 6
        previsto = [2] * 12
        params = dict(plazo=2, cobertura=2, inventario_inicial=4, precio=3,
                      moq=0, multiplo=1, costo_pedido=1,
                      costo_mantenimiento=0.1, costo_faltante=5)
        a = simular(real, previsto, **params)
        b = simular(real, previsto, **params)
        self.assertEqual(a, b)
        self.assertEqual(a['demanda_total'], 12)
        self.assertEqual(a['atendida'] + a['faltante'], 12)
        self.assertAlmostEqual(a['costo_simulado'], a['compras'] * 3 + a['ordenes'] + a['faltante'] * 5 + a['inventario_medio'] * len(real) * 0.1)


class FlujosIntegralesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(username='admin_integral', email='admin_integral@example.test', password='ClaveSegura123!', rol='ADMINISTRADOR')
        cls.operador = User.objects.create_user(username='operador_integral', email='operador_integral@example.test', password='ClaveSegura123!', rol='OPERADOR')
        cls.proveedor = Proveedor.objects.create(nombre='Proveedor integral')
        cls.materia = MateriaPrima.objects.create(nombre='Harina integral', codigo='HAR-INT', unidad_medida='kg', stock_actual=Decimal('10'), stock_minimo=Decimal('5'))
        cls.oferta = MateriaPrimaProveedor.objects.create(materia_prima=cls.materia, proveedor=cls.proveedor, precio=Decimal('2'), lead_time_dias=3, moq=Decimal('5'), multiplo=Decimal('4'))

    def test_cp01_registro_login_rol_y_cierre(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'nuevo_operador', 'email': 'nuevo@example.test', 'password1': 'ClaveSegura123!',
            'password2': 'ClaveSegura123!', 'rol': 'ADMINISTRADOR',
        })
        self.assertEqual(response.status_code, 302)
        nuevo = get_user_model().objects.get(username='nuevo_operador')
        self.assertEqual(nuevo.rol, 'OPERADOR')
        self.client.get(reverse('dashboard:home'))
        self.assertTrue(UserSession.objects.filter(user=nuevo, is_active=True).exists())
        self.client.get(reverse('accounts:logout'))
        self.assertFalse(UserSession.objects.filter(user=nuevo, is_active=True).exists())
        bad = self.client.post(reverse('accounts:login'), {'username': 'nuevo_operador', 'password': 'errónea'})
        self.assertEqual(bad.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_cp01_cambio_rol_y_bloqueo_operador(self):
        self.client.force_login(self.operador)
        self.client.post(reverse('accounts:user_change_role', args=[self.operador.pk]), {'rol': 'ADMINISTRADOR'})
        self.operador.refresh_from_db()
        self.assertEqual(self.operador.rol, 'OPERADOR')
        self.client.force_login(self.admin)
        self.client.post(reverse('accounts:user_change_role', args=[self.operador.pk]), {'rol': 'ADMINISTRADOR'})
        self.operador.refresh_from_db()
        self.assertEqual(self.operador.rol, 'ADMINISTRADOR')

    def test_cp01_catalogos_proveedor_y_producto_por_http(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('inventario:proveedor_create'), {
            'nombre': 'Proveedor nuevo', 'tiempo_entrega_dias': '4',
        })
        self.assertEqual(response.status_code, 302)
        proveedor = Proveedor.objects.get(nombre='Proveedor nuevo')
        self.client.post(reverse('inventario:proveedor_edit', args=[proveedor.pk]), {
            'nombre': 'Proveedor actualizado', 'tiempo_entrega_dias': '5',
        })
        proveedor.refresh_from_db()
        self.assertEqual(proveedor.tiempo_entrega_dias, 5)
        response = self.client.post(reverse('inventario:producto_terminado_create'), {
            'nombre': 'Producto nuevo', 'codigo': 'PT-NUEVO', 'unidad_medida': 'kg', 'precio': '3',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProductoTerminado.objects.filter(codigo='PT-NUEVO').exists())
        self.client.post(reverse('inventario:proveedor_delete', args=[proveedor.pk]))
        proveedor.refresh_from_db()
        self.assertFalse(proveedor.activo)

    def test_cp02_previsualizacion_y_confirmacion_http(self):
        azucar = MateriaPrima.objects.create(nombre='Azúcar integral', codigo='AZ-INT', stock_actual=Decimal('40'), unidad_medida='kg')
        producto = ProductoTerminado.objects.create(nombre='Galleta integral', codigo='PT-INT', unidad_medida='kg')
        DetalleProducto.objects.create(codigoProductoTerminado=producto, codigoMateriaPrima=self.materia, cantidad=Decimal('0.6'))
        DetalleProducto.objects.create(codigoProductoTerminado=producto, codigoMateriaPrima=azucar, cantidad=Decimal('0.4'))
        self.materia.stock_actual = Decimal('100'); self.materia.save()
        self.client.force_login(self.admin)
        response = self.client.post(reverse('produccion:produccion_form'), {'producto': producto.pk, 'cantidad': '10', 'unidades_producidas': '100'})
        self.assertEqual(response.status_code, 302)
        preview = self.client.get(reverse('produccion:produccion_preview'))
        self.assertEqual(preview.status_code, 200)
        self.assertEqual([x['requerido'] for x in preview.context['lineas']], [Decimal('6.00000'), Decimal('4.00000')])
        self.client.post(reverse('produccion:produccion_confirmar'))
        self.client.post(reverse('produccion:produccion_confirmar'))
        self.materia.refresh_from_db(); azucar.refresh_from_db()
        self.assertEqual((self.materia.stock_actual, azucar.stock_actual), (94, 36))
        self.assertEqual(Produccion.objects.filter(producto=producto, ejecutada=True).count(), 1)

    def test_cp03_reserva_ejecucion_y_lote_vencido(self):
        hoy = timezone.localdate()
        self.materia.gestionar_lotes = True; self.materia.save()
        LoteMateriaPrima.objects.create(materia_prima=self.materia, numero='VENCIDO', cantidad_inicial=Decimal('3'), cantidad_disponible=Decimal('3'), fecha_recepcion=hoy-timedelta(days=10), fecha_vencimiento=hoy-timedelta(days=1))
        vigente = LoteMateriaPrima.objects.create(materia_prima=self.materia, numero='VIGENTE', cantidad_inicial=Decimal('7'), cantidad_disponible=Decimal('7'), fecha_recepcion=hoy-timedelta(days=2), fecha_vencimiento=hoy+timedelta(days=5))
        self.assertEqual(utilizable(self.materia), 7)
        producto = ProductoTerminado.objects.create(nombre='Galleta lote', codigo='PT-LOT', unidad_medida='kg')
        DetalleProducto.objects.create(codigoProductoTerminado=producto, codigoMateriaPrima=self.materia, cantidad=Decimal('1'))
        orden = OrdenProduccion.objects.create(producto_terminado=producto, cantidad_producida=Decimal('5'), usuario=self.admin)
        reservar_orden(orden.pk, self.admin)
        self.assertEqual(ReservaInventario.objects.get(orden=orden).cantidad, 5)
        self.assertEqual(utilizable(self.materia), 2)
        ejecutar_orden(orden.pk, self.admin)
        orden.refresh_from_db(); vigente.refresh_from_db(); self.materia.refresh_from_db()
        self.assertEqual(orden.estado, 'COMPLETADA')
        self.assertFalse(ReservaInventario.objects.get(orden=orden).activa)
        self.assertEqual(vigente.cantidad_disponible, 2)
        self.assertEqual(self.materia.stock_actual, 5)

    def test_cp03_ajuste_de_stock_deja_historial(self):
        ajustar_stock(self.materia.pk, Decimal('2'), 'ENTRADA', self.admin, 'Ajuste de conteo')
        self.materia.refresh_from_db()
        self.assertEqual(self.materia.stock_actual, 12)
        self.assertEqual(MovimientoInventario.objects.get(materia_prima=self.materia).descripcion, 'Ajuste de conteo')

    def test_cp01_existencia_inicial_trazable_por_entrada(self):
        nueva = MateriaPrima.objects.create(nombre='Insumo inicial', codigo='INI-INT', unidad_medida='kg')
        ajustar_stock(nueva.pk, Decimal('12'), 'ENTRADA', self.admin, 'Saldo inicial')
        nueva.refresh_from_db()
        self.assertEqual(nueva.stock_actual, 12)
        self.assertEqual(MovimientoInventario.objects.get(materia_prima=nueva).descripcion, 'Saldo inicial')

    def test_cp05_horizonte_y_artefacto_invalido(self):
        run = Entrenamiento.objects.create(materia_prima=self.materia, estado='MODELO_DISPONIBLE', modelo='Promedio móvil', fin=timezone.localdate()-timedelta(days=1), artefacto='inexistente.joblib')
        with self.assertRaises(ValidationError):
            pronosticar(run, 366)
        with self.assertRaises(ValidationError):
            pronosticar(run, 30)
        self.assertEqual(Pronostico.objects.filter(entrenamiento=run).count(), 0)

    def test_cp05_entrenamiento_y_pronostico_real_con_40_dias(self):
        from produccion.models import ConsumoMateriaPrima
        producto = ProductoTerminado.objects.create(nombre='Producto serie', codigo='PT-SER', unidad_medida='kg')
        hoy = timezone.localdate()
        for i in range(40):
            p = Produccion.objects.create(producto=producto, cantidad_producida=Decimal('1'))
            Produccion.objects.filter(pk=p.pk).update(fecha=timezone.make_aware(
                datetime.combine(hoy - timedelta(days=40 - i), time(12))))
            ConsumoMateriaPrima.objects.create(produccion=p, materia_prima=self.materia, cantidad_usada=Decimal(2+i%3))
        with TemporaryDirectory() as model_dir, override_settings(MODEL_STORAGE=model_dir):
            run = entrenar(self.materia, self.admin)
            self.assertEqual(run.registros, 40)
            self.assertTrue(run.artefacto)
            forecast = pronosticar(run, 7)
            self.assertEqual(len(forecast.valores), 7)
            self.assertEqual(forecast.inicio, hoy)
            from pathlib import Path
            Path(model_dir, run.artefacto).write_bytes(b'alterado')
            with self.assertRaises(ValidationError):
                pronosticar(run, 7)

    def test_cp06_sin_pronostico_no_inventa_riesgo(self):
        result = analizar(self.materia)
        self.assertEqual(result['riesgo'], 'SIN_DATOS')
        self.assertEqual(result['cantidad'], 0)
        self.client.force_login(self.operador)
        response = self.client.get(reverse('produccion:analisis', args=[self.materia.pk]))
        self.assertContains(response, 'SIN DATOS')

    def test_cp06_estados_de_riesgo_siguen_stock_y_cobertura(self):
        hoy = timezone.localdate()
        self.materia.cobertura_dias = 7; self.materia.save()
        run = Entrenamiento.objects.create(materia_prima=self.materia, estado='COMPLETADO', modelo='BASELINE')
        values = [{'fecha': (hoy+timedelta(days=i)).isoformat(), 'consumo': 1} for i in range(20)]
        forecast = Pronostico.objects.create(materia_prima=self.materia, entrenamiento=run, inicio=hoy, horizonte=20, valores=values, total=Decimal('20'))
        for stock, expected in [(Decimal('0'), 'CRITICO'), (Decimal('5'), 'ATENCION'), (Decimal('50'), 'ESTABLE')]:
            self.materia.stock_actual = stock; self.materia.save()
            self.assertEqual(analizar(self.materia, forecast)['riesgo'], expected)
            self.assertEqual(self.materia.necesita_reposicion(), stock <= self.materia.stock_minimo)

    def test_cp07_reserva_y_llegada_tardia_no_reducen_compra(self):
        hoy = timezone.localdate()
        run = Entrenamiento.objects.create(materia_prima=self.materia, estado='COMPLETADO', modelo='BASELINE')
        self.materia.cobertura_dias = 7; self.materia.save()
        values = [{'fecha': (hoy+timedelta(days=i)).isoformat(), 'consumo': 1} for i in range(20)]
        forecast = Pronostico.objects.create(materia_prima=self.materia, entrenamiento=run, inicio=hoy, horizonte=20, valores=values, total=Decimal('20'))
        base = analizar(self.materia, forecast)
        order = OrdenCompra.objects.create(proveedor=self.proveedor, usuario=self.admin, fecha_estimada=hoy+timedelta(days=20))
        DetalleOrdenCompra.objects.create(orden=order, oferta=self.oferta, cantidad=Decimal('5'), precio=Decimal('2'))
        late = analizar(self.materia, forecast)
        self.assertEqual(base['cantidad'], late['cantidad'])
        producto = ProductoTerminado.objects.create(nombre='Reserva integral', codigo='PT-RES', unidad_medida='kg')
        DetalleProducto.objects.create(codigoProductoTerminado=producto, codigoMateriaPrima=self.materia, cantidad=Decimal('1'))
        op = OrdenProduccion.objects.create(producto_terminado=producto, cantidad_producida=Decimal('2'), usuario=self.admin)
        reservar_orden(op.pk, self.admin)
        reserved = analizar(self.materia, forecast)
        self.assertEqual(reserved['reservado'], 2)
        self.assertGreaterEqual(reserved['cantidad'], late['cantidad'])

    def test_cp08_panel_cuenta_registros_y_operador_no_entrena(self):
        self.client.force_login(self.operador)
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.context['total_materias_primas'], 1)
        self.assertEqual(response.context['total_proveedores'], 1)
        self.assertEqual(response.context['producciones_total'], 0)
        self.client.post(reverse('produccion:accion_analisis', args=[self.materia.pk, 'entrenar']))
        self.assertEqual(Entrenamiento.objects.count(), 0)

    def test_cp08_navegacion_basica_y_acceso_administrativo(self):
        self.client.force_login(self.operador)
        for name in ('dashboard:home', 'inventario:materia_prima_list', 'inventario:proveedor_list',
                     'inventario:producto_terminado_list', 'produccion:formula_list',
                     'produccion:historial', 'produccion:panel', 'produccion:compras',
                     'produccion:planes', 'produccion:lotes', 'produccion:produccion_list'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertNotEqual(self.client.get(reverse('accounts:user_list')).status_code, 200)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('accounts:user_list')).status_code, 200)

    def test_cp07_recepcion_registra_plazo_real(self):
        hoy = timezone.localdate()
        order = OrdenCompra.objects.create(proveedor=self.proveedor, usuario=self.admin,
                                          fecha_pedido=hoy-timedelta(days=2), fecha_estimada=hoy)
        detalle = DetalleOrdenCompra.objects.create(orden=order, oferta=self.oferta, cantidad=Decimal('4'), precio=Decimal('2'))
        recibir(order.pk, self.admin, hoy)
        self.assertEqual(LeadTimeReal.objects.get(detalle=detalle).dias, 2)
        self.assertEqual(OrdenCompra.objects.get(pk=order.pk).fecha_recepcion, hoy)

    def test_cp10_reposicion_manual_ss_rop_objetivo_y_fecha(self):
        hoy = timezone.localdate()
        self.materia.stock_actual = Decimal('5'); self.materia.cobertura_dias = 7; self.materia.save()
        run = Entrenamiento.objects.create(materia_prima=self.materia, estado='COMPLETADO', modelo='BASELINE')
        values = [{'fecha': (hoy+timedelta(days=i)).isoformat(), 'consumo': 1} for i in range(20)]
        forecast = Pronostico.objects.create(materia_prima=self.materia, entrenamiento=run, inicio=hoy, horizonte=20, valores=values, total=Decimal('20'))
        data = analizar(self.materia, forecast)
        self.assertEqual(data['seguridad'], 0)
        self.assertEqual(data['rop'], 3)
        self.assertEqual(data['objetivo'], 10)
        self.assertEqual(data['cantidad'], 8)
        self.assertEqual(data['fecha_pedido'], hoy+timedelta(days=1))

    def test_cp11_cierre_administrativo_invalida_sesion(self):
        from django.test import Client
        operator_client, admin_client = Client(), Client()
        self.assertTrue(operator_client.login(username=self.operador.username, password='ClaveSegura123!'))
        operator_client.get(reverse('dashboard:home'))
        session = UserSession.objects.get(user=self.operador)
        admin_client.force_login(self.admin)
        response = admin_client.post(reverse('accounts:session_close', args=[session.pk]))
        self.assertEqual(response.status_code, 302)
        session.refresh_from_db()
        self.assertFalse(session.is_active)
        self.assertEqual(operator_client.get(reverse('dashboard:home')).status_code, 302)

    def test_cp11_operador_no_cierra_sesion_ajena(self):
        from django.test import Client
        admin_client, operator_client = Client(), Client()
        self.assertTrue(admin_client.login(username=self.admin.username, password='ClaveSegura123!'))
        admin_client.get(reverse('dashboard:home'))
        sesion = UserSession.objects.get(user=self.admin)
        operator_client.force_login(self.operador)
        operator_client.post(reverse('accounts:session_close', args=[sesion.pk]))
        sesion.refresh_from_db()
        self.assertTrue(sesion.is_active)
        self.assertEqual(admin_client.get(reverse('dashboard:home')).status_code, 200)
