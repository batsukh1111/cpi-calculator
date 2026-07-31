# PowerShell launcher - right click -> Run with PowerShell
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "========================================"
Write-Host " CPI calculator 2023=100"
Write-Host "========================================"
Write-Host ""

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $py = "python"
}

$input = "C:\Users\batsukh\Desktop\cpi calculation 2023=100.xlsx"
if (-not (Test-Path $input)) {
    Write-Host "ERROR: Excel not found: $input" -ForegroundColor Red
    Read-Host "Press Enter"
    exit 1
}

Write-Host "Calculating... wait 30-90 sec"
& $py (Join-Path $PSScriptRoot "cli.py") calculate -i $input -o (Join-Path $PSScriptRoot "output") --json
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED" -ForegroundColor Red
    Read-Host "Press Enter"
    exit $LASTEXITCODE
}

$result = Join-Path $PSScriptRoot "output\cpi_result.xlsx"
Write-Host "SUCCESS: $result" -ForegroundColor Green
if (Test-Path $result) { Start-Process $result }
Start-Process explorer.exe (Join-Path $PSScriptRoot "output")
Read-Host "Press Enter to close"
