[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
    $script = Join-Path $here 'Plan-K1V7RecompXbeBatch.py'
    & python.exe -m py_compile $script
    if ($LASTEXITCODE -ne 0) { throw '[K1-V7] Python syntax preflight failed' }
    Write-Host '[K1-V7] PYTHON PREFLIGHT PASS'
    & python.exe $script
    if ($LASTEXITCODE -ne 0) { throw '[K1-V7] Retail XBE/recomp batch gate failed' }
    $path = Join-Path $repo 'build\phase6_integration_map\k1_batch_recomp_recovery_v7\v7_batch_gap_report.json'
    if (!(Test-Path -LiteralPath $path)) { throw '[K1-V7] Missing batch report' }
    $m = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if ($m.stage -ne 'V7_ORIGINAL_XBOXRECOMP_AND_RETAIL_XBE_BATCH_GAP_ANALYSIS_ONLY' -or
        $m.hardware_frontier -ne '0x0022F5A7' -or
        $m.retail_sha256 -ne 'AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7' -or
        $m.real_64_true_tus_preserved -ne $true -or
        $m.safe_to_build_xex -ne $false) {
        throw '[K1-V7] Batch provenance guard FAILED'
    }
    Write-Host '[K1-V7] BATCH AUDIT PASS (NO XDK)'
    Write-Host ("[K1-V7] Full report: " + $path)
} finally {
    Pop-Location
}
