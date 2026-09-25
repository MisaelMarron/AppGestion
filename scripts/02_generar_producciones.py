"""
02_generar_producciones.py
===========================
Genera producciones simuladas a lo largo del último mes, como si fuera
una empresa real de galletas que produce diariamente.

Lógica de simulación:
 - Produce entre 1 y 3 lotes por día laborable (lunes a sábado).
 - Los productos más populares (chocolate, avena y miel) se producen
   con más frecuencia que los demás.
 - Las cantidades varían de forma realista (2 a 8 kg por lote).
 - Se inyecta variabilidad: algunos días no se produce, otros tienen
   picos de demanda (viernes/sábado).
 - Los stocks de materias primas se reabastecen automáticamente
   cuando no alcanzan (simula compras intermedias).

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
from django.db import connection
from django.contrib.auth import get_user_model
from inventario.models import (
    MateriaPrima, ProductoTerminado, MovimientoInventario,
)
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
# Más peso = se produce más seguido
PESOS_PRODUCTO = {}
for pt in productos:
    cod = pt.codigo.upper()
    if 'PROD0001' in cod:    # Galleta de chocolate — la más popular
        PESOS_PRODUCTO[pt.pk] = 30
    elif 'PROD0002' in cod:  # Galleta de avena y miel
        PESOS_PRODUCTO[pt.pk] = 25
    elif 'PROD0003' in cod:  # Galleta de maíz
        PESOS_PRODUCTO[pt.pk] = 18
    elif 'PROD0004' in cod:  # Galleta de maní
        PESOS_PRODUCTO[pt.pk] = 15
    elif 'PROD0005' in cod:  # Galleta de avena y cacao
        PESOS_PRODUCTO[pt.pk] = 12
    else:
        PESOS_PRODUCTO[pt.pk] = 10

# ── Rango de fechas: último mes completo ──
hoy = timezone.localdate()
fecha_inicio = hoy - timedelta(days=30)
fecha_fin = hoy - timedelta(days=1)  # hasta ayer

print(f'\n═══ Generando producciones del {fecha_inicio} al {fecha_fin} ═══')
print(f'    Usuario: {usuario.username}')
print(f'    Productos: {len(productos)}')
print(f'    Recetas: {len(recetas)}\n')

# ── Función auxiliar: reabastecer MP si el stock es bajo ──
def reabastecer_si_necesario(materia, cantidad_necesaria):
    """Simula una compra/reabastecimiento cuando el stock no alcanza."""
    if materia.stock_actual < cantidad_necesaria:
        reabastecimiento = cantidad_necesaria * Decimal('3') + Decimal('10')
        materia.stock_actual += reabastecimiento
        materia.save(update_fields=['stock_actual', 'ultima_vez_actualizado'])
        # Registrar movimiento de entrada
        MovimientoInventario.objects.create(
            tipo='ENTRADA',
            materia_prima=materia,
            cantidad=reabastecimiento,
            usuario=usuario,
            descripcion='Reabastecimiento automático (simulación)',
        )

# ── Generar producciones día a día ──
total_producciones = 0
total_kg = Decimal('0')
resumen_por_producto = {}

dia_actual = fecha_inicio
while dia_actual <= fecha_fin:
    dia_semana = dia_actual.weekday()  # 0=Lunes ... 6=Domingo

    # Domingos: no se produce
    if dia_semana == 6:
        dia_actual += timedelta(days=1)
        continue

    # Determinar cuántas producciones hacer hoy
    if dia_semana in (4, 5):  # Viernes y sábado: más producción
        num_producciones = random.choices([1, 2, 3, 4], weights=[10, 30, 40, 20])[0]
    elif dia_semana == 0:  # Lunes: arranque lento
        num_producciones = random.choices([0, 1, 2], weights=[15, 50, 35])[0]
    else:  # Martes a Jueves: ritmo normal
        num_producciones = random.choices([1, 2, 3], weights=[25, 50, 25])[0]

    # Algunos días aleatorios: no se produce (mantenimiento, etc.)
    if random.random() < 0.08:
        num_producciones = 0

    for _ in range(num_producciones):
        # Seleccionar producto con pesos de popularidad
        ids = list(PESOS_PRODUCTO.keys())
        pesos = [PESOS_PRODUCTO[pk] for pk in ids]
        producto_id = random.choices(ids, weights=pesos)[0]

        if producto_id not in recetas:
            continue

        producto = ProductoTerminado.objects.get(pk=producto_id)

        # Cantidad a producir: varía entre 2 y 8 kg con distribución normal-ish
        base = random.gauss(4.5, 1.5)
        cantidad = Decimal(str(max(1.5, min(9.0, base)))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        # Días de más demanda → cantidades un poco mayores
        if dia_semana in (4, 5):
            cantidad = (cantidad * Decimal('1.25')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

        # Verificar y reabastecer materias primas
        receta_lineas = recetas[producto_id]
        snapshot = []
        puede_producir = True
        for linea in receta_lineas:
            mp = MateriaPrima.objects.get(pk=linea['materia_id'])
            cant_requerida = (linea['cantidad'] * cantidad).quantize(
                Decimal('0.00001'), rounding=ROUND_HALF_UP
            )
            reabastecer_si_necesario(mp, cant_requerida)
            snapshot.append({
                'materia_id': mp.pk,
                'cantidad': str(cant_requerida),
            })

        # Crear la producción con fecha pasada
        # Hora aleatoria entre 7am y 5pm
        hora = random.randint(7, 17)
        minuto = random.randint(0, 59)
        fecha_produccion = timezone.make_aware(
            datetime(dia_actual.year, dia_actual.month, dia_actual.day, hora, minuto)
        )

        produccion = Produccion(
            producto=producto,
            usuario=usuario,
            clave_operacion=uuid.uuid4(),
            cantidad_producida=cantidad,
            ejecutada=True,
            sintetica=False,
            receta_snapshot=snapshot,
        )
        produccion.full_clean()
        produccion.save()

        # Forzar la fecha al pasado
        Produccion.objects.filter(pk=produccion.pk).update(fecha=fecha_produccion)

        # Consumir materias primas y crear registros de consumo
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
                descripcion=f'Producción simulada {produccion.pk}',
            )
            # Forzar fecha del movimiento
            MovimientoInventario.objects.filter(pk=mov.pk).update(fecha=fecha_produccion)

        # Incrementar stock del producto terminado
        producto.stock_actual += cantidad
        producto.save(update_fields=['stock_actual'])

        mov_pt = MovimientoInventario.objects.create(
            tipo='PRODUCCION',
            producto_terminado=producto,
            cantidad=cantidad,
            usuario=usuario,
            descripcion=f'Producción simulada {produccion.pk}',
        )
        MovimientoInventario.objects.filter(pk=mov_pt.pk).update(fecha=fecha_produccion)

        total_producciones += 1
        total_kg += cantidad
        resumen_por_producto[producto.nombre] = resumen_por_producto.get(producto.nombre, 0) + 1

    dia_actual += timedelta(days=1)

# ── Resumen final ──
print('═══ Resumen de producción simulada ═══')
print(f'  📦 Total producciones: {total_producciones}')
print(f'  ⚖️  Total producido:   {total_kg:.2f} kg')
print()
for nombre, conteo in sorted(resumen_por_producto.items(), key=lambda x: -x[1]):
    print(f'  • {nombre}: {conteo} lotes')

print('\n═══ Stock actual de materias primas ═══')
for mp in MateriaPrima.objects.filter(activo=True).order_by('codigo'):
    print(f'  {mp.codigo}  {mp.nombre:.<25s} {mp.stock_actual:>8.2f} {mp.unidad_medida}')

print('\n═══ Stock actual de productos terminados ═══')
for pt in ProductoTerminado.objects.filter(activo=True).order_by('codigo'):
    print(f'  {pt.codigo}  {pt.nombre:.<30s} {pt.stock_actual:>8.2f} {pt.unidad_medida}')

# ═══════════════════════════════════════════════════════════════════
# ENTRENAR MODELOS PREDICTIVOS Y GENERAR PRONÓSTICOS
# ═══════════════════════════════════════════════════════════════════
print('\n═══ Entrenando modelos predictivos ═══')

from produccion.services.forecasting.training import entrenar
from produccion.services.forecasting.prediction import pronosticar

for mp in MateriaPrima.objects.filter(activo=True).order_by('codigo'):
    try:
        run = entrenar(mp, usuario)
        print(f'  ✔ {mp.nombre}: {run.estado} (modelo: {run.modelo or "N/A"}, registros: {run.registros})')

        if run.artefacto and not run.obsoleto:
            forecast = pronosticar(run, horizonte=60)
            print(f'    → Pronóstico generado: {forecast.horizonte} días, total estimado: {forecast.total:.2f} {mp.unidad_medida}')
        else:
            print(f'    → Sin modelo disponible para pronosticar')
    except Exception as e:
        print(f'  ⚠ {mp.nombre}: {e}')

print('\n✅  Producciones simuladas y modelos predictivos generados exitosamente.\n')

