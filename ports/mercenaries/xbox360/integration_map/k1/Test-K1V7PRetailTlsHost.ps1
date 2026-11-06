[CmdletBinding()]
param()
# V7P portable source-only host test. Absolutely no VS2017 XDK/Xbox invocation.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
$source=Join-Path $PSScriptRoot 'Test-K1V7PRetailTlsCore.cpp'
$header=Join-Path $PSScriptRoot 'K1V7PRetailTlsCore.h'
$out=Join-Path $repo 'build\phase6_integration_map\k1_v7p_retail_tls_host'
foreach($file in @($source,$header)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){throw "[K1-V7P] Missing source: $file"}
}
New-Item -ItemType Directory -Path $out -Force | Out-Null
$exe=Join-Path $out 'k1_v7p_tls_test.exe'
$clang=Get-Command clang++.exe -ErrorAction SilentlyContinue
$gcc=Get-Command g++.exe -ErrorAction SilentlyContinue
$cl=Get-Command cl.exe -ErrorAction SilentlyContinue
if($clang){
    & $clang.Source '-std=c++11' '-Wall' '-Wextra' '-Werror' $source '-o' $exe
}elseif($gcc){
    & $gcc.Source '-std=c++11' '-Wall' '-Wextra' '-Werror' $source '-o' $exe
}elseif($cl){
    & $cl.Source '/nologo' '/EHsc' '/W4' $source "/Fe:$exe" "/Fo:$(Join-Path $out 'k1_v7p_tls_test.obj')"
}else{
    throw "[K1-V7P] No host C++ compiler in PATH. Use VS Developer Command Prompt (cl) or clang++/g++; no XDK attempted."
}
if($LASTEXITCODE -ne 0){throw "[K1-V7P] HOST compilation failed"}
& $exe
if($LASTEXITCODE -ne 0){throw "[K1-V7P] HOST fixture failed"}
Write-Host '[K1-V7P] RETAIL TLS CORE HOST PASS; no translated main patch or Xbox build.'
