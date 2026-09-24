# Ampliación de OperaStock

## Auditoría inicial — 24/09/2026

Se amplió el proyecto existente. Se conservaron los cambios locales previos en proveedores, inventario, pronóstico y templates. La base operativa tenía 10 materias primas, 4 producciones y 12 consumos al comenzar la ampliación. No se incorporaron datos sintéticos a esa base.

### Arquitectura encontrada

- Python 3.13 y Django 5.2.5; ORM, Django Auth y SQLite.
- `accounts`: usuario personalizado, roles administrador/operador, sesiones y perfil.
- `inventario`: proveedores, insumos, productos terminados, movimientos y ajustes.
- `produccion`: dos representaciones de recetas; flujo web de producción inmediata; estimación de reposición por promedio y tendencia.
- `dashboard`: indicadores de stock mínimo y movimientos. Leía `OrdenProduccion`, aunque el flujo web registraba `Produccion`.
- `templates/` y `static/`: Bootstrap 5, iconos, HTML/CSS/JavaScript. Se conserva el estilo.
- No había pandas, numpy, scikit-learn, statsmodels ni joblib instalados. PostgreSQL no estaba configurado efectivamente.
- Había una sola prueba: creación de productos demo.

### Modelos y tablas previos

| Modelo | Tabla | Relaciones principales |
|---|---|---|
| CustomUser | accounts_customuser | Auth, grupos, permisos, sesiones |
| UserSession | accounts_usersession | N:1 usuario |
| Proveedor | inventario_proveedor | 1:N insumos por proveedor principal |
| MateriaPrima | inventario_materiaprima | proveedor opcional, recetas, consumos, movimientos |
| ProductoTerminado | inventario_productoterminado | recetas, producción, movimientos |
| MovimientoInventario | inventario_movimientoinventario | insumo/producto, usuario |
| FormulaProducto | produccion_formulaproducto | N:1 producto terminado |
| DetalleFormula | produccion_detalleformula | fórmula + materia prima |
| DetalleProducto | produccion_detalleproducto | producto + materia prima; receta usada por la interfaz |
| Produccion | produccion_produccion | producto, cantidad y fecha |
| ConsumoMateriaPrima | produccion_consumomateriaprima | producción + materia prima |
| OrdenProduccion | produccion_ordenproduccion | fórmula, producto, usuario; `producir()` sin implementar |

Se mantienen además las tablas propias de Django: permisos, grupos, sesiones, admin, content types y migraciones.

### Estado inicial por característica

| Estado | Característica |
|---|---|
| ✅ Ya implementado | Autenticación, usuarios, roles, sesiones, CRUD de insumos/productos/proveedores, recetas por producto, consumo vinculado a producción |
| 🟡 Parcial | Historial sin pantalla; pronóstico promedio/tendencia sin evaluación; fecha/cantidad sugerida sin persistencia; lead time fijo; dashboard; movimientos |
| 🔧 Requería modificación | Producción y ajustes sin transacción integral; ejecución repetible; movimientos con menor precisión; referencias del dashboard; conservación de recetas históricas; posibilidad de cambiar el rol desde perfil propio |
| ❌ No implementado | Preprocesamiento, características temporales, HW/SARIMA/RF, evaluación temporal, selección, artefactos y pronósticos persistidos |
| ❌ No implementado | Relación N:M proveedores, reservas, seguridad estadística, ROP predictivo, órdenes/recepción, lead time real |
| ❌ No implementado | Anomalías revisables, ABC/XYZ, lotes/FEFO, retroalimentación y auditoría de negocio |

## Arquitectura ampliada

No se creó otro proyecto ni se renombraron rutas previas. Los modelos nuevos pertenecen a las apps existentes; `models.py` importa sus definiciones separadas para mantener archivos manejables.

```text
produccion/
  models.py                    # Producción, receta, consumo y planificación existentes
  forecast_models.py           # Entrenamiento, Pronostico, EvaluacionPronostico
  predictive_forms.py
  predictive_views.py
  services/
    operaciones.py             # receta común, reserva, producción, cancelación
    clasificacion.py           # ABC/XYZ
    forecasting/
      preprocessing.py
      features.py
      models.py
      evaluation.py
      training.py
      prediction.py
  management/commands/
    entrenar_modelos.py
    evaluar_pronosticos.py
    generar_demo_predictiva.py
inventario/
  models.py                    # Catálogos existentes ampliados
  abastecimiento_models.py     # Proveedores, compras, reservas, lotes y auditoría
  services.py                  # Stock, ajustes, FEFO, auditoría
  procurement.py               # Política, sugerencias, aprobación, recepción
```

Entidades añadidas: `MateriaPrimaProveedor`, `ReservaInventario`, `SugerenciaCompra`, `OrdenCompra`, `DetalleOrdenCompra`, `LeadTimeReal`, `LoteMateriaPrima`, `ConsumoLote`, `Auditoria`, `Entrenamiento`, `Pronostico` y `EvaluacionPronostico`.

La relación insumo–proveedor es N:M mediante ofertas. Se conserva `MateriaPrima.proveedor` para compatibilidad con el pronóstico anterior. La migración copia los proveedores principales existentes a ofertas; las ofertas posteriores se gestionan en el nuevo panel. Las órdenes de compra guardan sus precios en Decimal y relacionan sus líneas con la oferta. Cada sugerencia conserva el pronóstico y el cálculo usado. Cada pronóstico conserva el entrenamiento y la versión.

## Migraciones y conservación

Se crearon migraciones aditivas de inventario desde `0005` y de producción desde `0004`, además de una migración de datos para proveedores existentes y producciones ya ejecutadas. No se editaron migraciones anteriores.

Antes de migrar se creó `backups/antes_ampliacion.sqlite3` usando la API de respaldo de SQLite. Ese archivo, los artefactos y los resultados de QA están excluidos de Git.

Los consumos históricos anteriores conservan sus valores originales. No se inventan recetas pasadas: si no existía copia, la interfaz lo indica. Las nuevas producciones guardan `receta_snapshot` y usuario. Las relaciones históricas relevantes usan PROTECT. Los movimientos nuevos admiten cinco decimales; la precisión perdida en movimientos antiguos no puede recuperarse.

## Uso del sistema

1. Iniciar sesión y abrir **Aprovisionamiento** en la navegación o en el dashboard.
2. Abrir **Ver análisis** de una materia prima.
3. Configurar ofertas: proveedor, precio, lead time, MOQ, múltiplo y presentación.
4. Configurar nivel de servicio y días de cobertura.
5. Como administrador, pulsar **Reentrenar modelos**.
6. Generar pronóstico de 7/15/30/60/180/365 días. Para calcular la compra se requiere cubrir al menos LT + cobertura. Un horizonte corto sigue siendo válido para consultar demanda.
7. Revisar cálculos y generar una sugerencia. En **Sugerencias y compras**, aprobar o rechazar.
8. La aprobación crea una orden; registrar Enviada → Confirmada → En tránsito → Recibida → Cerrada.
9. La recepción es total, transaccional y única. Incrementa stock, registra movimiento, lote si corresponde y lead time real. Los cambios de estado no envían mensajes externos.
10. Actualizar la comparación con consumos reales cuando existan días completos posteriores al pronóstico.

Operadores consultan análisis e históricos, registran producción y planifican/reservan. Administradores configuran política/ofertas, entrenan, generan pronósticos/sugerencias, deciden compras, reciben y revisan exclusiones/auditoría.

### Reservas y recetas

Planificar una orden permite usar una `FormulaProducto` específica o, dejando fórmula vacía, la receta vigente `DetalleProducto`. Reservar copia la receta: una edición posterior no cambia una reserva ya comprometida. Ejecutar descuenta stock, consume lotes FEFO y libera reservas en una sola transacción. Cancelar libera reservas sin modificar stock físico.

Stock disponible = físico − reservado. Posición = disponible + compras abiertas. Las reservas se descuentan conservadoramente antes de aplicar el pronóstico estadístico; el pronóstico representa demanda adicional, no una conciliación automática de producción planificada con demanda histórica. No se añadieron características de planes actuales al entrenamiento retrospectivo porque no existen snapshots históricos que prueben cuándo se conoció cada plan.

### Lotes

La gestión es opcional por materia prima. Para habilitarla con existencias, distribuir el stock ya existente mediante **Registrar lote de apertura** y luego activar la política. La suma de lotes debe conciliar con stock físico; abrir lotes no incrementa stock. Las entradas posteriores requieren número de lote. FEFO omite lotes vencidos y consume primero vencimiento, luego recepción y ID. Los lotes sin vencimiento se usan al final. El stock vencido se muestra por separado y se excluye del stock utilizable en reservas, producción, proyección y cantidad de compra. El pronóstico no simula caducidad futura.

## Metodología verificable

### Preparación y características

- Fuente: consumos operativos no sintéticos, hasta el día anterior al corte en America/Lima. El día actual incompleto y el futuro se excluyen.
- Duplicados: se eliminan únicamente IDs repetidos de la extracción; consumos legítimos coincidentes se suman.
- Cantidades nulas/no finitas/negativas y fechas inválidas se omiten en la copia derivada, dejando contadores.
- Días sin operaciones desde el primer registro hasta el corte se completan con cero. Esto supone captura operativa completa: ausencia de captura no puede distinguirse automáticamente de ausencia de demanda.
- Un día con exclusión manual queda desconocido y se imputa usando los siete días anteriores; no se convierte automáticamente en cero. No se modifica el histórico.
- Se conservan atípicos; IQR sobre totales diarios los señala para revisión. Excluir/incluir exige motivo y deja auditoría. Reentrenar aplica la decisión.
- Lags 1/7/14/30, medias 7/14/30, desviaciones 7/30, calendario, tendencia y frecuencia. Las ventanas se desplazan un día; no incorporan el objetivo de la fecha predicha.
- Historial con agregación diaria/semanal/mensual; entrenamiento y pronóstico son diarios.

### Entrenamiento y selección

80 % inicial para entrenamiento, 20 % final para evaluación. Todos los candidatos usan las mismas fechas. Random Forest predice recursivamente todo el bloque de prueba; no utiliza valores reales futuros para construir sus lags.

- Holt-Winters: tendencia y estacionalidad aditivas, periodo semanal de 7 días.
- SARIMA: (1,1,1) × (1,0,1,7), máximo 80 iteraciones. Si no converge se registra y descarta, sin presentar métricas falsas. Parámetros centralizados en `forecasting/models.py`.
- Random Forest: 100 árboles, profundidad 8, mínimo 2 por hoja, semilla 42, un proceso.
- Promedio móvil de 7 días: referencia que también puede ganar legítimamente la comparación.

Se habilita la comparación compleja con al menos 45 días en el tramo de entrenamiento y 30 registros operativos. Con menos datos se utiliza el promedio móvil y el estado DATOS_INSUFICIENTES. Sin observaciones válidas se muestra SIN_DATOS y no se genera pronóstico.

MAE y RMSE usan todo el bloque de prueba. MAPE excluye objetivos cero e informa el denominador y cuántos ceros se omitieron; si todos son cero, es nulo. Gana el menor RMSE, con MAE como desempate. Las métricas no son intervalos de confianza ni garantizan precisión futura. No se presume que RF sea el mejor.

El modelo elegido se ajusta otra vez con el histórico completo permitido. Se conserva comparación, validación real/predicha, parámetros, fechas, número de registros, versión y registro de calidad. Los modelos se guardan privadamente en `var/modelos`, con nombre UUID y SHA-256. No hay carga de archivos de modelos desde la interfaz. Joblib solo carga artefactos generados localmente; proteger el directorio y la base sigue siendo necesario porque joblib no es un formato seguro para archivos de terceros.

Un modelo de hasta 30 días de antigüedad puede pronosticar avanzando desde su fecha de corte hasta hoy; se descartan los pasos intermedios. Después exige reentrenamiento. Abrir páginas nunca entrena.

### Política de inventario

SS = Z(nivel de servicio) × desviación poblacional diaria × √LT.

ROP = suma del pronóstico de los primeros LT días + SS.

S = suma del pronóstico de LT + H días + SS.

Q = max(0, S − posición en cobertura). Si Q > 0, se eleva a MOQ y al siguiente múltiplo. MOQ no genera compras si Q = 0.

LT es el promedio histórico de entregas redondeado hacia arriba, o el estimado sin historial. Se registra también desviación del lead time y porcentaje de entregas dentro del plazo estimado. La fórmula de SS usa variabilidad de demanda, no variabilidad conjunta de demanda y LT.

Se elige proveedor activo por menor LT histórico/estimado, luego precio e ID. Se muestran las alternativas. La política no optimiza automáticamente costo total, descuentos ni capacidad de proveedor.

La posición total incluye compras abiertas. Para calcular S−posición solo se descuentan entradas con fecha vigente dentro del horizonte de cobertura; compras atrasadas o posteriores no ocultan necesidades inmediatas. Se advierte cuando una entrega está atrasada.

Simulación: saldo siguiente = saldo actual − demanda + recepciones de esa fecha. Las recepciones se consideran disponibles antes del consumo de su día. Se registra primera fecha de saldo ≤ ROP, ≤ SS y ≤ 0. El plazo de pedido es el menor entre el cruce de ROP y la fecha de seguridad menos LT, sin retroceder antes de hoy. No se resta LT dos veces al ROP. Agotamiento nulo significa que no se alcanza dentro del horizonte, no cobertura ilimitada.

CRÍTICO: disponible ≤ SS o agotamiento antes de poder recibir. ATENCIÓN: posición ≤ ROP o pedido dentro de siete días. En otro caso, ESTABLE. Sin pronóstico/cobertura/proveedor suficiente, no se inventa una compra.

Cada sugerencia almacena explicación determinística y variables. Aprobar vuelve a calcular: cambios de stock, fechas, pronóstico, proveedor, precio o restricciones obligan a regenerar y revisar. Nunca se crea una orden al cargar una página ni al entrenar.

### ABC/XYZ y retroalimentación

ABC usa valor consumido de los últimos 365 días, costo unitario del catálogo y umbrales acumulados 80/95 %. El insumo que cruza un umbral queda en la clase del acumulado anterior. Sin costo no se finge valoración. XYZ usa CV diario: X ≤ 0.5, Y ≤ 1, Z > 1; media cero/sin datos queda sin clasificación. No modifica cantidades recomendadas.

La retroalimentación guarda por pronóstico y fecha: real, predicho, error absoluto y porcentual (nulo para real cero). Solo evalúa días completos y actualiza idempotentemente por si se corrige el histórico. No dispara un entrenamiento automático.

## Comandos reproducibles (PowerShell)

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py test
.\venv\Scripts\python.exe manage.py entrenar_modelos --materia 1 --horizonte 60
.\venv\Scripts\python.exe manage.py evaluar_pronosticos
.\venv\Scripts\python.exe manage.py generar_demo_predictiva --salida var/demo/consumos.csv
.\venv\Scripts\python.exe manage.py runserver
```

`entrenar_modelos` sin `--materia` procesa insumos activos; `--solo-entrenar` omite pronóstico. Se puede programar externamente en el futuro. No se instaló un scheduler ni un servicio adicional.

`generar_demo_predictiva` genera CSV etiquetado SINTETICO_NO_INVESTIGACION con semilla fija, tendencia, estacionalidad, ruido y atípicos; no escribe consumos operativos. El comando anterior `seed_productos_demo` ahora etiqueta producciones nuevas como sintéticas y no borra producciones ya existentes. No se reclasifican automáticamente registros viejos cuya procedencia no puede probarse.

`python scripts/preview_predictivo.py` genera HTML de QA en `var/ui` usando exclusivamente una base temporal de pruebas y modelos entrenados sobre su fixture. Esa vista está rotulada como sintética; sus botones no son una aplicación independiente. Sirve para revisar diseño sin alterar la base operativa.

PostgreSQL usa variables `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`; se incluye psycopg. SQLite sigue siendo predeterminado. Para despliegue configurar también `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` y `DJANGO_ALLOWED_HOSTS`. La verificación de esta entrega se realizó en SQLite; PostgreSQL está preparado, no certificado aquí. En producción concurrente PostgreSQL permite los bloqueos de fila de `select_for_update`; SQLite serializa escrituras y puede devolver bloqueo bajo carga.

## Pruebas y revisión

La suite incluye 28 pruebas aprobadas en la verificación final. Cubre consumo proporcional, reversión ante fallo, producción única, reservas/cancelación/snapshot, stock disponible, compras sin aprobación automática, aprobación/rechazo, sugerencias obsoletas, recepción única, reversión por lote inválido, lead time, fechas de recepción, FEFO/vencidos, SS, ROP, MOQ/múltiplos, métricas y ceros, selección, entrenamiento real, ausencia de fuga temporal, datos insuficientes, anomalías/exclusión, no mutación del origen, separación de sintéticos/futuro, integridad del artefacto, retroalimentación, permisos y páginas antiguas/nuevas.

Se revisó visualmente el análisis con datos de prueba en escritorio y ancho móvil; se corrigió la altura del gráfico. Bootstrap y Chart.js usan CDN, como el frontend previo: las tablas siguen disponibles si el gráfico no puede cargar.

## Alcance y límites deliberados

- Recepciones totales; no se implementaron entregas parciales ni cancelación de compras ya aprobadas.
- Sin LLM ni API externa. La explicación determinística permite agregar un redactor futuro sin delegarle cálculos.
- Sin intervalos predictivos calibrados; se presenta error de validación y advertencias.
- Sin inferir receta, usuario o stock histórico faltante. El stock pasado se reconstruye desde movimientos disponibles y se advierte su limitación.
- No se entrenaron modelos de investigación sobre la base operativa durante la implementación; la muestra actual es pequeña y algunos registros anteriores pueden provenir del comando demo previo.
- Cambios de estado de compras son seguimiento interno; no se contactó a proveedores.

## Fases y archivos afectados

| Fases | Resultado | Archivos principales |
|---|---|---|
| 0 | Auditoría y pruebas de referencia | Este documento, lectura de modelos/rutas/templates/migraciones |
| 1–3 | Integridad, historial, ofertas, reservas y posición | `inventario/models.py`, `abastecimiento_models.py`, `services.py`, `produccion/models.py`, `services/operaciones.py`, migraciones |
| 4–10 | Preparación, features, HW/SARIMA/RF, métricas, selección y pronósticos | `produccion/services/forecasting/*.py`, `forecast_models.py` |
| 11–14 | SS/ROP, fechas/cantidades, sugerencias, compra y recepción | `inventario/procurement.py`, `predictive_views.py`, `predictive_forms.py` |
| 15 | Panel, dashboard y gráficos | `dashboard/views.py`, templates de dashboard/producción, `static/js/predictive.js` |
| 16–18 | Anomalías, ABC/XYZ, lotes/FEFO y auditoría | preprocessing, clasificación, servicios, administración y pantallas |
| 19–20 | Pruebas integrales, revisión visual, comandos y documentación | `produccion/test_predictive.py`, `scripts/preview_predictivo.py`, commands, este documento, README |

Se modificaron además `accounts/views.py` para impedir autoelevación de rol, `config/settings.py`, `requirements.txt`, `.gitignore`, navegación, formularios/vistas de ajustes y producción, y el comando demo previo. Los templates nuevos están bajo `templates/produccion/`; no reemplazan las pantallas anteriores.
