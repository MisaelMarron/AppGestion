@echo off
echo ============================================
echo   Generando producciones simuladas
echo ============================================
echo.
cd /d "%~dp0.."
call venv\Scripts\activate.bat 2>nul
python scripts\02_generar_producciones.py
echo.
pause
