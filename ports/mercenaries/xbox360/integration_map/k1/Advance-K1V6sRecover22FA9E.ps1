[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
    $script = Join-Path $here 'Audit-K1V6sMissingRetail22FA9E.py'
    & python.exe -m py_compile $script
    if ($LASTEXITCODE -ne 0) { throw 'V6s Python syntax preflight failed' }
    Write-Host '[K1-V6s] PYTHON SYNTAX PREFLIGHT PASS'
    & python.exe $script
    if ($LASTEXITCODE -ne 0) { throw 'V6s exact retail function disassembly proof failed' }
    $report = Join-Path $repo 'build\phase6_integration_map\k1_retail_22fa9e_recovery\retail_22fa9e_audit.json'
    if (!(Test-Path -LiteralPath $report)) { throw 'V6s evidence report not emitted' }
    $meta = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($meta.stage -ne 'V6S_MISSING_ORIGINAL_TRANSLATION_RETAIL_X86_AUDIT_ONLY' -or
        $meta.function_entry -ne '0x0022FA9E' -or
        $meta.original_generated_c_exists -ne $false -or
        $meta.safe_to_build_xex -ne $false -or
        $meta.retail_xbe_sha256 -ne 'AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7') {
        throw 'V6s report evidence guard failed'
    }
    Write-Host '[K1-V6s] ORIGINAL MACHINE CODE AUDIT: PASS'
    Write-Host '[K1-V6s] No guest patch, no fake function, no XDK run.'
    Write-Host "[K1-V6s] Report: $report"
} finally {
    Pop-Location
}
