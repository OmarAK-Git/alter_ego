$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot\..

$lockFile = Join-Path (Get-Location) "scratch\.sweep.lock"
if (Test-Path $lockFile) {
    $lockAge = (Get-Date) - (Get-Item $lockFile).LastWriteTime
    if ($lockAge.TotalHours -lt 12) {
        Write-Error "Sweep lock exists ($lockFile, age $($lockAge.TotalMinutes.ToString('F0')) min). Another sweep may be running."
        exit 2
    }
    Remove-Item $lockFile -Force
}
New-Item -ItemType File -Path $lockFile -Force | Out-Null

try {
    foreach ($series in @("e", "f", "g", "h")) {
        $log = "scratch/series_${series}_sweep.log"
        Write-Output "=== Series $($series.ToUpper()) started $(Get-Date -Format o) ===" | Tee-Object -FilePath $log
        python "scratch/run_series_${series}_sweep.py" 2>&1 | Tee-Object -Append -FilePath $log
        $code = $LASTEXITCODE
        "EXIT:$code" | Tee-Object -Append -FilePath $log
        Write-Output "=== Series $($series.ToUpper()) exit $code $(Get-Date -Format o) ===" | Tee-Object -Append -FilePath $log
        if ($code -ne 0) { exit $code }
    }
    Write-Output "ALL_SWEEPS_DONE $(Get-Date -Format o)"
} finally {
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}
