import tempfile
from datetime import timedelta
from decimal import Decimal as D
from unittest.mock import patch
import numpy as np
import pandas as pd
from django.test import TestCase, SimpleTestCase, override_settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import CustomUser
from inventario.models import (MateriaPrima, ProductoTerminado, Proveedor, MateriaPrimaProveedor,
    MovimientoInventario, SugerenciaCompra, OrdenCompra, DetalleOrdenCompra, LeadTimeReal, LoteMateriaPrima)
from inventario.services import disponible, ajustar_stock
from inventario.procurement import seguridad, redondear_compra, analizar, sugerir, decidir, recibir, transicionar
from produccion.models import (DetalleProducto, Produccion, ConsumoMateriaPrima, FormulaProducto,
    DetalleFormula, OrdenProduccion, Entrenamiento, Pronostico)
from produccion.services.operaciones import reservar_orden, ejecutar_orden, cancelar_orden
from produccion.services.forecasting.features import caracteristicas
from produccion.services.forecasting.evaluation import metricas, seleccionar
from produccion.services.forecasting.preprocessing import preparar, anomalias
from produccion.services.forecasting.training import entrenar
from produccion.services.forecasting.prediction import pronosticar, retroalimentar


class CalculosTest(SimpleTestCase):
    def test_seguridad_moq_multiplo(self):
        self.assertAlmostEqual(float(seguridad(10,4,.95)),32.8970725,places=5)
        self.assertEqual(redondear_compra(D(11),D(20),D(6)),D(24))
        self.assertEqual(redondear_compra(D(-2),D(20),D(6)),0)

    def test_metricas_y_seleccion(self):
        m = metricas([0,10],[2,8])
        self.assertEqual(m['mae'],2)
        self.assertEqual(m['rmse'],2)
        self.assertEqual(m['mape'],20)
        self.assertIsNone(metricas([0,0],[1,1])['mape'])
        self.assertEqual(seleccionar([{'modelo':'A','metricas':m},{'modelo':'B','metricas':metricas([10],[10])}])['modelo'],'B')

    def test_features_no_futuro(self):
        series = pd.Series(np.arange(70.),index=pd.date_range('2025-01-01',periods=70))
        x = caracteristicas(series)
        series.iloc[40:] = 99999
        changed = caracteristicas(series)
        pd.testing.assert_frame_equal(x.iloc[:41],changed.iloc[:41])
        self.assertEqual(x.iloc[40]['promedio_movil_7'],36)


class OperacionesTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='admin',email='admin@test.local',password='test12345',rol='ADMINISTRADOR')
        self.mp = MateriaPrima.objects.create(codigo='MP1',nombre='Harina',stock_actual=D(100),unidad_medida='kg')
        self.pt = ProductoTerminado.objects.create(codigo='PT1',nombre='Pan')
        DetalleProducto.objects.create(codigoMateriaPrima=self.mp,codigoProductoTerminado=self.pt,cantidad=D(2))
        self.prov = Proveedor.objects.create(nombre='Proveedor')
        self.oferta = MateriaPrimaProveedor.objects.create(materia_prima=self.mp,proveedor=self.prov,
            precio=D('2.50'),lead_time_dias=3,moq=20,multiplo=5)

    def history(self,days=70):
        for i in range(days):
            p = Produccion.objects.create(producto=self.pt,cantidad_producida=1,ejecutada=True)
            Produccion.objects.filter(pk=p.pk).update(fecha=timezone.now()-timedelta(days=days-i))
            ConsumoMateriaPrima.objects.create(produccion=p,materia_prima=self.mp,cantidad_usada=D(str(10+i%7)))

    def forecast(self,value=10,days=60):
        run = Entrenamiento.objects.create(materia_prima=self.mp,estado='MODELO_DISPONIBLE',modelo='Prueba')
        return Pronostico.objects.create(materia_prima=self.mp,entrenamiento=run,inicio=timezone.localdate(),
            horizonte=days,total=value*days,valores=[{'fecha':(timezone.localdate()+timedelta(days=i)).isoformat(),'consumo':value} for i in range(days)])

    def test_produccion_atomicidad_idempotencia(self):
        other = MateriaPrima.objects.create(codigo='MP2',nombre='Sal',stock_actual=0)
        DetalleProducto.objects.create(codigoMateriaPrima=other,codigoProductoTerminado=self.pt,cantidad=1)
        p = Produccion.objects.create(producto=self.pt,cantidad_producida=5)
        with self.assertRaises(ValidationError):
            p.consumir_materiales(self.user)
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.stock_actual,100)
        self.assertFalse(p.consumos.exists())
        self.assertFalse(MovimientoInventario.objects.exists())
        ajustar_stock(other.pk,5,'ENTRADA',self.user)
        p.consumir_materiales(self.user)
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.stock_actual,90)
        self.pt.refresh_from_db()
        self.assertEqual(self.pt.stock_actual,5)
        with self.assertRaises(ValidationError):
            p.consumir_materiales(self.user)

    def test_reserva_formula_snapshot_y_liberacion(self):
        f = FormulaProducto.objects.create(producto_terminado=self.pt,nombre='Lote',cantidad_resultante=10)
        detail = DetalleFormula.objects.create(formula=f,materia_prima=self.mp,cantidad_requerida=20)
        order = OrdenProduccion.objects.create(producto_terminado=self.pt,formula=f,cantidad_producida=5,usuario=self.user)
        reservar_orden(order.pk,self.user)
        self.assertEqual(disponible(self.mp),90)
        detail.cantidad_requerida = 999
        detail.save()
        with self.assertRaises(ValidationError):
            ajustar_stock(self.mp.pk,91,'SALIDA',self.user)
        ejecutar_orden(order.pk,self.user)
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.stock_actual,90)
        self.assertEqual(disponible(self.mp),90)
        self.assertFalse(order.reservas.filter(activa=True).exists())

    def test_rop_cantidad_proyeccion(self):
        self.forecast()
        result = analizar(self.mp)
        self.assertEqual(result['rop'],30)
        self.assertEqual(result['objetivo'],330)
        self.assertEqual(result['cantidad'],230)
        self.assertEqual(result['proyeccion'][0]['stock'],90)
        self.assertEqual(result['fecha_agotamiento'],timezone.localdate()+timedelta(days=9))

    def test_compra_aprobacion_recepcion_unica(self):
        self.forecast()
        s = sugerir(self.mp,self.user)
        self.assertFalse(OrdenCompra.objects.exists())
        decidir(s.pk,self.user,True)
        order = OrdenCompra.objects.get()
        with self.assertRaises(ValidationError):
            decidir(s.pk,self.user,True)
        transicionar(order.pk,'ENVIADA',self.user)
        transicionar(order.pk,'CONFIRMADA',self.user)
        recibir(order.pk,self.user)
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.stock_actual,330)
        self.assertEqual(LeadTimeReal.objects.get().dias,0)
        with self.assertRaises(ValidationError):
            recibir(order.pk,self.user)
        self.assertEqual(MovimientoInventario.objects.filter(tipo='ENTRADA').count(),1)

    def test_sugerencia_obsoleta(self):
        self.forecast()
        s = sugerir(self.mp,self.user)
        ajustar_stock(self.mp.pk,5,'ENTRADA',self.user)
        with self.assertRaises(ValidationError):
            decidir(s.pk,self.user,True)
        self.assertFalse(OrdenCompra.objects.exists())

    def test_fefo_y_vencidos(self):
        self.mp.gestionar_lotes = True
        self.mp.save()
        today = timezone.localdate()
        expired = LoteMateriaPrima.objects.create(materia_prima=self.mp,numero='vencido',cantidad_inicial=50,cantidad_disponible=50,fecha_recepcion=today,fecha_vencimiento=today-timedelta(days=1))
        first = LoteMateriaPrima.objects.create(materia_prima=self.mp,numero='primero',cantidad_inicial=10,cantidad_disponible=10,fecha_recepcion=today,fecha_vencimiento=today+timedelta(days=1))
        last = LoteMateriaPrima.objects.create(materia_prima=self.mp,numero='ultimo',cantidad_inicial=40,cantidad_disponible=40,fecha_recepcion=today,fecha_vencimiento=today+timedelta(days=30))
        p = Produccion.objects.create(producto=self.pt,cantidad_producida=8)
        p.consumir_materiales(self.user)
        first.refresh_from_db(); last.refresh_from_db(); expired.refresh_from_db()
        self.assertEqual(first.cantidad_disponible,0)
        self.assertEqual(last.cantidad_disponible,34)
        self.assertEqual(expired.cantidad_disponible,50)

    def test_sin_datos_y_baseline(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MODEL_STORAGE=directory):
            run = entrenar(self.mp)
            self.assertEqual(run.estado,'SIN_DATOS')
            self.history(5)
            run = entrenar(self.mp)
            self.assertEqual(run.estado,'DATOS_INSUFICIENTES')
            forecast = pronosticar(run,7)
            self.assertEqual(len(forecast.valores),7)
            self.assertEqual(forecast.inicio,timezone.localdate())

    def test_entrenamiento_temporal_real(self):
        self.history(70)
        with tempfile.TemporaryDirectory() as directory, override_settings(MODEL_STORAGE=directory):
            run = entrenar(self.mp)
            self.assertEqual(run.estado,'MODELO_DISPONIBLE')
            self.assertEqual(len(run.comparacion),4)
            self.assertEqual(len(run.validacion),14)
            self.assertEqual(run.modelo,seleccionar(run.comparacion)['modelo'])
            self.assertEqual(len(pronosticar(run,30).valores),30)

    def test_preprocesamiento_anomalias_inmutabilidad(self):
        self.history(30)
        c = ConsumoMateriaPrima.objects.first()
        c.cantidad_usada = 200
        c.save()
        before = list(ConsumoMateriaPrima.objects.values_list('id','cantidad_usada'))
        self.assertTrue(anomalias(self.mp))
        serie,log = preparar(self.mp)
        self.assertEqual(len(serie),30)
        self.assertEqual(before,list(ConsumoMateriaPrima.objects.values_list('id','cantidad_usada')))
        c.excluido_entrenamiento = True
        c.save()
        serie,log = preparar(self.mp)
        self.assertEqual(log['excluidos'],1)

    def test_paginas_y_permisos(self):
        self.client.force_login(self.user)
        paths = ['/dashboard/','/produccion/inteligencia/',f'/produccion/analisis/{self.mp.pk}/',
                 '/produccion/historial/','/produccion/compras/','/produccion/planes/',
                 '/produccion/clasificacion/','/produccion/auditoria/','/produccion/lotes/',
                 '/produccion/lotes/apertura/','/produccion/ofertas/nueva/',f'/produccion/politica/{self.mp.pk}/',
                 '/inventario/materias-primas/','/produccion/formulas/','/produccion/pronosticos/']
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code,200)
        self.user.rol = 'OPERADOR'
        self.user.save()
        response = self.client.post(f'/produccion/analisis/{self.mp.pk}/entrenar/')
        self.assertEqual(response.status_code,302)
        self.assertFalse(Entrenamiento.objects.exists())

    def test_dashboard_no_entrena(self):
        self.client.force_login(self.user)
        with patch('produccion.predictive_views.entrenar',side_effect=AssertionError('No entrenar')):
            self.client.get('/dashboard/')
            self.client.get('/produccion/inteligencia/')
        self.assertFalse(Entrenamiento.objects.exists())

    def test_cancelar_reserva_receta_actual(self):
        order = OrdenProduccion.objects.create(producto_terminado=self.pt,cantidad_producida=5,usuario=self.user)
        reservar_orden(order.pk,self.user)
        self.assertEqual(disponible(self.mp),90)
        cancelar_orden(order.pk,self.user)
        self.assertEqual(disponible(self.mp),100)
        with self.assertRaises(ValidationError):
            ejecutar_orden(order.pk,self.user)

    def test_precio_actualizado_requiere_revision(self):
        self.forecast()
        s = sugerir(self.mp,self.user)
        self.oferta.precio = D('10')
        self.oferta.save()
        with self.assertRaises(ValidationError):
            decidir(s.pk,self.user,True)

    def test_rechazo_no_crea_orden(self):
        self.forecast()
        s = sugerir(self.mp,self.user)
        decidir(s.pk,self.user,False)
        s.refresh_from_db()
        self.assertEqual(s.estado,'RECHAZADA')
        self.assertFalse(OrdenCompra.objects.exists())

    def test_receipt_en_fecha_no_adelantada(self):
        self.forecast()
        order = OrdenCompra.objects.create(proveedor=self.prov,usuario=self.user,
            fecha_estimada=timezone.localdate()+timedelta(days=4))
        DetalleOrdenCompra.objects.create(orden=order,oferta=self.oferta,cantidad=30,precio=2)
        a = analizar(self.mp)
        self.assertEqual(a['transito'],30)
        self.assertEqual(a['posicion'],130)
        self.assertEqual(a['proyeccion'][0]['stock'],90)
        self.assertEqual(a['proyeccion'][4]['stock'],80)
        order.fecha_estimada = timezone.localdate()-timedelta(days=1)
        order.save()
        a = analizar(self.mp)
        self.assertEqual(a['posicion_cobertura'],100)
        self.assertTrue(a['advertencias'])

    def test_recepcion_lote_invalido_reversible(self):
        self.mp.gestionar_lotes = True
        self.mp.save()
        order = OrdenCompra.objects.create(proveedor=self.prov,usuario=self.user,
            fecha_estimada=timezone.localdate(),estado='CONFIRMADA')
        DetalleOrdenCompra.objects.create(orden=order,oferta=self.oferta,cantidad=30,precio=2)
        with self.assertRaises(ValidationError):
            recibir(order.pk,self.user)
        self.mp.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.mp.stock_actual,100)
        self.assertEqual(order.estado,'CONFIRMADA')
        self.assertFalse(LeadTimeReal.objects.exists())

    def test_feedback_idempotente_y_cero(self):
        forecast = self.forecast()
        yesterday = timezone.localdate()-timedelta(days=1)
        forecast.inicio = yesterday
        forecast.valores = [{'fecha':yesterday.isoformat(),'consumo':10}]
        forecast.save()
        retroalimentar(); retroalimentar()
        self.assertEqual(forecast.evaluaciones.count(),1)
        e = forecast.evaluaciones.get()
        self.assertEqual(e.error_absoluto,10)
        self.assertIsNone(e.error_porcentual)

    def test_sintetico_futuro_no_entrena(self):
        self.history(5)
        p = Produccion.objects.create(producto=self.pt,cantidad_producida=1,sintetica=True)
        Produccion.objects.filter(pk=p.pk).update(fecha=timezone.now()-timedelta(days=100))
        ConsumoMateriaPrima.objects.create(produccion=p,materia_prima=self.mp,cantidad_usada=999)
        future = Produccion.objects.create(producto=self.pt,cantidad_producida=1)
        Produccion.objects.filter(pk=future.pk).update(fecha=timezone.now()+timedelta(days=10))
        ConsumoMateriaPrima.objects.create(produccion=future,materia_prima=self.mp,cantidad_usada=999)
        series,log = preparar(self.mp)
        self.assertEqual(len(series),5)
        self.assertEqual(log['registros_utilizados'],5)

    def test_no_elevar_rol_desde_perfil(self):
        self.user.rol = 'OPERADOR'
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.post('/accounts/perfil/editar/',{'username':self.user.username,'email':self.user.email,
            'telefono':'','rol':'ADMINISTRADOR','is_active':'on'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.rol,'OPERADOR')
        self.assertNotEqual(response.status_code,404)

    def test_filtros_invalidos_no_error_servidor(self):
        self.client.force_login(self.user)
        response = self.client.get('/produccion/historial/?desde=invalido')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['form'].errors)

    def test_artifact_integridad(self):
        from pathlib import Path
        self.history(5)
        with tempfile.TemporaryDirectory() as directory, override_settings(MODEL_STORAGE=directory):
            run = entrenar(self.mp)
            (Path(directory)/run.artefacto).write_bytes(b'alterado')
            with self.assertRaises(ValidationError):
                pronosticar(run,7)

    def test_pantalla_con_modelo_y_compra(self):
        self.history(5)
        self.client.force_login(self.user)
        with tempfile.TemporaryDirectory() as directory, override_settings(MODEL_STORAGE=directory):
            run = entrenar(self.mp)
            pronosticar(run,60)
            response = self.client.get(f'/produccion/analisis/{self.mp.pk}/')
            self.assertContains(response,'Promedio móvil')
            self.assertContains(response,'Datos históricos insuficientes')
            suggestion = sugerir(self.mp,self.user)
            response = self.client.post(f'/produccion/sugerencias/{suggestion.pk}/aprobar/')
            self.assertEqual(response.status_code,302)
            order = OrdenCompra.objects.get()
            self.assertEqual(self.client.get(f'/produccion/compras/{order.pk}/').status_code,200)

    def test_confirmacion_web_repetida_no_duplica(self):
        self.client.force_login(self.user)
        self.client.post('/produccion/producir/',{'producto':self.pt.pk,'cantidad':'5'})
        keys = {key:self.client.session[key] for key in ['produccion_producto_id','produccion_cantidad','produccion_clave']}
        self.client.post('/produccion/producir/confirmar/')
        session = self.client.session
        session.update(keys)
        session.save()
        self.client.post('/produccion/producir/confirmar/')
        self.assertEqual(Produccion.objects.count(),1)
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.stock_actual,90)

    def test_vencidos_no_financian_compra(self):
        self.mp.gestionar_lotes = True
        self.mp.save()
        LoteMateriaPrima.objects.create(materia_prima=self.mp,numero='V',cantidad_inicial=50,
            cantidad_disponible=50,fecha_recepcion=timezone.localdate()-timedelta(days=20),
            fecha_vencimiento=timezone.localdate()-timedelta(days=1))
        self.forecast()
        a = analizar(self.mp)
        self.assertEqual(a['disponible'],100)
        self.assertEqual(a['utilizable'],50)
        self.assertEqual(a['cantidad'],280)
