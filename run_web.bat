@echo off
setlocal
cd /d "%~dp0"
title CPI web

echo.
echo  Starting CPI web interface...
echo  Browser will open. Keep this window open.
echo  Close this window to stop the server.
echo.

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" -c "import streamlit" 1>nul 2>nul
if errorlevel 1 (
  echo Installing streamlit...
  "%PY%" -m pip install streamlit pandas openpyxl
)

echo Opening http://localhost:8501 ...
start "" http://localhost:8501
"%PY%" -m streamlit run "%~dp0app.py" --server.headless true
pause
endlocal
