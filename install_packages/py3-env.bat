@ECHO OFF 

REM Поиск установленной версии QGIS в каталоге "C:\Program Files\QGIS *.*"
for /f "delims=" %%i in ('dir "C:\Program Files\QGIS *.*" /b /ad') do set QGIS_DIR=%%i
set OSGEO4W_ROOT=C:\Program Files\%QGIS_DIR%

set PATH=%OSGEO4W_ROOT%\bin;%PATH%
set PATH=%PATH%;%OSGEO4W_ROOT%\apps\qgis\bin

@echo off
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"
call "%OSGEO4W_ROOT%\bin\qt5_env.bat"
call "%OSGEO4W_ROOT%\bin\py3_env.bat"
@echo off
path %OSGEO4W_ROOT%\apps\qgis\bin;%PATH%

cd /d %~dp0