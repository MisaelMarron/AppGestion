"""Genera láminas fieles al log y al JSON de la evaluación sintética."""
from collections import Counter
from pathlib import Path
import json
import re

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / 'resultados'
log = (OUT / 'ejecucion.txt').read_text(encoding='utf-8-sig', errors='replace')
rows = re.findall(r'(test_\S+).*?\.\.\. (ok|FAIL|ERROR)', log)
total = int(re.search(r'Ran (\d+) tests?', log).group(1))
assert len(rows) == total, f'Registro incompleto: {len(rows)} filas para {total} pruebas'
assert 'OK' in log and all(status == 'ok' for _, status in rows), 'No se publica una lámina verde si hay fallos'
counts = Counter(int(re.search(r'_cp(\d+)', name).group(1)) for name, _ in rows if re.search(r'_cp(\d+)', name))
regular = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 20)
small = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 17)
heading = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 34)


def canvas(title, subtitle, height):
    im = Image.new('RGB', (1650, height), 'white')
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1650, 118), fill='#17324d')
    d.text((50, 22), title, font=heading, fill='white')
    d.text((51, 75), subtitle, font=small, fill='#d7e6ef')
    return im, d


im, d = canvas('Resultado de la suite de pruebas', 'OperaStock · base temporal Django · 12/11/2026', 760)
d.text((52, 145), f'{total} pruebas ejecutadas  ·  {total} satisfactorias  ·  0 fallos  ·  0 errores', font=regular, fill='#166534')
d.text((52, 188), 'Comando: python manage.py test --verbosity 2', font=small, fill='#334155')
for n in range(1, 13):
    col, row = (n - 1) // 6, (n - 1) % 6
    x, y = 53 + 790 * col, 245 + 73 * row
    d.rounded_rectangle((x, y, x + 725, y + 55), radius=7, fill='#f1f5f9')
    d.text((x + 18, y + 11), f'CP-{n:02d}', font=regular, fill='#17324d')
    d.text((x + 155, y + 11), f'{counts[n]} prueba(s) satisfactoria(s)', font=regular, fill='#166534')
d.text((53, 704), '1 prueba adicional: catálogo de productos y fórmulas. Fuente: ejecucion.txt.', font=small, fill='#475569')
im.save(OUT / 'captura_01_resumen.png')

for start, end, filename in [(1, 4, 'captura_02_cp01_cp04.png'),
                             (5, 8, 'captura_03_cp05_cp08.png'),
                             (9, 12, 'captura_04_cp09_cp12.png')]:
    chosen = [(name, status) for name, status in rows if (m := re.search(r'_cp(\d+)', name)) and start <= int(m.group(1)) <= end]
    height = 220 + 47 * len(chosen)
    im, d = canvas(f'Evidencia CP-{start:02d} a CP-{end:02d}',
                   'Identificadores exactos de las aserciones ejecutadas · fuente: ejecucion.txt', height)
    for i, (name, status) in enumerate(chosen):
        y = 151 + 47 * i
        d.text((53, y), name, font=small, fill='#17324d')
        d.text((1460, y), status.upper(), font=small, fill='#166534')
        d.line((53, y + 32, 1597, y + 32), fill='#e2e8f0')
    d.text((53, height - 47), f'{len(chosen)} pruebas satisfactorias en esta lámina · 12/11/2026', font=small, fill='#475569')
    im.save(OUT / filename)

result = json.loads((OUT / 'cp12_politicas_120.json').read_text(encoding='utf-8'))
im, d = canvas('CP-12 · costo simulado por insumo',
               'Diferencia sistema − promedio móvil; negativo favorece al sistema · 120 días sintéticos', 925)
items = result['por_insumo']
largest = max(abs(x['sistema']['costo_simulado'] - x['promedio_movil']['costo_simulado']) for x in items)
middle = 850
d.line((middle, 140, middle, 760), fill='#64748b', width=2)
for i, x in enumerate(items):
    y = 155 + i * 59
    diff = x['sistema']['costo_simulado'] - x['promedio_movil']['costo_simulado']
    width = int(abs(diff) / largest * 500) if largest else 0
    left, right = (middle - width, middle) if diff < 0 else (middle, middle + width)
    d.text((53, y + 5), x['insumo'], font=regular, fill='#17324d')
    d.rectangle((left, y, right, y + 28), fill='#166534' if diff < 0 else '#b45309')
    d.text((1370, y + 5), f'{diff:+.2f} S/', font=regular, fill='#17324d')
s = result['resumen']
d.text((53, 787), f"Costo total: sistema {s['sistema_costo_simulado']:.2f} S/; referencia {s['referencia_costo_simulado']:.2f} S/.", font=small, fill='#334155')
d.text((53, 820), f"Quiebres: {s['sistema_dias_quiebre']} vs. {s['referencia_dias_quiebre']}. Costos unitarios son supuestos, no cifras empresariales.", font=small, fill='#334155')
d.text((53, 862), 'Fuente: cp12_politicas_120.json y evaluar_politicas_120.py · 12/11/2026', font=small, fill='#475569')
im.save(OUT / 'captura_05_cp12_comparacion.png')
