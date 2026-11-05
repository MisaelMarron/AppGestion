# Evidencia de pruebas de OperaStock

**Fecha:** 4 de noviembre de 2026. **Entorno:** Python 3.13, Django 5.2.5 y SQLite. **Datos:** historial sintético aislado de 120 días calendario, entre el 7 de julio y el 3 de noviembre de 2026.

## Correcciones realizadas antes de la validación

Se corrigieron tres defectos reproducidos en la versión inicial: la edición de cantidad de una sugerencia era interceptada por otra ruta; el rechazo borraba la sugerencia y su trazabilidad; el CSV predictivo mostraba porcentajes predeterminados sin evaluación. Se eliminaron además las métricas y nombres de modelos de la interfaz destinada al usuario. El CSV técnico queda limitado a administradores y muestra métricas solo cuando existen.

## Resultado verificable

El comando `python manage.py test --verbosity 2` ejecuta la suite descubierta por Django. El registro íntegro está en `resultados/ejecucion.txt` y la lámina derivada de este registro en `resultados/captura_01_resumen.png`. El archivo `tests.py` conserva las entradas, aserciones y efectos comprobados. El verificador `verificar_demo_120.py` produjo `resultados/verificacion_120_dias.json` sobre una base aislada de la base habitual del proyecto.

La base de demostración contiene 120 días calendario, 101 días con producción, 257 producciones sintéticas, 1654 consumos, 13 insumos con entrenamiento y 13 pronósticos. Las capturas de la ejecución real del sistema se encuentran en `interfaces/IU01_login.jpg` a `interfaces/IU17_historial_producciones.jpg`, y se insertaron en la sección de interfaces de la tesis.

## Alcance de la conclusión

Las pruebas automatizadas acreditan los cálculos y flujos cubiertos, el control de acceso y la persistencia de decisiones. El historial sintético permite reproducir las funciones del sistema; no demuestra precisión predictiva ni reducción de faltantes en una empresa real. Para sostener esas conclusiones se requieren series operativas reales, evaluación cronológica fuera de muestra, comparación contra una línea base, y medición de quiebres, inventario y costos. La aceptación de usuarios exige participantes y respuestas reales anonimizadas.

El plan CP09–CP18 incorporado a la tesis separa estos estudios pendientes de las verificaciones de software ya ejecutadas. Cada futura ejecución debe conservar versión, datos iniciales, actor, fecha, resultado esperado, resultado observado, evidencia e incidencia.
