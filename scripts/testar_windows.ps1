param([string]$Python = 'python', [string]$EvaluationOutput = 'artifacts/evaluations')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$localPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if ($Python -eq 'python' -and (Test-Path -LiteralPath $localPython)) { $Python = $localPython }
& $Python -m ruff check backend scripts
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/check_fixtures.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m pytest backend/tests -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/evaluate.py --mode all-offline --output $EvaluationOutput
exit $LASTEXITCODE
