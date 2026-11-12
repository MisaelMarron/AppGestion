# Evidencia de casos de pruebas de OperaStock

**Ejecución:** 12 de noviembre de 2026. **Entorno:** Python 3.13, Django 5.2.5 y SQLite temporal. **Datos de demostración:** base aislada con historial sintético de 120 días, del 7 de julio al 3 de noviembre de 2026.

## Resultado reproducible

`python evidencia_tesis/ejecutar.py` ejecuta `python manage.py test --verbosity 2` y conserva la salida completa en `resultados/ejecucion.txt`. La ejecución final contiene **41 pruebas satisfactorias, cero fallos y cero errores**. El código está en `tests.py`, `test_ampliacion.py`, `test_casos_integrales.py` e `inventario/tests.py`. Las láminas `captura_01_resumen.png` a `captura_04_cp09_cp12.png` se generan únicamente a partir de ese registro mediante `generar_capturas.py`; no son fotografías de la consola.

Los 12 casos CP-01 a CP-12 tienen pasos, entradas y resultados esperados y observados en el capítulo IV de la tesis. CP-09 a CP-12 están incorporados a las tablas de casos y de estado. Las capturas reales de las interfaces IU01–IU17 están en `interfaces/`. Las cinco láminas de resultados se incorporaron al apartado de anexos **Evidencia de casos de pruebas**.

## Evaluación de pronósticos en 365 días

El escenario generado para la evaluación comprendió del 5 de noviembre de 2025 al 4 de noviembre de 2026: 796 producciones, 5124 registros de consumo y 13 insumos. El script `scripts/02_generar_producciones.py` usa semilla 42 y permite generar el historial con `--dias 365`. No debe ejecutarse contra la base habitual del proyecto.

Para reproducirlo, cree una base de prueba separada mediante `OPERA_DB_PATH`, aplique las migraciones, cree un usuario administrador en esa base y ejecute en orden `scripts/01_cargar_datos_iniciales.py`, `scripts/02_generar_producciones.py --dias 365` y `evidencia_tesis/evaluar_365.py`. El evaluador exige `OPERA_DB_PATH` y guarda el desglose en `resultados/evaluacion_365.json`. La generación depende de la fecha de ejecución; para reproducir exactamente el mismo período y cifras se debe usar la fecha de corte indicada arriba.

El evaluador reserva el 20 % final de cada serie para prueba externa. Dentro del 80 % anterior divide de nuevo cronológicamente para elegir entre Holt-Winters, SARIMA, Random Forest y promedio móvil, reajusta el ganador solo con el tramo de entrenamiento externo y lo contrasta con el promedio móvil sobre los mismos días finales. En el escenario registrado, los 13 insumos fueron evaluables: 11 obtuvieron menor RMSE que la referencia y dos, mayor. La media de RMSE fue 0,8856 kg frente a 1,0510 kg. Se preservan los casos desfavorables y el desglose por insumo.

## Hallazgo corregido

La prueba `test_cp04_excluido_no_borra_consumo_valido_del_mismo_dia` reprodujo un defecto de preparación: al excluir un consumo, el proceso sustituía también el consumo válido del mismo día por una media. Se corrigió `preparar_filas` para sumar solo registros válidos e imputar únicamente días que contienen exclusivamente registros excluidos. La prueba pasó tras la corrección.

## CP-12: comparación de políticas

`evaluar_politicas_120.py` separa el último 20 % de cada serie como prueba externa y elige el método usando solo el tramo anterior. `politicas.py` reproduce la misma política objetivo de compra bajo dos pronósticos: el modelo elegido y el promedio móvil. En ambos se usan las mismas observaciones, inventario inicial, oferta, plazo, cobertura, MOQ, múltiplo y supuestos de costo. La evaluación **no modifica compras ni inventario** de la base.

El archivo `resultados/cp12_politicas_120.json` conserva supuestos y resultados por insumo. Diez insumos reunieron las condiciones de evaluación; el tramo externo tuvo 23 o 24 días por serie. Se obtuvo **1 día de quiebre frente a 1** y una atención media de **99,33 %** para ambas políticas. El costo total *simulado* fue **S/ 4 671,83** con el método elegido frente a **S/ 4 747,15** con el promedio móvil. Cinco insumos fueron más baratos y cinco más caros con el primero. `captura_05_cp12_comparacion.png` representa estos datos.

Los costos de pedido, mantenimiento y faltante son supuestos de prueba; no se han medido costos ni reducción de faltantes en una empresa. La conclusión de CP-12 se limita al contrafactual sintético. Para validar un impacto empresarial hacen falta datos operativos reales y observar la política durante su uso.
