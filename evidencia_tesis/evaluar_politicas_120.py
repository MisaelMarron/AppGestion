"""Compara políticas de compra sin alterar la base sintética de 120 días."""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.utils import timezone
from inventario.models import MateriaPrima
from inventario.procurement import elegir_oferta
from produccion.models import Produccion
from produccion.services.forecasting.preprocessing import preparar
from produccion.services.forecasting.models import PARAMETROS, ajustar, predecir
from produccion.services.forecasting.evaluation import metricas, seleccionar
from evidencia_tesis.politicas import simular


def main():
    db = str(django.conf.settings.DATABASES['default']['NAME'])
    if Path(db).name != 'tesis_demo_120.sqlite3':
        raise SystemExit('Use OPERA_DB_PATH con la base aislada tesis_demo_120.sqlite3.')
    ultima = Produccion.objects.filter(sintetica=True).order_by('-fecha').first()
    if not ultima:
        raise SystemExit('La base aislada no contiene producciones sintéticas.')
    corte = timezone.localtime(ultima.fecha).date() + timedelta(days=1)
    resultados = []
    for materia in MateriaPrima.objects.filter(activo=True).order_by('codigo'):
        serie, calidad = preparar(materia, corte)
        if len(serie) < 100 or calidad.get('registros_utilizados', 0) < 30:
            continue
        oferta = elegir_oferta(materia)
        if not oferta:
            continue
        externo = max(1, int(len(serie) * 0.2))
        train, test = serie.iloc[:-externo], serie.iloc[-externo:]
        interior = max(2, int(len(train) * 0.8))
        fit, validacion = train.iloc[:interior], train.iloc[interior:]
        candidatos = []
        for nombre in PARAMETROS:
            try:
                modelo, _ = ajustar(nombre, fit)
                predicho = predecir(nombre, modelo, fit, len(validacion))
                candidatos.append({'modelo': nombre, 'metricas': metricas(validacion, predicho)})
            except Exception as exc:
                candidatos.append({'modelo': nombre, 'error': str(exc)})
        mejor = seleccionar(candidatos)
        if not mejor:
            continue
        plazo = max(1, oferta.lead_time_dias)
        cobertura = min(materia.cobertura_dias, 30)
        horizonte = len(test) + plazo + cobertura + 1
        modelo, _ = ajustar(mejor['modelo'], train)
        pred_modelo = predecir(mejor['modelo'], modelo, train, horizonte)
        base, _ = ajustar('Promedio móvil', train)
        pred_base = predecir('Promedio móvil', base, train, horizonte)
        # Mismos costos, stock inicial y demanda real para ambas alternativas.
        stock_inicial = max(1, float(train.tail(14).mean()) * plazo)
        common = dict(plazo=plazo, cobertura=cobertura,
                      inventario_inicial=stock_inicial, precio=oferta.precio,
                      moq=oferta.moq, multiplo=oferta.multiplo)
        real = test.tolist()
        sistema = simular(real, pred_modelo, **common)
        referencia = simular(real, pred_base, **common)
        resultados.append({
            'insumo': materia.codigo, 'dias_entrenamiento': len(train),
            'dias_prueba': len(test), 'modelo_seleccionado': mejor['modelo'],
            'rmse_sistema': metricas(test, pred_modelo[:len(test)])['rmse'],
            'rmse_promedio_movil': metricas(test, pred_base[:len(test)])['rmse'],
            'supuestos': {'plazo_dias': plazo, 'cobertura_dias': cobertura,
                          'inventario_inicial': stock_inicial, 'precio_unitario': float(oferta.precio),
                          'moq': float(oferta.moq), 'multiplo': float(oferta.multiplo),
                          'costo_pedido': 0, 'costo_mantenimiento_por_unidad_dia': 0.02,
                          'costo_faltante_por_unidad': 5},
            'sistema': sistema, 'promedio_movil': referencia,
        })
    if not resultados:
        raise SystemExit('Ningún insumo reúne los requisitos de evaluación.')
    summary = {'insumos': len(resultados), 'dias_prueba_por_insumo': sorted(set(x['dias_prueba'] for x in resultados)),
               'sistema_dias_quiebre': sum(x['sistema']['dias_quiebre'] for x in resultados),
               'referencia_dias_quiebre': sum(x['promedio_movil']['dias_quiebre'] for x in resultados),
               'sistema_costo_simulado': sum(x['sistema']['costo_simulado'] for x in resultados),
               'referencia_costo_simulado': sum(x['promedio_movil']['costo_simulado'] for x in resultados),
               'sistema_atencion_media_pct': mean(x['sistema']['nivel_atencion_pct'] for x in resultados),
               'referencia_atencion_media_pct': mean(x['promedio_movil']['nivel_atencion_pct'] for x in resultados)}
    result = {'fuente': Path(db).name, 'corte': corte.isoformat(),
              'metodo': '120 días sintéticos; último 20 % externo; elección dentro del 80 % previo; pronóstico fijado antes de prueba; mismos supuestos',
              'limite': 'Contrafactual sintético sin costos reales ni ejecución de compras de la empresa.',
              'resumen': summary, 'por_insumo': resultados}
    output = ROOT / 'evidencia_tesis' / 'resultados' / 'cp12_politicas_120.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f'Evidencia: {output}')


if __name__ == '__main__':
    main()
