@echo off
echo ============================================
echo   Cargando datos iniciales en OperaStock
echo ============================================
echo.
cd /d "%~dp0.."
call venv\Scripts\activate.bat 2>nul
python scripts\01_cargar_datos_iniciales.py
echo.
pause
