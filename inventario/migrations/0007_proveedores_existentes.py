from django.db import migrations


def migrar(apps, schema_editor):
    Materia = apps.get_model('inventario','MateriaPrima')
    Oferta = apps.get_model('inventario','MateriaPrimaProveedor')
    Produccion = apps.get_model('produccion','Produccion')
    for materia in Materia.objects.exclude(proveedor=None).select_related('proveedor').iterator():
        Oferta.objects.get_or_create(materia_prima_id=materia.pk,proveedor_id=materia.proveedor_id,
            defaults={'precio':materia.costo_unitario or 0,'lead_time_dias':materia.proveedor.tiempo_entrega_dias})
    Produccion.objects.filter(consumos__isnull=False).update(ejecutada=True)


class Migration(migrations.Migration):
    dependencies = [('inventario','0006_sugerenciacompra_pronostico_ordencompra_sugerencia_and_more')]
    operations = [migrations.RunPython(migrar,migrations.RunPython.noop)]
