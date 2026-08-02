param(
    [Parameter(Mandatory = $true)]
    [string]$Step,
    [string[]]$Set = @()
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$sweep = "scratch/run_series_i_sweep.py"
$log = ".workflow/2026-08-02-series-i-serial-calibration/results/series_i_${Step}_sweep.log"

if (-not (Test-Path $sweep)) { throw "Missing $sweep" }

$args = @("-u", $sweep, "--step", $Step, "--chunked")
foreach ($s in $Set) { $args += @("--set", $s) }

for ($i = 0; $i -lt 40; $i++) {
    Write-Output "=== Series I $Step chunk $i $(Get-Date -Format o) ==="
    & python @args 2>&1 | Tee-Object -Append -FilePath $log
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Output "Series I $Step complete"
        exit 0
    }
    if ($code -ne 2) {
        Write-Output "Series I $Step failed with exit $code"
        exit $code
    }
}
throw "Exceeded max chunks for Series I $Step"
