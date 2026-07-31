@echo off
setlocal
cd /d "%~dp0"
title Deploy CPI to GitHub Pages

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "INPUT=C:\Users\batsukh\Desktop\cpi calculation 2023=100.xlsx"

echo.
echo  1) Export data from Excel...
"%PY%" "%~dp0cli.py" web-export -i "%INPUT%"
if errorlevel 1 (
  echo EXPORT FAILED
  pause
  exit /b 1
)

echo.
echo  2) Git commit + push...
git add docs
git status
git commit -m "Update online CPI dashboard data"
if errorlevel 1 (
  echo Nothing to commit or commit failed.
)

git push origin master
if errorlevel 1 (
  echo PUSH FAILED - check git login
  pause
  exit /b 1
)

echo.
echo  3) Enable GitHub Pages if needed...
gh api repos/batsukh1111/cpi-calculator/pages -X POST -f build_type=workflow 2>nul
gh api repos/batsukh1111/cpi-calculator/pages -X PUT -f build_type=legacy -f source[branch]=master -f source[path]=/docs 2>nul

echo.
echo  DONE.
echo  Online: https://batsukh1111.github.io/cpi-calculator/
echo  Wait 1-2 min after first enable.
echo.
start "" "https://batsukh1111.github.io/cpi-calculator/"
pause
