param(
    [switch]$Reload,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "E:\Anaconda\python.exe"
}

Write-Host "Python: $python"
Write-Host "Start:  http://127.0.0.1:$Port"
Write-Host "Health: http://127.0.0.1:$Port/api/health"

$args = @(
    "-m", "uvicorn", "backend.main:app",
    "--host", "0.0.0.0",
    "--port", "$Port"
)
if ($Reload) { $args += "--reload" }

& $python @args
