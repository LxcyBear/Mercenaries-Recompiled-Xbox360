[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python)){
    $cmd=Get-Command python -ErrorAction SilentlyContinue
    if($null-eq$cmd){throw "Python unavailable"}
    $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r64_a545f_status_source.py"
$source=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$report=Join-Path $root "build\phase6_native_graphics\phase6r64-a545f-status-source.txt"
foreach($file in @($script,$source)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "R64 source audit prerequisite missing: $file"
    }
}
Write-Host "[Phase6R64] ZERO BUILD - A545F DIRECTSOUND HRESULT PROVENANCE"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R64 Python preflight failed"}
& $python $script --source $source 2>&1 | Tee-Object -FilePath $report
if($LASTEXITCODE-ne0){throw "R64 source audit failed"}
Write-Host "[Phase6R64] REPORT: $report"
if($CopyToClipboard){
    Get-Content -LiteralPath $report -Raw | Set-Clipboard
    Write-Host "[Phase6R64] Copied full report to clipboard; paste it into ChatGPT."
}
