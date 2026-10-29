[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python = Join-Path $root ".venv\Scripts\python.exe"
if(-not (Test-Path -LiteralPath $python -PathType Leaf)){
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue
    if($null -eq $pyCmd){throw "Python is unavailable"}
    $python = $pyCmd.Source
}
$script = Join-Path $PSScriptRoot "inspect_phase6r65_a545f_two_paths.py"
$source = Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$report = Join-Path $root "build\phase6_native_graphics\phase6r65-a545f-two-paths.txt"
foreach($file in @($script,$source)){
    if(-not (Test-Path -LiteralPath $file -PathType Leaf)){
        throw "R65 source audit input missing: $file"
    }
}
Write-Host "[Phase6R65] ZERO-BUILD A545F / A2E38 / A4238 STATUS AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "R65 Python syntax preflight failed"}
& $python -u $script --source $source 2>&1 | Tee-Object -FilePath $report
if($LASTEXITCODE -ne 0){throw "R65 source audit failed; see $report"}
Write-Host "[Phase6R65] REPORT: $report"
if($CopyToClipboard){
    Get-Content -LiteralPath $report -Raw | Set-Clipboard
    Write-Host "[Phase6R65] Copied report to clipboard."
}
