"""Crea una lámina de resultados a partir del registro real de Django."""
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / 'resultados'
log = (OUT / 'ejecucion.txt').read_text(encoding='utf-8-sig', errors='replace')
rows = re.findall(r'(test_\S+).*?\.\.\. (ok|FAIL|ERROR)', log)
total = int(re.search(r'Ran (\d+) tests?', log).group(1))
assert len(rows) == total, f'Registro incompleto: {len(rows)} filas para {total} pruebas'
assert 'OK' in log and all(status == 'ok' for _, status in rows), 'La suite debe aprobar antes de publicar esta lámina'

font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 19)
small = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 16)
title = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 31)
height = 210 + 44 * total
im = Image.new('RGB', (1650, height), 'white')
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 1650, 112), fill='#17324d')
d.text((52, 24), 'Ejecución automatizada de OperaStock', font=title, fill='white')
d.text((53, 70), 'Django TestCase · base temporal SQLite · 04/11/2026', font=small, fill='#d7e6ef')
d.text((54, 136), 'Comando: .\\venv\\Scripts\\python.exe manage.py test --verbosity 2', font=small, fill='#334155')
for i, (name, status) in enumerate(rows):
    y = 178 + 44 * i
    d.text((55, y), name, font=font, fill='#172b4d')
    d.text((1400, y), status, font=font, fill='#166534')
    d.line((54, y + 29, 1596, y + 29), fill='#e5e7eb')
d.text((55, height - 54), f'Resultado: {total} pruebas aprobadas. Fuente: resultados/ejecucion.txt', font=small, fill='#166534')
im.save(OUT / 'captura_01_resumen.png')
