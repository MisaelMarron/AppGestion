from django.db import migrations
from django.utils import timezone


def copiar_fecha(apps,schema_editor):
    Orden = apps.get_model('inventario','OrdenCompra')
    for orden in Orden.objects.all().iterator():
        orden.fecha_pedido = timezone.localtime(orden.fecha).date()
        orden.save(update_fields=['fecha_pedido'])


class Migration(migrations.Migration):
    dependencies = [('inventario','0009_ordencompra_fecha_pedido_ordencompra_observacion_and_more')]
    operations = [migrations.RunPython(copiar_fecha,migrations.RunPython.noop)]
