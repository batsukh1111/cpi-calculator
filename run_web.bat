@echo off
setlocal
cd /d "%~dp0"
title CPI WEB - http://127.0.0.1:5050

echo.
echo  ========================================
echo   CPI WEB starting...
echo   Browser: http://127.0.0.1:5050
echo   Keep this window OPEN.
echo   Close this window = stop website.
echo  ========================================
echo.

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  where python >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Python not found.
    echo Install Python and check "Add to PATH".
    pause
    exit /b 1
  )
  set "PY=python"
)

echo Python: %PY%

"%PY%" -c "import flask" 1>nul 2>nul
if errorlevel 1 (
  echo Installing flask...
  "%PY%" -m pip install flask openpyxl pandas
  if errorlevel 1 (
    echo ERROR: pip install failed
    pause
    exit /b 1
  )
)

if not exist "C:\Users\batsukh\Desktop\cpi calculation 2023=100.xlsx" (
  echo WARNING: Excel not on Desktop:
  echo   C:\Users\batsukh\Desktop\cpi calculation 2023=100.xlsx
  echo Website will open but calculate may fail.
  echo.
)

REM Free port 5050 if old server still running
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5050 ^| findstr LISTENING') do (
  echo Stopping old process on port 5050: %%a
  taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo Starting server...
start "CPI-WEB-SERVER" /MIN "%PY%" "%~dp0server.py"

echo Waiting for server (up to 30 sec)...
set /a n=0
:waitloop
set /a n+=1
if %n% gtr 30 goto waitfail
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri http://127.0.0.1:5050/api/status -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if errorlevel 1 goto waitloop

echo.
echo  OK - server is running.
echo  Opening browser...
echo.
start "" http://127.0.0.1:5050

echo.
echo  ========================================
echo   Website is running.
echo   If page is empty: click "Excel дахин"
echo   First load of data takes 30-90 sec.
echo  ========================================
echo.
echo  Press any key to STOP the website...
pause >nul

REM Stop server
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5050 ^| findstr LISTENING') do (
  taskkill /F /PID %%a >nul 2>&1
)
echo Stopped.
timeout /t 2 >nul
exit /b 0

:waitfail
echo.
echo ERROR: Server did not start in 30 seconds.
echo Check output\web_err.log or run:
echo   %PY% server.py
echo.
pause
exit /b 1
