# Evidencia de casos de pruebas de OperaStock

**Ejecución:** 12 de noviembre de 2026. **Entorno:** Python 3.13, Django 5.2.5 y SQLite temporal. **Datos de demostración:** base aislada con historial sintético de 120 días, del 7 de julio al 3 de noviembre de 2026.

## Resultado reproducible

`python evidencia_tesis/ejecutar.py` ejecuta `python manage.py test --verbosity 2` y conserva la salida completa en `resultados/ejecucion.txt`. La ejecución final contiene **41 pruebas satisfactorias, cero fallos y cero errores**. El código está en `tests.py`, `test_ampliacion.py`, `test_casos_integrales.py` e `inventario/tests.py`. Las láminas `captura_01_resumen.png` a `captura_04_cp09_cp12.png` se generan únicamente a partir de ese registro mediante `generar_capturas.py`; no son fotografías de la consola.

Los 12 casos CP-01 a CP-12 tienen pasos, entradas y resultados esperados y observados en el capítulo IV de la tesis. CP-09 a CP-12 están incorporados a las tablas de casos y de estado. Las capturas reales de las interfaces IU01–IU17 están en `interfaces/`. Las cinco láminas de resultados se incorporaron al apartado de anexos **Evidencia de casos de pruebas**.

## Evaluación de pronósticos en 365 días

El escenario generado para la evaluación comprendió del 5 de noviembre de 2025 al 4 de noviembre de 2026: 796 producciones, 5124 registros de consumo y 13 insumos. El script `scripts/02_generar_producciones.py` usa semilla 42 y permite generar el historial con `--dias 365`. No debe ejecutarse contra la base habitual del proyecto.

Para reproducirlo, cree una base de prueba separada mediante `OPERA_DB_PATH`, aplique las migraciones, cree un usuario administrador en esa base y ejecute en orden `scripts/01_cargar_datos_iniciales.py`, `scripts/02_generar_producciones.py --dias 365 --fecha-fin 2026-11-04`, `evidencia_tesis/evaluar_365.py` y `evidencia_tesis/comparar_hw_rf_articulo.py`. El evaluador de la tesis exige `OPERA_DB_PATH` y guarda el desglose en `resultados/evaluacion_365.json`; la comparación del artículo escribe `resultados/comparacion_articulo_365.json`. La fecha final explícita conserva el período del 5 de noviembre de 2025 al 4 de noviembre de 2026 aunque se ejecute otro día.

El evaluador reserva el 20 % final de cada serie para prueba externa. Dentro del 80 % anterior divide de nuevo cronológicamente para elegir entre Holt-Winters, SARIMA, Random Forest y promedio móvil, reajusta el ganador solo con el tramo de entrenamiento externo y lo contrasta con el promedio móvil sobre los mismos días finales. En el escenario registrado, los 13 insumos fueron evaluables: 11 obtuvieron menor RMSE que la referencia y dos, mayor. La media de RMSE fue 0,8856 kg frente a 1,0510 kg. Se preservan los casos desfavorables y el desglose por insumo.

## Indicadores complementarios del pronóstico

Con la misma base aislada, ejecute `OPERA_DB_PATH=/ruta/a/tesis_demo_365.sqlite3 python evidencia_tesis/medir_indicadores.py`. El script usa los modelos seleccionados en `resultados/evaluacion_365.json`, recorta la serie al 4 de noviembre de 2026 para conservar la ventana evaluada y escribe `resultados/indicadores_365.json`. Reajusta cada ganador en el 80 % inicial, calcula R² sobre el 20 % final y mide el tiempo de un ajuste y de tres pronósticos consecutivos de 60 días. Informa la mediana de esos tres pronósticos para cada insumo.

En esta ejecución (Python 3.12.14, scikit-learn 1.9.1 y statsmodels 0.15.0), la mediana de R² externo fue 0,0048; cuatro de 13 valores fueron negativos y el rango fue −0,0473 a 0,5336. La mediana del tiempo de ajuste fue 99,83 ms (50,75 a 269,19 ms); la mediana de tiempo de pronóstico entre insumos fue 1,09 ms (0,84 a 305,27 ms). Los tiempos describen solo el cálculo local de esta ejecución; no incluyen red ni renderizado y pueden variar en otro equipo. El archivo JSON conserva los 13 resultados individuales y las tres repeticiones de pronóstico.

## Comparación reproducible para el artículo

Ejecute `OPERA_DB_PATH=/ruta/tesis_demo_365.sqlite3 python evidencia_tesis/comparar_hw_rf_articulo.py`. El corte fijo excluye desde el 5 de noviembre de 2026. El archivo `resultados/comparacion_articulo_365.json` conserva por insumo el RMSE y MAE externos de Holt-Winters, Random Forest, promedio móvil de siete días y referencia estacional semanal. El experimento principal usa el 80 % inicial para ajuste y el 20 % final para prueba; la sensibilidad reajusta los modelos en tres orígenes no superpuestos de 28 días. Un bootstrap descriptivo de 10 000 remuestreos de las 13 diferencias HW−RF usa semilla 42.

En la prueba principal, Holt-Winters obtuvo RMSE medio 0,8794 kg y Random Forest 0,9043 kg, con ocho y cinco victorias por insumo. Las ventanas de sensibilidad dieron 6–7, 6–7 y 12–1 victorias HW–RF. El intervalo bootstrap del promedio HW−RF fue [−0,0729; 0,0176] kg; incluye cero y no prueba superioridad estable ni generalización fuera del escenario generado.

## Hallazgo corregido

La prueba `test_cp04_excluido_no_borra_consumo_valido_del_mismo_dia` reprodujo un defecto de preparación: al excluir un consumo, el proceso sustituía también el consumo válido del mismo día por una media. Se corrigió `preparar_filas` para sumar solo registros válidos e imputar únicamente días que contienen exclusivamente registros excluidos. La prueba pasó tras la corrección.

## CP-12: comparación de políticas

`evaluar_politicas_120.py` separa el último 20 % de cada serie como prueba externa y elige el método usando solo el tramo anterior. `politicas.py` reproduce la misma política objetivo de compra bajo dos pronósticos: el modelo elegido y el promedio móvil. En ambos se usan las mismas observaciones, inventario inicial, oferta, plazo, cobertura, MOQ, múltiplo y supuestos de costo. La evaluación **no modifica compras ni inventario** de la base.

El archivo `resultados/cp12_politicas_120.json` conserva supuestos y resultados por insumo. Diez insumos reunieron las condiciones de evaluación; el tramo externo tuvo 23 o 24 días por serie. Se obtuvo **1 día de quiebre frente a 1** y una atención media de **99,33 %** para ambas políticas. El costo total *simulado* fue **S/ 4 671,83** con el método elegido frente a **S/ 4 747,15** con el promedio móvil. Cinco insumos fueron más baratos y cinco más caros con el primero. `captura_05_cp12_comparacion.png` representa estos datos.

Los costos de pedido, mantenimiento y faltante son supuestos de prueba; no se han medido costos ni reducción de faltantes en una empresa. La conclusión de CP-12 se limita al contrafactual sintético. Para validar un impacto empresarial hacen falta datos operativos reales y observar la política durante su uso.
