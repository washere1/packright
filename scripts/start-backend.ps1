$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Missing .venv. Run scripts/setup.ps1 first." }
Set-Location -LiteralPath $ProjectRoot
& $PythonExe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

