@echo off
setlocal
cd /d "%~dp0"
title CPI online export

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "INPUT=C:\Users\batsukh\Desktop\cpi calculation 2023=100.xlsx"

echo.
echo  Excel -^> GitHub Pages data
echo  Input: %INPUT%
echo.

"%PY%" "%~dp0cli.py" web-export -i "%INPUT%"
if errorlevel 1 (
  echo ERROR
  pause
  exit /b 1
)

echo.
echo Next: git add docs ^&^& git commit ^&^& git push
echo Or run: deploy_online.bat
echo.
pause
