param([string]$Series = "e")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$script = "scratch/run_series_${Series}_sweep.py"
if (-not (Test-Path $script)) { throw "Missing $script" }

for ($i = 0; $i -lt 40; $i++) {
    Write-Output "=== Chunk $i $(Get-Date -Format o) ==="
    python $script --chunked
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Output "Series $Series complete"
        exit 0
    }
    if ($code -ne 2) {
        Write-Output "Series $Series failed with exit $code"
        exit $code
    }
}
throw "Exceeded max chunks for series $Series"
