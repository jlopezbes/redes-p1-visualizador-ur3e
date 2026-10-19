@echo off
rem Practica 1 (visualizador UR3e): arranca los scripts con el Python portatil de la carpeta entorno\.
rem No hay que instalar nada. Las IP de los robots estan en datos\robots.json (opcion 4 del menu).
rem Tambien se puede lanzar directo, sin menu:  iniciar.bat primaria | tiempo_real | ensenar
setlocal
cd /d "%~dp0"
title Practica 1 - visualizador UR3e

set "PY=entorno\python.exe"
if not exist "%PY%" (
    set "PY=python"
    echo [AVISO] No existe entorno\python.exe: se usa el Python instalado en este PC ^(necesita 3.7, pybullet y UR3e_rg2^).
    echo         El entorno portatil se crea con: herramientas\crear_entorno.ps1
    echo.
)

if /i "%~1"=="primaria"    goto primaria
if /i "%~1"=="tiempo_real" goto tiempo_real
if /i "%~1"=="ensenar"     goto ensenar

:menu
echo ============================================================
echo   PRACTICA 1 - visualizador de robots UR3e
echo ============================================================
echo   1  Primaria     visualiza 1 o varios robots ^(puerto 30001^)
echo   2  Tiempo real  visualiza 1 o varios robots ^(puerto 30003^)
echo   3  Ensenar      guarda y reproduce puntos, con web de control
echo                   ENVIA movej: solo con el robot libre y zona despejada
echo   4  Cambiar las IP de los robots ^(datos\robots.json^)
echo   5  Salir
echo.
choice /c 12345 /n /m "Elige una opcion (1-5): "
if errorlevel 5 goto fin
if errorlevel 4 goto ip
if errorlevel 3 goto ensenar
if errorlevel 2 goto tiempo_real
goto primaria

:primaria
"%PY%" -u -B src\primaria.py
goto terminado

:tiempo_real
"%PY%" -u -B src\tiempo_real.py
goto terminado

:ensenar
echo.
choice /c SN /n /m "ensenar ENVIA movej al robot. Robot libre y zona despejada? (S/N): "
if errorlevel 2 goto menu
"%PY%" -u -B src\ensenar.py
goto terminado

:ip
start /wait notepad datos\robots.json
goto menu

:terminado
set "CODIGO=%errorlevel%"
echo.
echo El programa ha terminado ^(codigo %CODIGO%; 0 = normal, 1 = error explicado arriba^).
pause
if "%~1"=="" goto menu

:fin
endlocal
