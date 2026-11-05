"""Ejecuta los casos de tesis en una base temporal y conserva la salida íntegra."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / 'resultados'
OUT.mkdir(exist_ok=True)
command = [sys.executable, 'manage.py', 'test', '--verbosity', '2', '--no-color']
run = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
(OUT / 'ejecucion.txt').write_text(run.stdout, encoding='utf-8')
print(f'Registro guardado en: {OUT / "ejecucion.txt"}')
for line in run.stdout.splitlines():
    if line.startswith(('Ran ', 'FAILED', 'OK')):
        print(line)
raise SystemExit(run.returncode)
