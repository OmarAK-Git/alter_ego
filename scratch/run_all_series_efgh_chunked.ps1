$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot\..

$lockFile = Join-Path (Get-Location) "scratch\.sweep.lock"
if (Test-Path $lockFile) {
    $lockAge = (Get-Date) - (Get-Item $lockFile).LastWriteTime
    if ($lockAge.TotalHours -lt 12) {
        Write-Error "Sweep lock exists ($lockFile, age $($lockAge.TotalMinutes.ToString('F0')) min)."
        exit 2
    }
    Remove-Item $lockFile -Force
}
New-Item -ItemType File -Path $lockFile -Force | Out-Null

$statusFile = "scratch/sweep_sequential_status.txt"
function Write-Status($msg) {
    $line = "$(Get-Date -Format o) $msg"
    Add-Content -Path $statusFile -Value $line
    Write-Output $line
}

try {
    foreach ($series in @("e", "f", "g", "h")) {
        $log = "scratch/series_${series}_chunked_run.log"
        Write-Status "SWEEP_$($series.ToUpper()) START"
        for ($i = 0; $i -lt 40; $i++) {
            Write-Output "=== Series $($series.ToUpper()) chunk $i $(Get-Date -Format o) ===" | Tee-Object -Append -FilePath $log
            & python "scratch/run_series_${series}_sweep.py" --chunked 2>&1 | Tee-Object -Append -FilePath $log
            $code = $LASTEXITCODE
            "CHUNK_EXIT:$code" | Tee-Object -Append -FilePath $log
            if ($code -eq 0) {
                Write-Status "SWEEP_$($series.ToUpper()) exit=0 metrics=$(Test-Path "scratch/series_${series}_metrics.json")"
                break
            }
            if ($code -ne 2) {
                Write-Status "SWEEP_$($series.ToUpper()) exit=$code metrics=False"
                exit $code
            }
        }
        if (-not (Test-Path "scratch/series_${series}_metrics.json")) {
            Write-Status "SWEEP_$($series.ToUpper()) FAILED no metrics"
            exit 1
        }
    }
    Write-Status "ALL_DONE"
    & python scratch/write_governance_efgh.py 2>&1 | Tee-Object -Append -FilePath "scratch/governance_write.log"
    exit $LASTEXITCODE
} finally {
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}
