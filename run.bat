@echo off
setlocal
cd /d "%~dp0"
title CPI calculator 2023=100

echo.
echo  ========================================
echo   CPI calculator 2023=100
echo  ========================================
echo.

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  where python >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Python not found.
    echo Install Python from https://www.python.org/downloads/
    echo Check "Add python.exe to PATH" when installing.
    goto END
  )
  set "PY=python"
)

"%PY%" -c "import openpyxl" 1>nul 2>nul
if errorlevel 1 (
  echo Installing packages first time...
  "%PY%" -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 (
    echo ERROR: pip install failed
    goto END
  )
)

set "INPUT=C:\Users\batsukh\Desktop\cpi calculation 2023=100.xlsx"
if not exist "%INPUT%" (
  echo ERROR: Excel file not found:
  echo   %INPUT%
  echo Put "cpi calculation 2023=100.xlsx" on Desktop.
  goto END
)

echo Input: %INPUT%
echo.
echo Calculating... please wait 30-90 seconds
echo Do NOT close this window.
echo.

"%PY%" "%~dp0cli.py" calculate -i "%INPUT%" -o "%~dp0output" --json
if errorlevel 1 (
  echo.
  echo ERROR: calculation failed. Read messages above.
  goto END
)

echo.
echo ========================================
echo  SUCCESS
echo  Result folder:
echo  %~dp0output
echo ========================================
echo.
if exist "%~dp0output\cpi_result.xlsx" (
  echo Opening Excel result...
  start "" "%~dp0output\cpi_result.xlsx"
)
start "" explorer "%~dp0output"

:END
echo.
echo Press any key to close...
pause >nul
endlocal
