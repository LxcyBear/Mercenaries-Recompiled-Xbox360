[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){
    $cmd=Get-Command python -ErrorAction SilentlyContinue
    if($null-eq$cmd){throw "Python unavailable"}
    $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r68_dsound_pool_constructor.py"
$source=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$out=Join-Path $root "build\phase6_native_graphics\phase6r68-pool-constructor-audit.txt"
foreach($file in @($script,$source)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "R68 required source missing: $file"
    }
}
Write-Host "[Phase6R68] ZERO-BUILD DSOUND PAGE POOL CONSTRUCTOR AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R68 Python syntax validation failed"}
& $python -u $script --source $source 2>&1 | Tee-Object -FilePath $out
if($LASTEXITCODE-ne0){throw "R68 audit failed; report: $out"}
Write-Host "[Phase6R68] REPORT: $out"
if($CopyToClipboard){
    Get-Content -LiteralPath $out -Raw | Set-Clipboard
    Write-Host "[Phase6R68] Full report copied to clipboard."
}
