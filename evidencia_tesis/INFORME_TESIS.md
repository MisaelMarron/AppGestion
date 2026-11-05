# Evidencia de validación de OperaStock

**Fecha de corte:** 5 de noviembre de 2026. **Entorno:** Django, Python y SQLite aislada. Los datos de producción se generan para las pruebas y no son registros operativos de una empresa.

## Suite automatizada

Ejecute `python manage.py test --verbosity 2` desde la raíz del repositorio. La suite incluye 18 pruebas y las 18 fueron satisfactorias en la revisión de este informe. `tests.py` conserva los casos originales y `test_ampliacion.py` añade tres verificaciones:

| Caso | Entrada y resultado esperado | Resultado observado |
| --- | --- | --- |
| CP-09, fuga temporal | Alterar el consumo del día 26 de una serie de 30 días; los 25 valores anteriores deben ser idénticos. | Los 25 valores previos no cambiaron; el valor del día 26 sí cambió. |
| CP-10, reposición | Stock 5 kg, 1 kg/día, plazo 3 días, cobertura 7, MOQ 5 y múltiplo 4: SS 0, ROP 3, objetivo 10, compra 8, pedido al día siguiente. | El cálculo del sistema coincidió con los valores independientes. |
| CP-11, sesión | El administrador cierra una sesión de operador; la siguiente solicitud protegida debe exigir autenticación. | Sesión inactiva y redirección HTTP 302. |

Estas pruebas se ejecutan en la base temporal que crea Django. El recorrido visual de las interfaces fue informado por el autor de la tesis y no forma parte de la suite automatizada.

## Evaluación de pronósticos en 365 días

El escenario generado para la evaluación comprendió del 5 de noviembre de 2025 al 4 de noviembre de 2026: 796 producciones, 5124 registros de consumo y 13 insumos. El script `scripts/02_generar_producciones.py` usa semilla 42 y permite generar el historial con `--dias 365`. No debe ejecutarse contra la base habitual del proyecto.

Para reproducirlo, cree una base de prueba separada mediante `OPERA_DB_PATH`, aplique las migraciones, cree un usuario administrador en esa base y ejecute en orden `scripts/01_cargar_datos_iniciales.py`, `scripts/02_generar_producciones.py --dias 365` y `evidencia_tesis/evaluar_365.py`. El evaluador exige `OPERA_DB_PATH` y guarda el desglose en `resultados/evaluacion_365.json`. La generación depende de la fecha de ejecución; para reproducir exactamente el mismo período y cifras se debe usar la fecha de corte indicada arriba.

El evaluador reserva el 20 % final de cada serie para prueba externa. Dentro del 80 % anterior divide de nuevo cronológicamente para elegir entre Holt-Winters, SARIMA, Random Forest y promedio móvil, reajusta el ganador solo con el tramo de entrenamiento externo y lo contrasta con el promedio móvil sobre los mismos días finales. En el escenario registrado, los 13 insumos fueron evaluables: 11 obtuvieron menor RMSE que la referencia y dos, mayor. La media de RMSE fue 0,8856 kg frente a 1,0510 kg. Se preservan los casos desfavorables y el desglose por insumo.

## Alcance

La suite y los recorridos HTTP verifican reglas y flujos bajo las entradas ensayadas. La evaluación cronológica mide error retrospectivo en el escenario de prueba. La comparación de políticas de compra CP-12 tiene un protocolo diseñado, pero aún no se ha ejecutado ni medido una reducción de faltantes, inventario o costos en operación.
