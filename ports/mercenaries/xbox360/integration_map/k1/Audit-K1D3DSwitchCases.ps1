[CmdletBinding()]
param(
    [string]$XbePath = "",
    [string]$PythonCommand = "python"
)
# Windows PowerShell 5.1: exact original retail XBE case-path disassembly.
# No XDK, no Xbox, no files inside 64 TrueTUs or generated main changed.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$inspector = Join-Path $PSScriptRoot "Audit-K1D3DSwitchCases.py"
$originalC = Join-Path $root "build\phase3n_final_abi_scale\runtime\gen\recomp_0013.c"
$outRoot = Join-Path $root "build\phase6_integration_map\k1_d3d_predictive_batch"
$outJson = Join-Path $outRoot "k1-d3d-six-switch-cases-original-xbe.json"
if([string]::IsNullOrWhiteSpace($XbePath)){
    $XbePath = Join-Path $env:USERPROFILE "OneDrive\Desktop\My Xbox\default.xbe"
}
foreach($path in @($inspector,$originalC,$XbePath)) {
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
        throw "[K1D3D-CASES] Required source not found: $path"
    }
}
$python = (Get-Command $PythonCommand -ErrorAction Stop).Source
& $python -m py_compile $inspector
if($LASTEXITCODE -ne 0){
    throw "[K1D3D-CASES] Python syntax check failed"
}
& $python -u $inspector --self-test
if($LASTEXITCODE -ne 0){
    throw "[K1D3D-CASES] Source safety fixtures failed"
}
& $python -c "import capstone"
if($LASTEXITCODE -ne 0){
    throw "[K1D3D-CASES] Missing x86 decoder. Install it into this Python with: $python -m pip install capstone"
}
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null
Write-Host "[K1D3D-CASES] Original retail XBE SHA-256 checked by Python; never copied to repo"
Write-Host "[K1D3D-CASES] Decoding six original D3D jump-table destinations, preserving raw machine-code provenance"
& $python -u $inspector --xbe $XbePath --original-generated-c $originalC --out $outJson
if($LASTEXITCODE -ne 0){
    throw "[K1D3D-CASES] Verified original jump case decode failed; XDK remains unchanged"
}
$doc = Get-Content -LiteralPath $outJson -Raw -Encoding UTF8 | ConvertFrom-Json
if($doc.status -ne "K1_D3D_ORIGINAL_XBE_JUMP_CASES_SOURCE_ONLY" -or
   $doc.original_retail_xbe_sha256 -ne "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7" -or
   [int]$doc.original_source_proof.exact_sha_original_pointer_slots -ne 6 -or
   $doc.safe_to_modify_guest_dispatch -ne $false -or
   $doc.safe_to_build_new_xex -ne $false -or
   @($doc.case_paths).Count -ne 6){
    throw "[K1D3D-CASES] Missing original six-way decoder proof or unsafe report contract"
}
Write-Host "[K1D3D-CASES] FINISHED: NO XDK BUILD. NO XEX CHANGES. ORIGINAL 64 TUs UNTOUCHED"
Write-Host "[K1D3D-CASES] Report: $outJson"
