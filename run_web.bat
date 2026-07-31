@echo off
setlocal
cd /d "%~dp0"
title CPI Web Site

echo.
echo  ========================================
echo   CPI веб сайт эхлүүлж байна...
echo   Хөтөч: http://127.0.0.1:5050
echo   Хаахдаа энэ цонхыг хаана.
echo  ========================================
echo.

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" -c "import flask" 1>nul 2>nul
if errorlevel 1 (
  echo Flask суулгаж байна...
  "%PY%" -m pip install flask openpyxl pandas
)

echo.
echo Эхний удаа Excel тооцоолол 30-90 сек болно.
echo.

start "" http://127.0.0.1:5050
"%PY%" "%~dp0server.py"

pause
endlocal
