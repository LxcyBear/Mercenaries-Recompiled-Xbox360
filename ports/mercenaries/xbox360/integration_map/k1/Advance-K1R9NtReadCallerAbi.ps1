[CmdletBinding()]
param(
    [string]$XboxLog = "",
    [string]$RetailXbe = ""
)
# K1-R9 SOURCE-ONLY: analyze existing R8 candidate and original x86 caller.
# No XDK, hardware run, ABI modification, stack repair or speculative bypass.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$r8=Join-Path $root "build\phase6_integration_map\k1_ntread44_frame_evidence_r8"
$main=Join-Path $r8 "main.cpp"
$report=Join-Path $r8 "k1-r9-ntread-caller-abi-audit.json"
$script=Join-Path $PSScriptRoot "Audit-K1R9NtReadCallerAbi.py"
if(-not (Test-Path -LiteralPath $main -PathType Leaf)){
    throw "[K1-R9] R8 main.cpp missing; run R8 source stage first"
}
$python=(Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "[K1-R9] Python syntax failed"}
$arguments=@("-u",$script,"--r8-main",$main,"--output",$report)
if($XboxLog){
    if(-not(Test-Path -LiteralPath $XboxLog -PathType Leaf)){
        throw "[K1-R9] XboxLog file does not exist: $XboxLog"
    }
    $arguments+=@("--xbox-log",(Resolve-Path -LiteralPath $XboxLog).Path)
}
if($RetailXbe){
    if(-not(Test-Path -LiteralPath $RetailXbe -PathType Leaf)){
        throw "[K1-R9] RetailXbe file does not exist: $RetailXbe"
    }
    $arguments+=@("--retail-xbe",(Resolve-Path -LiteralPath $RetailXbe).Path)
}
& $python @arguments
if($LASTEXITCODE -ne 0){throw "[K1-R9] Source/retail/hardware proof failed closed"}
Write-Host "[K1-R9] No XDK build or Xbox run requested; inspect report above." -ForegroundColor Green
