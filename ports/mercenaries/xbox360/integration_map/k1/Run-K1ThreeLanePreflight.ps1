[CmdletBinding()]
param(
    [string]$HardwareLog = "",
    [string]$Output = ""
)
# Read-only, Windows PowerShell 5.1. No XDK, no Xbox, no generated C++ edits.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$shards = Join-Path $root "build\phase6_integration_map\k1_ntquerydirectory207_native\translated_shards"
$proof = Join-Path $root "build\phase6_integration_map\k1_nv2a_prmdio_write8\focused-0028ED48.txt"
$script = Join-Path $PSScriptRoot "Audit-K1ThreeLaneFrontiers.py"
if(-not $Output){
    $Output = Join-Path $root "build\phase6_integration_map\k1_three_lane_report\three_lane.json"
}
foreach($p in @($proof, $script)){
    if(-not (Test-Path -LiteralPath $p -PathType Leaf)){
        throw "[K1-3LANE] Missing required original-source evidence: $p"
    }
}
if(-not (Test-Path -LiteralPath $shards -PathType Container)){
    throw "[K1-3LANE] Missing generated 64 TrueTUs: $shards"
}
if($HardwareLog -and -not(Test-Path -LiteralPath $HardwareLog -PathType Leaf)){
    throw "[K1-3LANE] Hardware log not found: $HardwareLog"
}
$python = (Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "[K1-3LANE] Python source syntax failed"}
& $python -u $script --self-test
if($LASTEXITCODE -ne 0){throw "[K1-3LANE] Python fixtures failed"}
$argv = @("--shards", $shards, "--proof", $proof, "--out", $Output)
if($HardwareLog){$argv += @("--hardware-log", $HardwareLog)}
& $python -u $script @argv
if($LASTEXITCODE -ne 0){throw "[K1-3LANE] Real TrueTU/source audit failed"}
$doc = Get-Content -LiteralPath $Output -Raw -Encoding UTF8 | ConvertFrom-Json
if($doc.status -ne "SOURCE_ONLY_READ_ONLY_NO_XDK" -or
   [int]$doc.counts.files -ne 64 -or
   [int]$doc.translated_files_mutated -ne 0 -or
   $doc.mmio_fences_changed -ne $false -or
   $doc.synthetic_pixels -ne $false){
    throw "[K1-3LANE] Report provenance/safety mismatch"
}
Write-Host "[K1-3LANE] PASS: PFIFO, hot 001E, and Swap/PersistDisplay independently audited"
Write-Host "[K1-3LANE] Report: $Output"
Write-Host "[K1-3LANE] No XDK, no Xbox, no TrueTU changes"
