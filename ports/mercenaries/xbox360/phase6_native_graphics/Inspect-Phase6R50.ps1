[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python)){
    $cmd=Get-Command python -ErrorAction SilentlyContinue
    if($null-eq$cmd){throw "Python was not found"}
    $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r50_kernel173_frame.py"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$log=Join-Path $root "build\phase6_native_graphics\phase6r50-kernel173-audit.txt"
foreach($file in @($script,$source)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "Missing R50 input: $file"
    }
}
Write-Host "[Phase6R50] ZERO-BUILD KERNEL 173 PROVENANCE AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R50 syntax check failed"}
& $python $script "--source" $source 2>&1 | Tee-Object -FilePath $log
if($LASTEXITCODE-ne0){throw "R50 audit failed"}
Write-Host "[Phase6R50] REPORT: $log"
if($CopyToClipboard){
    Get-Content -LiteralPath $log -Raw | Set-Clipboard
    Write-Host "[Phase6R50] Full audit report copied to clipboard"
}
