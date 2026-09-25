"""
02_generar_producciones.py
===========================
Genera producciones simuladas a lo largo de los últimos 75 días, como si fuera
una empresa real de galletas que produce diariamente.

Lógica de simulación:
 - Produce entre 1 y 4 lotes por día laborable (lunes a sábado).
 - Cada lote registra la cantidad en masa/bulk (kg) y las unidades producidas
   (paquetes/unidades, aprox. 15 unidades por kilo).
 - Los productos más populares se producen con mayor frecuencia.
 - Simula el consumo histórico completo para que los 4 modelos de Machine Learning
   y series temporales (Random Forest, SARIMA, Holt-Winters y Promedio Móvil)
   tengan datos suficientes para entrenarse y compararse automáticamente.
 - Al finalizar, entrena los modelos, genera pronósticos a 60 días y crea las
   sugerencias de reabastecimiento automáticas para insumos con bajo stock.

Ejecutar desde la raíz del proyecto:
    python scripts/02_generar_producciones.py
"""
import os, sys, random, uuid
from pathlib import Path
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP

# ── Forzar salida UTF-8 en Windows ──
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ── Configurar Django ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.utils import timezone
from django.db import connection, transaction
from django.contrib.auth import get_user_model
from inventario.models import (
    MateriaPrima, ProductoTerminado, MovimientoInventario,
    SugerenciaCompra, OrdenCompra, DetalleOrdenCompra, MateriaPrimaProveedor,
)
from inventario.procurement import analizar, sugerir
from produccion.models import (
    Produccion, ConsumoMateriaPrima, DetalleProducto,
)

User = get_user_model()

# ── Semilla reproducible ──
random.seed(42)

# ── Obtener usuario para los movimientos ──
usuario = User.objects.filter(is_superuser=True).first()
if not usuario:
    usuario = User.objects.first()
if not usuario:
    print('⚠  No hay usuarios en el sistema. Creando superusuario "admin"…')
    usuario = User.objects.create_superuser('admin', 'admin@operastock.local', 'admin123')

# ── Verificar que existan productos y materias primas ──
productos = list(ProductoTerminado.objects.filter(activo=True))
materias = {mp.pk: mp for mp in MateriaPrima.objects.filter(activo=True)}

if not productos:
    print('❌  No hay productos terminados. Ejecuta primero 01_cargar_datos_iniciales.py')
    sys.exit(1)

# ── Obtener recetas ──
recetas = {}  # producto_id → [{materia_id, cantidad}, ...]
for pt in productos:
    detalles = DetalleProducto.objects.filter(codigoProductoTerminado=pt)
    if detalles.exists():
        recetas[pt.pk] = [
            {'materia_id': d.codigoMateriaPrima_id, 'cantidad': d.cantidad}
            for d in detalles
        ]

if not recetas:
    print('❌  No hay recetas configuradas. Ejecuta primero 01_cargar_datos_iniciales.py')
    sys.exit(1)

# ── Pesos de popularidad por producto ──
# Equilibrado para asegurar que todos los insumos alcancen >= 30 consumos
PESOS_PRODUCTO = {}
for pt in productos:
    cod = (pt.codigo or '').upper()
    if 'PROD0001' in cod:    # Galleta de chocolate
        PESOS_PRODUCTO[pt.pk] = 25
    elif 'PROD0002' in cod:  # Galleta de avena y miel
        PESOS_PRODUCTO[pt.pk] = 22
    elif 'PROD0003' in cod:  # Galleta de maíz
        PESOS_PRODUCTO[pt.pk] = 20
    elif 'PROD0004' in cod:  # Galleta de maní
        PESOS_PRODUCTO[pt.pk] = 18
    elif 'PROD0005' in cod:  # Galleta de avena y cacao
        PESOS_PRODUCTO[pt.pk] = 15
    else:
        PESOS_PRODUCTO[pt.pk] = 15

# ── Rango de fechas: 85 días históricos para asegurar split >= 45 y registros >= 30 en todos los insumos ──
hoy = timezone.localdate()
fecha_inicio = hoy - timedelta(days=85)
fecha_fin = hoy - timedelta(days=1)  # hasta ayer

print(f'\n═══ Generando producciones del {fecha_inicio} al {fecha_fin} (85 días) ═══')
print(f'    Usuario: {usuario.username}')
print(f'    Productos: {len(productos)}')
print(f'    Recetas: {len(recetas)}\n')

# ── Función auxiliar: reabastecer MP si el stock es bajo durante la simulación ──
def reabastecer_si_necesario(materia, cantidad_necesaria, dia_actual):
    """Simula una compra/reabastecimiento periódica cuando el stock no alcanza."""
    if materia.stock_actual < cantidad_necesaria:
        # En los últimos 5 días dejamos stock más ajustado para que se vean insumos críticos
        dias_para_fin = (fecha_fin - dia_actual).days
        factor = Decimal('2.0') if dias_para_fin > 6 else Decimal('1.1')
        reabastecimiento = (cantidad_necesaria * factor + Decimal('15')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        materia.stock_actual += reabastecimiento
        materia.save(update_fields=['stock_actual', 'ultima_vez_actualizado'])
        
        # Fecha del movimiento
        fecha_mov = timezone.make_aware(datetime(dia_actual.year, dia_actual.month, dia_actual.day, 8, 0))
        mov = MovimientoInventario.objects.create(
            tipo='ENTRADA',
            materia_prima=materia,
            cantidad=reabastecimiento,
            usuario=usuario,
            descripcion='Reabastecimiento de insumos',
        )
        MovimientoInventario.objects.filter(pk=mov.pk).update(fecha=fecha_mov)

# ── Generar producciones día a día ──
total_producciones = 0
total_kg = Decimal('0')
total_unidades = 0
resumen_por_producto = {}

ultimos_producidos = []

dia_actual = fecha_inicio
while dia_actual <= fecha_fin:
    dia_semana = dia_actual.weekday()  # 0=Lunes ... 6=Domingo

    # Domingos: descanso
    if dia_semana == 6:
        dia_actual += timedelta(days=1)
        continue

    # Determinar cuántas producciones hacer hoy
    if dia_semana in (4, 5):  # Viernes y sábado: mayor ritmo (2 a 4 lotes)
        num_producciones = random.choices([2, 3, 4], weights=[20, 50, 30])[0]
    elif dia_semana == 0:  # Lunes: 2 lotes
        num_producciones = random.choices([1, 2, 3], weights=[30, 50, 20])[0]
    else:  # Martes a Jueves: 2 a 3 lotes
        num_producciones = random.choices([2, 3], weights=[60, 40])[0]

    for _ in range(num_producciones):
        # Seleccionar producto balanceando para evitar rezagados
        recientes = [r for r in ultimos_producidos[-2:]]
        candidatos = [pk for pk in PESOS_PRODUCTO.keys() if pk not in recientes] or list(PESOS_PRODUCTO.keys())
        pesos = [PESOS_PRODUCTO[pk] for pk in candidatos]
        producto_id = random.choices(candidatos, weights=pesos)[0]
        ultimos_producidos.append(producto_id)

        if producto_id not in recetas:
            continue

        producto = ProductoTerminado.objects.get(pk=producto_id)

        # Cantidad en bulk (kg): varía entre 3 y 10 kg
        base = random.gauss(5.5, 1.8)
        cantidad_bulk = Decimal(str(max(2.0, min(12.0, base)))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        # Viernes y sábados lotes ligeramente mayores
        if dia_semana in (4, 5):
            cantidad_bulk = (cantidad_bulk * Decimal('1.2')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

        # Unidades producidas: aprox. 15 paquetes/unidades por cada kg de bulk
        # ej. 10 kg -> ~150 unidades
        unidades = int(cantidad_bulk * Decimal('15')) + random.randint(-2, 3)
        unidades = max(10, unidades)

        # Verificar y reabastecer materias primas si hiciera falta
        receta_lineas = recetas[producto_id]
        snapshot = []
        for linea in receta_lineas:
            mp = MateriaPrima.objects.get(pk=linea['materia_id'])
            cant_requerida = (linea['cantidad'] * cantidad_bulk).quantize(
                Decimal('0.00001'), rounding=ROUND_HALF_UP
            )
            reabastecer_si_necesario(mp, cant_requerida, dia_actual)
            snapshot.append({
                'materia_id': mp.pk,
                'cantidad': str(cant_requerida),
            })

        # Hora aleatoria de producción
        hora = random.randint(7, 17)
        minuto = random.randint(0, 59)
        fecha_produccion = timezone.make_aware(
            datetime(dia_actual.year, dia_actual.month, dia_actual.day, hora, minuto)
        )

        produccion = Produccion(
            producto=producto,
            usuario=usuario,
            clave_operacion=uuid.uuid4(),
            cantidad_producida=cantidad_bulk,
            unidades_producidas=unidades,
            ejecutada=True,
            sintetica=False,
            receta_snapshot=snapshot,
        )
        produccion.full_clean()
        produccion.save()

        # Forzar la fecha histórica
        Produccion.objects.filter(pk=produccion.pk).update(fecha=fecha_produccion)

        # Consumir materias primas y registrar movimientos
        for linea in snapshot:
            mp = MateriaPrima.objects.get(pk=linea['materia_id'])
            cant = Decimal(linea['cantidad'])

            ConsumoMateriaPrima.objects.create(
                produccion=produccion,
                materia_prima=mp,
                cantidad_usada=cant,
            )

            mp.stock_actual -= cant
            mp.save(update_fields=['stock_actual', 'ultima_vez_actualizado'])

            mov = MovimientoInventario.objects.create(
                tipo='PRODUCCION',
                materia_prima=mp,
                cantidad=-cant,
                usuario=usuario,
                descripcion=f'Consumo producción #{produccion.pk} ({producto.nombre})',
            )
            MovimientoInventario.objects.filter(pk=mov.pk).update(fecha=fecha_produccion)

        # Incrementar stock de producto terminado
        producto.stock_actual += cantidad_bulk
        producto.save(update_fields=['stock_actual'])

        mov_pt = MovimientoInventario.objects.create(
            tipo='PRODUCCION',
            producto_terminado=producto,
            cantidad=cantidad_bulk,
            usuario=usuario,
            descripcion=f'Producción #{produccion.pk} ({unidades} uds)',
        )
        MovimientoInventario.objects.filter(pk=mov_pt.pk).update(fecha=fecha_produccion)

        total_producciones += 1
        total_kg += cantidad_bulk
        total_unidades += unidades
        resumen_por_producto[producto.nombre] = resumen_por_producto.get(producto.nombre, 0) + 1

    dia_actual += timedelta(days=1)

# ── Resumen de producción ──
print('═══ Resumen de producción simulada ═══')
print(f'  📦 Total producciones: {total_producciones}')
print(f'  ⚖️  Total bulk (kg):   {total_kg:.2f} kg')
print(f'  🍪 Total unidades:    {total_unidades:,} unidades')
print()
for nombre, conteo in sorted(resumen_por_producto.items(), key=lambda x: -x[1]):
    print(f'  • {nombre}: {conteo} lotes')

print('\n═══ Stock actual de materias primas ═══')
for mp in MateriaPrima.objects.filter(activo=True).order_by('codigo'):
    print(f'  {mp.codigo}  {mp.nombre:.<25s} {mp.stock_actual:>8.2f} {mp.unidad_medida}')

# ═══════════════════════════════════════════════════════════════════
# ENTRENAR MODELOS PREDICTIVOS Y GENERAR PRONÓSTICOS
# ═══════════════════════════════════════════════════════════════════
print('\n═══ Entrenando los 4 Modelos Predictivos (Machine Learning & Series Temporales) ═══')

from produccion.services.forecasting.training import entrenar
from produccion.services.forecasting.prediction import pronosticar

sugerencias_creadas = 0

for mp in MateriaPrima.objects.filter(activo=True).order_by('codigo'):
    try:
        run = entrenar(mp, usuario)
        num_modelos = len(run.comparacion) if run.comparacion else 1
        print(f'  ✔ {mp.nombre}: {run.estado} | Modelo óptimo: {run.modelo} ({num_modelos} modelos evaluados, {run.registros} registros)')

        if run.artefacto and not run.obsoleto:
            forecast = pronosticar(run, horizonte=60)
            print(f'    → Pronóstico generado: 60 días, demanda proyectada: {forecast.total:.2f} {mp.unidad_medida}')

            # Generar sugerencia de compra si el stock está por debajo del ROP
            try:
                calculo = analizar(mp, forecast)
                if calculo.get('cantidad', 0) > 0 and 'oferta_id' in calculo:
                    sugerencia = sugerir(mp, usuario)
                    sugerencias_creadas += 1
                    print(f'    💡 Sugerencia de compra generada: {sugerencia.cantidad:.2f} {mp.unidad_medida} (Proveedor: {sugerencia.oferta.proveedor.nombre})')
            except Exception as se:
                print(f'    ℹ Sin sugerencia inmediata: {se}')
        else:
            print(f'    → Sin artefacto de pronóstico')
    except Exception as e:
        print(f'  ⚠ {mp.nombre}: {e}')

# ═══════════════════════════════════════════════════════════════════
# CREAR ÓRDENES DE COMPRA DE EJEMPLO
# ═══════════════════════════════════════════════════════════════════
print('\n═══ Registrando órdenes de compra de ejemplo ═══')
try:
    # 1. Orden reciente en tránsito
    oferta_harina = MateriaPrimaProveedor.objects.filter(materia_prima__codigo='INS0001').first()
    if oferta_harina:
        oc1 = OrdenCompra.objects.create(
            proveedor=oferta_harina.proveedor,
            usuario=usuario,
            estado='EN_TRANSITO',
            fecha_pedido=hoy - timedelta(days=2),
            fecha_estimada=hoy + timedelta(days=2),
            observacion='Reabastecimiento programado de harina de trigo',
        )
        DetalleOrdenCompra.objects.create(
            orden=oc1,
            oferta=oferta_harina,
            cantidad=Decimal('50.00'),
            precio=oferta_harina.precio,
        )
        print(f'  ✔ Orden #{oc1.pk} EN TRÁNSITO registrada: 50 kg Harina de Trigo ({oferta_harina.proveedor.nombre})')

    # 2. Orden recibida la semana pasada
    oferta_cacao = MateriaPrimaProveedor.objects.filter(materia_prima__codigo='INS0005').first()
    if oferta_cacao:
        oc2 = OrdenCompra.objects.create(
            proveedor=oferta_cacao.proveedor,
            usuario=usuario,
            estado='RECIBIDA',
            fecha_pedido=hoy - timedelta(days=10),
            fecha_estimada=hoy - timedelta(days=8),
            fecha_recepcion=hoy - timedelta(days=8),
            observacion='Compra mensual de cacao en polvo',
        )
        DetalleOrdenCompra.objects.create(
            orden=oc2,
            oferta=oferta_cacao,
            cantidad=Decimal('20.00'),
            precio=oferta_cacao.precio,
        )
        print(f'  ✔ Orden #{oc2.pk} RECIBIDA registrada: 20 kg Cacao en Polvo ({oferta_cacao.proveedor.nombre})')
except Exception as oe:
    print(f'  ⚠ Error al crear órdenes de ejemplo: {oe}')

print(f'\n✅  Simulación completa exitosa.')
print(f'    • {total_producciones} producciones con registro de kilos bulk y unidades.')
print(f'    • Comparativa de 4 modelos predictivos activa.')
print(f'    • {sugerencias_creadas} sugerencias pendientes de compra listas en /produccion/compras/.\n')
