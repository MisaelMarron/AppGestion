"""
03_limpiar_base_datos.py
=========================
Elimina TODOS los datos de la base de datos dejando el sistema limpio,
como si fuera una instalación nueva.

⚠️  PRECAUCIÓN: Este script borra TODO el contenido de las tablas del
proyecto (inventario, producción, cuentas de usuario, etc.).
Las migraciones y la estructura se conservan.

Ejecutar desde la raíz del proyecto:
    python scripts/03_limpiar_base_datos.py
"""
import os, sys
from pathlib import Path

# ── Forzar salida UTF-8 en Windows ──
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdin.reconfigure(encoding='utf-8')


# ── Configurar Django ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.db import connection

# ── Confirmación de seguridad ──
print('\n' + '═' * 60)
print('  ⚠️   LIMPIEZA TOTAL DE LA BASE DE DATOS')
print('═' * 60)
print()
print('  Este script eliminará TODO el contenido:')
print('  • Materias primas')
print('  • Productos terminados')
print('  • Fórmulas y recetas')
print('  • Producciones y consumos')
print('  • Movimientos de inventario')
print('  • Proveedores y ofertas')
print('  • Órdenes de compra y sugerencias')
print('  • Entrenamientos y pronósticos')
print('  • Auditoría')
print('  • Usuarios (excepto estructura)')
print()

es_forzado = '--force' in sys.argv or '-y' in sys.argv

if not es_forzado:
    respuesta = input('  ¿Está seguro? Escriba "SI" para continuar: ').strip()
    if respuesta != 'SI':
        print('\n  ❌ Operación cancelada.\n')
        sys.exit(0)

print()

# ── Importar todos los modelos ──
from produccion.models import (
    ConsumoMateriaPrima, Produccion, DetalleFormula, FormulaProducto,
    DetalleProducto, OrdenProduccion,
)
from produccion.forecast_models import (
    EvaluacionPronostico, Pronostico, Entrenamiento,
)
from inventario.models import (
    MovimientoInventario, MateriaPrimaProveedor, MateriaPrima,
    ProductoTerminado, Proveedor,
    ReservaInventario, SugerenciaCompra, DetalleOrdenCompra,
    OrdenCompra, LeadTimeReal, LoteMateriaPrima, ConsumoLote, Auditoria,
)
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session

User = get_user_model()

# ── Orden de borrado (respetando FK) ──
BORRADO = [
    ('Evaluaciones de pronóstico',     EvaluacionPronostico),
    ('Pronósticos',                    Pronostico),
    ('Entrenamientos',                 Entrenamiento),
    ('Consumos de lote',               ConsumoLote),
    ('Consumos de materia prima',      ConsumoMateriaPrima),
    ('Reservas de inventario',         ReservaInventario),
    ('Lead times reales',              LeadTimeReal),
    ('Detalles de orden de compra',    DetalleOrdenCompra),
    ('Órdenes de compra',              OrdenCompra),
    ('Sugerencias de compra',          SugerenciaCompra),
    ('Movimientos de inventario',      MovimientoInventario),
    ('Producciones',                   Produccion),
    ('Órdenes de producción',          OrdenProduccion),
    ('Detalles de fórmula',            DetalleFormula),
    ('Fórmulas de producto',           FormulaProducto),
    ('Detalles de producto (recetas)', DetalleProducto),
    ('Lotes de materia prima',         LoteMateriaPrima),
    ('Ofertas MP–Proveedor',           MateriaPrimaProveedor),
    ('Materias primas',                MateriaPrima),
    ('Productos terminados',           ProductoTerminado),
    ('Proveedores',                    Proveedor),
    ('Auditoría',                      Auditoria),
    ('Sesiones',                       Session),
    ('Usuarios',                       User),
]

print('  Eliminando datos…\n')

with connection.cursor() as cursor:
    # Desactivar temporalmente foreign keys en SQLite para borrado sin bloqueos
    cursor.execute("PRAGMA foreign_keys = OFF;")
    
    for label, Model in BORRADO:
        try:
            count = Model.objects.count()
            if count > 0:
                table = Model._meta.db_table
                cursor.execute(f'DELETE FROM "{table}"')
                print(f'  🗑️  {label}: {count} registros eliminados')
            else:
                print(f'  ○  {label}: vacío')
        except Exception as e:
            print(f'  ⚠  {label}: error ({e})')

    cursor.execute("PRAGMA foreign_keys = ON;")

# ── Limpiar también archivos de modelos entrenados ──
from django.conf import settings
modelos_dir = getattr(settings, 'MODEL_STORAGE', None)
if modelos_dir and Path(modelos_dir).exists():
    import shutil
    for f in Path(modelos_dir).glob('*'):
        if f.is_file():
            f.unlink()
        elif f.is_dir():
            shutil.rmtree(f)
    print(f'\n  🧹 Directorio de modelos limpiado: {modelos_dir}')

# ── Resetear secuencias autoincrement (SQLite) ──
with connection.cursor() as cursor:
    try:
        cursor.execute("DELETE FROM sqlite_sequence")
        print('  🔄 Secuencias autoincrement reseteadas')
    except Exception:
        pass  # No aplica si usa PostgreSQL u otra BD

print('\n' + '═' * 60)
print('  ✅  Base de datos limpia. Sistema como nuevo.')
print('═' * 60 + '\n')
