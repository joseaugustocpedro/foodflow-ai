param([string]$Python = 'python', [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$localPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if ($Python -eq 'python' -and (Test-Path -LiteralPath $localPython)) { $Python = $localPython }
& $Python scripts/run_local.py --port $Port
exit $LASTEXITCODE
