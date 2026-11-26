@echo off
:: Busca automáticamente la ruta de PHP dentro de Laragon
set "PHP_EXE=php"
for /d %%D in ("C:\laragon\bin\php\php-*") do set "PHP_EXE=%%D\php.exe"

:: 1. Enciende el servidor Laravel minimizado en la barra de tareas
start /min "Servidor GeoLab (No cerrar)" cmd /k "cd /d C:\laragon\www\Suelos-api && "%PHP_EXE%" artisan serve"

:: 2. Espera 2 segundos
timeout /t 2 /nobreak >nul

:: 3. Abre GeoLab directamente sin consolas extra y cierra esta ventana
cd /d "D:\DISCO_1\MECANICA DE SUELOS\GeoLab_BaseDeDatos\GeoLab_BaseDeDatos"
start "" ".venv\Scripts\pythonw.exe" "1_PROYECTO_SUELOS\Suelos_1.py"
exit