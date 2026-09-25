@echo off
echo ============================================
echo   Limpieza total de base de datos
echo ============================================
echo.
cd /d "%~dp0.."
call venv\Scripts\activate.bat 2>nul
python scripts\03_limpiar_base_datos.py
echo.
pause
