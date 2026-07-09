@echo off
cd /d "%~dp0"
call "%~dp0venv\Scripts\activate.bat"
python manage.py migrate
python manage.py seed_productos_demo
if errorlevel 1 (
    echo.
    echo Error al cargar los productos de prueba.
    pause
    exit /b 1
)
echo.
echo Base de datos actualizada y productos cargados correctamente.
pause
