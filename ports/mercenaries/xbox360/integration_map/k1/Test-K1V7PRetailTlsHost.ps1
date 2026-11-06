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
    # Use the already installed desktop Visual Studio C++ toolchain through
    # its environment bootstrap. No change to the invoking PowerShell session.
    $vswhereCandidates=@(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft Visual Studio\Installer\vswhere.exe')
    )
    $vswhere=@($vswhereCandidates | Where-Object {
        $_ -and (Test-Path -LiteralPath $_ -PathType Leaf)
    } | Select-Object -First 1)
    $vsPath=''
    if($vswhere.Count -gt 0){
        $vsPath=((& $vswhere[0] -products '*' -latest -property installationPath) | Select-Object -First 1)
        if($LASTEXITCODE -ne 0){$vsPath=''}
    }
    $devCmd=''
    if(-not [string]::IsNullOrWhiteSpace($vsPath)){
        $candidate=Join-Path $vsPath 'Common7\Tools\VsDevCmd.bat'
        if(Test-Path -LiteralPath $candidate -PathType Leaf){$devCmd=$candidate}
    }
    if([string]::IsNullOrWhiteSpace($devCmd)){
        $fallbacks=@(
            (Join-Path $env:ProgramFiles 'Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat'),
            (Join-Path $env:ProgramFiles 'Microsoft Visual Studio\2026\Community\Common7\Tools\VsDevCmd.bat'),
            (Join-Path $env:ProgramFiles 'Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat')
        )
        $hits=@($fallbacks | Where-Object {Test-Path -LiteralPath $_ -PathType Leaf})
        if($hits.Count -gt 0){$devCmd=$hits[0]}
    }
    if([string]::IsNullOrWhiteSpace($devCmd)){
        throw "[K1-V7P] No host C++ compiler found, and no VS C++ Developer Environment detected. Install Desktop development with C++ in Visual Studio; no XDK attempted."
    }
    Write-Host "[K1-V7P] Found Visual Studio host environment: $devCmd"
    $cmdFile=Join-Path $out 'k1_v7p_host_compile.cmd'
    $obj=Join-Path $out 'k1_v7p_tls_test.obj'
    $lines=@(
        '@echo off',
        ('call "' + $devCmd + '" -no_logo -arch=x64 -host_arch=x64 >nul'),
        'if errorlevel 1 exit /b 1',
        ('cl.exe /nologo /EHsc /W4 "'+$source+'" /Fe:"'+$exe+'" /Fo:"'+$obj+'"'),
        'exit /b %errorlevel%'
    )
    Set-Content -LiteralPath $cmdFile -Value $lines -Encoding ASCII
    & $env:ComSpec /d /c ('"' + $cmdFile + '"')
}
if($LASTEXITCODE -ne 0){throw "[K1-V7P] HOST compilation failed"}
& $exe
if($LASTEXITCODE -ne 0){throw "[K1-V7P] HOST fixture failed"}
Write-Host '[K1-V7P] RETAIL TLS CORE HOST PASS; no translated main patch or Xbox build.'
