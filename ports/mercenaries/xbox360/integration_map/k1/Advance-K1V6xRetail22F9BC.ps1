[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
    $script = Join-Path $here 'Audit-K1V6xRetail22F9BC.py'
    & python.exe -m py_compile $script
    if ($LASTEXITCODE -ne 0) { throw 'V6x Python syntax preflight failed' }
    Write-Host '[K1-V6x] PYTHON SYNTAX PREFLIGHT PASS'
    & python.exe $script
    if ($LASTEXITCODE -ne 0) { throw 'V6x exact retail function disassembly proof failed' }
    $report = Join-Path $repo 'build\phase6_integration_map\k1_retail_22f9bc_recovery\retail_22f9bc_audit.json'
    if (!(Test-Path -LiteralPath $report)) { throw 'V6x evidence report not emitted' }
    $meta = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($meta.stage -ne 'V6X_NEXT_FRONTIER_RETAIL_X86_AUDIT_ONLY' -or
        $meta.function_entry -ne '0x0022F9BC' -or
        $meta.safe_to_build_xex -ne $false -or
        $meta.retail_xbe_sha256 -ne 'AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7') {
        throw 'V6x report evidence guard failed'
    }
    Write-Host '[K1-V6x] ORIGINAL MACHINE CODE AUDIT: PASS'
    Write-Host '[K1-V6x] No guest patch, no fake function, no XDK run.'
    Write-Host "[K1-V6x] Report: $report"
} finally {
    Pop-Location
}
