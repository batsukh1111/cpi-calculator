@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title CPI publication tables

echo.
echo  ========================================
echo   CPI нийтлэлийн хүснэгт (table 1-11)
echo  ========================================
echo.

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

set "INPUT=C:\Users\batsukh\Desktop\cpi calculation 2023=100.xlsx"
set "TEMPLATE=C:\Users\batsukh\Desktop\National_202607_2023.xlsx"

if not exist "%INPUT%" (
  echo ERROR: %INPUT%
  pause
  exit /b 1
)
if not exist "%TEMPLATE%" (
  echo ERROR template: %TEMPLATE%
  pause
  exit /b 1
)

echo Үнийн файл: %INPUT%
echo Загвар:     %TEMPLATE%
echo.
echo Хугацаа оруулна уу ^(ж.нь 2026-06^)
echo Хоосон үлдээвэл сүүлийн сарыг авна.
set /p PERIOD=Хугацаа: 

echo.
echo Тооцоолж байна... 30-90 сек хүлээнэ үү.
echo.

if "%PERIOD%"=="" (
  "%PY%" "%~dp0cli.py" publish -i "%INPUT%" -t "%TEMPLATE%" -o "%~dp0output"
) else (
  "%PY%" "%~dp0cli.py" publish -i "%INPUT%" -t "%TEMPLATE%" -p "%PERIOD%" -o "%~dp0output"
)

if errorlevel 1 (
  echo ERROR
  pause
  exit /b 1
)

echo.
echo DONE. Opening output folder...
explorer "%~dp0output"
pause
endlocal
