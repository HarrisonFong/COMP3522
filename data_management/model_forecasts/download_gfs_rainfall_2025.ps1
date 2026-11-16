param([ValidateRange(1,24)][int]$Workers = 16)

# One resumable run: import, independently verify, then refresh documentation.
# Root .env supplies connections; never echo its contents.
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonPath = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
Set-Location -LiteralPath $repositoryRoot
& $pythonPath -u (Join-Path $PSScriptRoot 'stream_gfs_rainfall.py') --workers $Workers
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonPath -u (Join-Path $PSScriptRoot 'verify_gfs_rainfall_2025.py')
$verificationExitCode = $LASTEXITCODE
& $pythonPath (Join-Path $PSScriptRoot 'schema_document.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit $verificationExitCode
