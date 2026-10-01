"""
01_cargar_datos_iniciales.py
============================
Carga materias primas, productos terminados, fórmulas y proveedores.

Ejecutar desde la raíz del proyecto:
    python scripts/01_cargar_datos_iniciales.py
"""
import os, sys, django
from pathlib import Path
from decimal import Decimal

# ── Forzar salida UTF-8 en Windows ──
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


# ── Configurar Django ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from inventario.models import (
    MateriaPrima, ProductoTerminado, Proveedor, MateriaPrimaProveedor,
)
from produccion.models import (
    FormulaProducto, DetalleFormula, DetalleProducto,
)

# =====================================================================
# 1.  MATERIAS PRIMAS
# =====================================================================
MATERIAS = [
    ('INS0001', 'Harina de trigo',  Decimal('50'), 'kg'),
    ('INS0002', 'Harina de maíz',   Decimal('40'), 'kg'),
    ('INS0003', 'Azúcar',           Decimal('35'), 'kg'),
    ('INS0004', 'Mantequilla',      Decimal('25'), 'kg'),
    ('INS0005', 'Cacao en polvo',   Decimal('15'), 'kg'),
    ('INS0006', 'Leche en polvo',   Decimal('12'), 'kg'),
    ('INS0007', 'Avena',            Decimal('30'), 'kg'),
    ('INS0008', 'Maní triturado',   Decimal('18'), 'kg'),
    ('INS0009', 'Miel',             Decimal('20'), 'kg'),
    ('INS0010', 'Sal',              Decimal('3'),  'kg'),
    ('INS0011', 'Coco rallado',     Decimal('16'), 'kg'),
    ('INS0012', 'Pasas',            Decimal('14'), 'kg'),
    ('INS0013', 'Canela molida',    Decimal('5'),  'kg'),
]
COSTOS = dict(zip((fila[0] for fila in MATERIAS), map(Decimal,
    ('3.20', '3.00', '2.80', '12.00', '15.00', '18.00', '4.50',
     '9.00', '17.00', '1.20', '13.00', '11.00', '32.00'))))

print('\n═══ 1. Creando materias primas ═══')
mp_dict = {}  # codigo → instancia
for codigo, nombre, stock, unidad in MATERIAS:
    obj, created = MateriaPrima.objects.get_or_create(
        codigo=codigo,
        defaults={
            'nombre': nombre,
            'stock_actual': stock,
            'unidad_medida': unidad,
            'stock_minimo': Decimal('2'),
            'costo_unitario': COSTOS[codigo],
            'activo': True,
        },
    )
    if not created:
        obj.nombre, obj.unidad_medida, obj.activo = nombre, unidad, True
        if obj.costo_unitario is None:
            obj.costo_unitario = COSTOS[codigo]
        obj.save(update_fields=['nombre', 'unidad_medida', 'activo', 'costo_unitario'])
    mp_dict[codigo] = obj
    print(f'  {"✔ Creada" if created else "↻ Actualizada"}: {obj}')

# =====================================================================
# 2.  PRODUCTOS TERMINADOS
# =====================================================================
PRODUCTOS = [
    ('PROD0001', 'Galleta de chocolate',      'kg', Decimal('15.00')),
    ('PROD0002', 'Galleta de avena y miel',   'kg', Decimal('14.50')),
    ('PROD0003', 'Galleta de maíz',           'kg', Decimal('12.00')),
    ('PROD0004', 'Galleta de maní',           'kg', Decimal('16.00')),
    ('PROD0005', 'Galleta de avena y cacao',  'kg', Decimal('15.50')),
    ('PROD0006', 'Galleta de coco',           'kg', Decimal('16.50')),
    ('PROD0007', 'Barra de avena y pasas',    'kg', Decimal('17.00')),
    ('PROD0008', 'Galleta de canela',         'kg', Decimal('14.00')),
]

print('\n═══ 2. Creando productos terminados ═══')
pt_dict = {}  # codigo → instancia
for codigo, nombre, unidad, precio in PRODUCTOS:
    obj, created = ProductoTerminado.objects.get_or_create(
        codigo=codigo,
        defaults={
            'nombre': nombre,
            'unidad_medida': unidad,
            'stock_actual': Decimal('0'),
            'precio': precio,
            'activo': True,
        },
    )
    if not created:
        obj.nombre, obj.unidad_medida, obj.precio, obj.activo = nombre, unidad, precio, True
        obj.save(update_fields=['nombre', 'unidad_medida', 'precio', 'activo'])
    pt_dict[codigo] = obj
    print(f'  {"✔ Creada" if created else "↻ Actualizada"}: {obj}')

# =====================================================================
# 3.  FÓRMULAS  (por cada 1 kg de producto)
# =====================================================================
# Cada fila: (cod_producto, [(cod_insumo, cantidad), ...])
FORMULAS = {
    'PROD0001': [
        ('INS0001', Decimal('0.40')),
        ('INS0003', Decimal('0.22')),
        ('INS0004', Decimal('0.18')),
        ('INS0005', Decimal('0.10')),
        ('INS0006', Decimal('0.08')),
        ('INS0010', Decimal('0.02')),
    ],
    'PROD0002': [
        ('INS0001', Decimal('0.25')),
        ('INS0003', Decimal('0.02')),
        ('INS0004', Decimal('0.08')),
        ('INS0006', Decimal('0.01')),
        ('INS0007', Decimal('0.32')),
        ('INS0009', Decimal('0.30')),
        ('INS0010', Decimal('0.02')),
    ],
    'PROD0003': [
        ('INS0001', Decimal('0.20')),
        ('INS0002', Decimal('0.40')),
        ('INS0003', Decimal('0.18')),
        ('INS0004', Decimal('0.15')),
        ('INS0006', Decimal('0.05')),
        ('INS0010', Decimal('0.02')),
    ],
    'PROD0004': [
        ('INS0001', Decimal('0.30')),
        ('INS0003', Decimal('0.20')),
        ('INS0004', Decimal('0.15')),
        ('INS0006', Decimal('0.08')),
        ('INS0008', Decimal('0.25')),
        ('INS0010', Decimal('0.02')),
    ],
    'PROD0005': [
        ('INS0001', Decimal('0.20')),
        ('INS0003', Decimal('0.18')),
        ('INS0004', Decimal('0.12')),
        ('INS0005', Decimal('0.10')),
        ('INS0006', Decimal('0.02')),
        ('INS0007', Decimal('0.30')),
        ('INS0009', Decimal('0.06')),
        ('INS0010', Decimal('0.02')),
    ],
    'PROD0006': [
        ('INS0001', Decimal('0.36')), ('INS0003', Decimal('0.18')),
        ('INS0004', Decimal('0.16')), ('INS0006', Decimal('0.06')),
        ('INS0011', Decimal('0.22')), ('INS0010', Decimal('0.02')),
    ],
    'PROD0007': [
        ('INS0007', Decimal('0.43')), ('INS0012', Decimal('0.20')),
        ('INS0009', Decimal('0.17')), ('INS0008', Decimal('0.12')),
        ('INS0004', Decimal('0.06')), ('INS0010', Decimal('0.02')),
    ],
    'PROD0008': [
        ('INS0001', Decimal('0.43')), ('INS0003', Decimal('0.23')),
        ('INS0004', Decimal('0.18')), ('INS0006', Decimal('0.10')),
        ('INS0013', Decimal('0.04')), ('INS0010', Decimal('0.02')),
    ],
}

print('\n═══ 3. Creando fórmulas ═══')
for cod_prod, ingredientes in FORMULAS.items():
    producto = pt_dict[cod_prod]

    # --- DetalleProducto (receta simplificada usada por el motor de producción) ---
    for cod_mp, cant in ingredientes:
        mp = mp_dict[cod_mp]
        DetalleProducto.objects.update_or_create(
            codigoMateriaPrima=mp,
            codigoProductoTerminado=producto,
            defaults={'cantidad': cant},
        )

    # --- FormulaProducto + DetalleFormula (receta formal) ---
    formula, fc = FormulaProducto.objects.update_or_create(
        producto_terminado=producto,
        nombre=f'Fórmula estándar – {producto.nombre}',
        defaults={'cantidad_resultante': Decimal('1'), 'activo': True},
    )
    for cod_mp, cant in ingredientes:
        mp = mp_dict[cod_mp]
        DetalleFormula.objects.update_or_create(
            formula=formula,
            materia_prima=mp,
            defaults={'cantidad_requerida': cant},
        )
    total = sum(c for _, c in ingredientes)
    print(f'  ✔ {producto.nombre}: {len(ingredientes)} insumos, total {total} kg')

# =====================================================================
# 4.  PROVEEDORES  y relaciones  MateriaPrimaProveedor
# =====================================================================
PROVEEDORES = [
    {
        'nombre': 'Distribuidora Andina de Insumos',
        'telefono': '51965034725',
        'whatsapp': '51965034725',
        'insumos': ['INS0001', 'INS0002', 'INS0007', 'INS0003'],
    },
    {
        'nombre': 'Comercial Dulce Sur',
        'telefono': '51965034725',
        'whatsapp': '51965034725',
        'insumos': ['INS0004', 'INS0006', 'INS0009', 'INS0005', 'INS0011'],
    },
    {
        'nombre': 'Abastecimientos Qiwa',
        'telefono': '51965034725',
        'whatsapp': '51965034725',
        'insumos': ['INS0008', 'INS0010', 'INS0003', 'INS0001', 'INS0012', 'INS0013'],
    },
]

print('\n═══ 4. Creando proveedores ═══')
for p in PROVEEDORES:
    prov, created = Proveedor.objects.update_or_create(
        nombre=p['nombre'],
        defaults={
            'telefono': p['telefono'],
            'whatsapp': p['whatsapp'],
            'activo': True,
            'tiempo_entrega_dias': 3,
        },
    )
    for cod in p['insumos']:
        mp = mp_dict[cod]
        MateriaPrimaProveedor.objects.update_or_create(
            materia_prima=mp,
            proveedor=prov,
            defaults={
                'precio': mp.costo_unitario or Decimal('0'),
                'lead_time_dias': 3,
                'activo': True,
            },
        )
        # También establecer el FK directo proveedor si no tiene uno
        if mp.proveedor is None:
            mp.proveedor = prov
            mp.save(update_fields=['proveedor'])
    print(f'  {"✔ Creado" if created else "↻ Actualizado"}: {prov.nombre}  →  {", ".join(p["insumos"])}')

print('\n✅  Datos iniciales cargados exitosamente.\n')
