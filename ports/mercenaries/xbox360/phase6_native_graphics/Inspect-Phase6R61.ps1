[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python)){
    $cmd=Get-Command python -ErrorAction SilentlyContinue
    if($null-eq$cmd){throw "Python is unavailable"}
    $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r61_f0c6_status_provenance.py"
$source=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$out=Join-Path $root "build\phase6_native_graphics\phase6r61-f0c6-status-audit.txt"
foreach($f in @($script,$source)){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){
        throw "R61 missing audit input: $f"
    }
}
Write-Host "[Phase6R61] ZERO-BUILD F0C6 STATUS PROVENANCE"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R61 Python syntax preflight failed"}
& $python $script --source $source 2>&1 | Tee-Object -FilePath $out
if($LASTEXITCODE-ne0){throw "R61 source-only audit failed"}
Write-Host "[Phase6R61] REPORT: $out"
if($CopyToClipboard){
    Get-Content -LiteralPath $out -Raw | Set-Clipboard
    Write-Host "[Phase6R61] Clipboard contains the complete report; paste it into chat."
}
