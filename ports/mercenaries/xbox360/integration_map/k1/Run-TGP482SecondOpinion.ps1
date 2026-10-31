[CmdletBinding()]
param(
    [string]$Workspace=(Join-Path $env:LOCALAPPDATA "Merc360-TGP482-XBERecomp"),
    [string]$ReconZip=(Join-Path $env:LOCALAPPDATA "Merc360-Xboxrecomp-Recon\Merc360_xboxrecomp_static_recon.zip"),
    [string]$Xbe=(Join-Path $env:LOCALAPPDATA "Merc360-Xboxrecomp-Recon\private\default.xbe"),
    [switch]$BuildTools,
    [switch]$ScanXbe,
    [switch]$RunRecompiler,
    [switch]$ReportOnly,
    [switch]$UpdateSdk,
    [string]$Generator=""
)
# PowerShell 5.1 / ASCII only. Never write original game code into git.
# This is an independent XBE analysis sidecar, NOT an Xbox 360 build.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$shaExpected="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
$work=[IO.Path]::GetFullPath($Workspace)
$sdk=Join-Path $work "XboxXBERecomp"
$private=Join-Path $work "private"
$reports=Join-Path $work "reports"
$cmakeSrc=Join-Path $work "cmake-tools-only"
$cmakeBuild=Join-Path $work "cmake-build"
$report=Join-Path $reports "tgp482_second_opinion.txt"
$reportJson=Join-Path $reports "tgp482_second_opinion.json"
$generated=Join-Path $private "generated"
$config=Join-Path $private "mercenaries.toml"
$auditScript=Join-Path $PSScriptRoot "Audit-TGP482SecondOpinion.py"
$cmakeTemplate=Join-Path $PSScriptRoot "TGP482-ToolsOnly.CMakeLists.txt"
$git=(Get-Command git -ErrorAction Stop).Source
$python=(Get-Command python -ErrorAction Stop).Source
Write-Host "[TGP-XBR] =================================================="
Write-Host "[TGP-XBR] TGP482 XBOX XBE RECOMP SECOND-OPINION SIDECAR"
Write-Host "[TGP-XBR] =================================================="
New-Item -ItemType Directory -Path @($work,$private,$reports) -Force | Out-Null
foreach($required in @($auditScript,$cmakeTemplate,$ReconZip)){
    if(-not(Test-Path -LiteralPath $required -PathType Leaf)){
        throw "[TGP-XBR] Required metadata/helper missing: $required"
    }
}
if(-not(Test-Path -LiteralPath (Join-Path $sdk "xdk\5849\signatures.toml") -PathType Leaf)){
    if(Test-Path -LiteralPath $sdk){throw "[TGP-XBR] Existing SDK directory incomplete; will not delete it: $sdk"}
    Write-Host "[TGP-XBR] Cloning upstream tool privately, outside Mercenaries git"
    & $git clone --depth 1 https://github.com/TGP482/XboxXBERecomp.git $sdk
    if($LASTEXITCODE -ne 0){throw "[TGP-XBR] Git clone failed"}
}
# Use the raw configured remote, not git remote get-url: the latter can be
# rewritten by a user's global url.<base>.insteadOf configuration. GitHub also
# redirects the legacy XboxXBE-Recomp spelling to XboxXBERecomp.
$rawRemoteOutput=@(& $git -C $sdk config --get remote.origin.url)
if($LASTEXITCODE -ne 0 -or $rawRemoteOutput.Count -ne 1){
    throw "[TGP-XBR] Cannot read git's configured origin URL; existing checkout is left untouched"
}
$origin=([string]$rawRemoteOutput[0]).Trim()
Write-Host "[TGP-XBR] Configured upstream origin: $origin"
# Reject unknown remotes using exact allowed HTTPS/SSH origins. PowerShell's
# '-in' is case-insensitive and does not interpret regex / dollar anchors.
$allowedOrigins=@(
    'https://github.com/TGP482/XboxXBERecomp.git',
    'https://github.com/TGP482/XboxXBERecomp',
    'https://github.com/TGP482/XboxXBE-Recomp.git',
    'https://github.com/TGP482/XboxXBE-Recomp',
    'git@github.com:TGP482/XboxXBERecomp.git',
    'git@github.com:TGP482/XboxXBERecomp',
    'git@github.com:TGP482/XboxXBE-Recomp.git',
    'git@github.com:TGP482/XboxXBE-Recomp',
    'ssh://git@github.com/TGP482/XboxXBERecomp.git',
    'ssh://git@github.com/TGP482/XboxXBE-Recomp.git'
)
if($origin.TrimEnd('/') -notin $allowedOrigins){
    throw "[TGP-XBR] SDK origin unrecognized: $origin. Expected github.com/TGP482/XboxXBERecomp; checkout unchanged."
}
if($UpdateSdk){
    & $git -C $sdk pull --ff-only
    if($LASTEXITCODE -ne 0){throw "[TGP-XBR] SDK fast-forward update failed"}
}
$version=(& $git -C $sdk rev-parse --short HEAD | Select-Object -First 1)
Write-Host "[TGP-XBR] Verified SDK checkout: $version"
& $python -m py_compile $auditScript
if($LASTEXITCODE -ne 0){throw "[TGP-XBR] Python syntax failed"}
$compareArgs=@("--sdk",$sdk,"--recon-zip",$ReconZip,
    "--report",$report,"--json-out",$reportJson)
& $python -u $auditScript @compareArgs
if($LASTEXITCODE -ne 0){throw "[TGP-XBR] XDK5849 signature/metadata audit failed"}
if($ReportOnly){
    if($ScanXbe -or $RunRecompiler -or $BuildTools){
        throw "[TGP-XBR] -ReportOnly is exclusive; it never builds or scans"
    }
    $sourceXbe=[IO.Path]::GetFullPath($Xbe)
    if(-not(Test-Path -LiteralPath $sourceXbe -PathType Leaf)){
        throw "[TGP-XBR] Missing previously scanned retail XBE, pass -Xbe"
    }
    $sourceHash=(Get-FileHash -LiteralPath $sourceXbe -Algorithm SHA256).Hash.ToUpperInvariant()
    if($sourceHash -ne $shaExpected){
        throw "[TGP-XBR] Wrong retail XBE SHA; refusing cached scan attribution"
    }
    if(-not(Test-Path -LiteralPath $config -PathType Leaf)){
        throw "[TGP-XBR] No saved scanner configuration. Run -ScanXbe first"
    }
    $scanScript=Join-Path $PSScriptRoot "Summarize-TGP482Scan.py"
    if(-not(Test-Path -LiteralPath $scanScript -PathType Leaf)){
        throw "[TGP-XBR] Missing scan report packager; update Mercenaries repository"
    }
    $scanTxt=Join-Path $reports "tgp482_signature_scan.txt"
    $scanCsv=Join-Path $reports "tgp482_signature_symbols.csv"
    & $python -u $scanScript --config $config --old-zip $ReconZip --out-txt $scanTxt --out-csv $scanCsv
    if($LASTEXITCODE -ne 0){throw "[TGP-XBR] Cached scanner report failed"}
    Write-Host "[TGP-XBR] CACHE REUSE PASS: no compile, no retail rescan. Share: $scanTxt"
    exit 0
}
if($RunRecompiler){$ScanXbe=$true; $BuildTools=$true}
if($ScanXbe){$BuildTools=$true}
if(-not $BuildTools){
    Write-Host "[TGP-XBR] METADATA PASS. No compiler, original XBE scan or Xbox build."
    Write-Host "[TGP-XBR] Share report: $report"
    exit 0
}
# CMake may be installed as an optional Visual Studio C++ component and
# therefore absent from the user's normal Windows PowerShell PATH.
# Prefer installed tools. Never auto-install or modify their toolchains.
$cmake=$null
$cmakeCandidates=New-Object 'System.Collections.Generic.List[string]'
$pathCmake=Get-Command "cmake.exe" -ErrorAction SilentlyContinue
if($null -ne $pathCmake -and -not [string]::IsNullOrWhiteSpace($pathCmake.Source)){
    $cmakeCandidates.Add($pathCmake.Source)
}
$vswherePaths=New-Object 'System.Collections.Generic.List[string]'
foreach($base in @($env:ProgramFiles, [Environment]::GetEnvironmentVariable('ProgramFiles(x86)'))){
    if([string]::IsNullOrWhiteSpace($base)){continue}
    $vswherePaths.Add((Join-Path $base "Microsoft Visual Studio\Installer\vswhere.exe"))
}
foreach($vswhere in $vswherePaths){
    if(-not(Test-Path -LiteralPath $vswhere -PathType Leaf)){continue}
    $installations=@(& $vswhere -products "*" -property installationPath)
    if($LASTEXITCODE -ne 0){continue}
    foreach($root in $installations){
        $cmakeCandidates.Add((Join-Path ([string]$root) "Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"))
    }
}
# Fallback when vswhere is absent or VS is installed in an unusual layout.
foreach($base in @($env:ProgramFiles,[Environment]::GetEnvironmentVariable('ProgramFiles(x86)'))){
    if([string]::IsNullOrWhiteSpace($base)){continue}
    $cmakeCandidates.Add((Join-Path $base "CMake\bin\cmake.exe"))
    foreach($version in @("18","2026","2022","2019","2017")){
        foreach($edition in @("Community","Professional","Enterprise","BuildTools")){
            $cmakeCandidates.Add((Join-Path $base ("Microsoft Visual Studio\"+$version+"\"+$edition+"\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe")))
        }
    }
}
foreach($candidate in $cmakeCandidates){
    if(Test-Path -LiteralPath $candidate -PathType Leaf){
        $cmake=$candidate
        break
    }
}
if($null -eq $cmake){
    throw "[TGP-XBR] CMake is not installed or discoverable in PATH/Visual Studio. In Visual Studio Installer select 'C++ CMake tools for Windows', or install standalone CMake: winget install --exact --id Kitware.CMake. Reopen PowerShell and rerun -ScanXbe. No XBE scan or XDK build occurred."
}
Write-Host "[TGP-XBR] Discovered CMake: $cmake"
& $cmake --version | Select-Object -First 1
New-Item -ItemType Directory -Force -Path @($cmakeSrc,$cmakeBuild) | Out-Null
Copy-Item -LiteralPath $cmakeTemplate -Destination (Join-Path $cmakeSrc "CMakeLists.txt") -Force
$configArgs=@("-S",$cmakeSrc,"-B",$cmakeBuild,"-DSDK_DIR:PATH=$sdk")
if(-not [string]::IsNullOrWhiteSpace($Generator)){
    $configArgs+=@("-G",$Generator)
    if($Generator -like "Visual Studio*"){$configArgs+=@("-A","x64")}
}
Write-Host "[TGP-XBR] CMake: ONLY upstream xbe_symbols and xbe_recomp (no D3D12/SDL)"
& $cmake @configArgs
if($LASTEXITCODE -ne 0){throw "[TGP-XBR] CMake configuration failed; specify a supported -Generator"}
# A signature scan needs ONLY xbe_symbols. Do not block a useful real-XBE
# signature scan on an unrelated code-generator compatibility issue.
$buildTargets=@("xbe_symbols")
$needRecompiler=($RunRecompiler -or (-not $ScanXbe))
if($needRecompiler){$buildTargets+=@("xbe_recomp")}
Write-Host "[TGP-XBR] Build targets: $($buildTargets -join ', ')"
& $cmake --build $cmakeBuild --config Release --target @buildTargets --parallel 4
if($LASTEXITCODE -ne 0){throw "[TGP-XBR] Analysis-tools build failed; Xbox runtime untouched"}
$symbols=@(Get-ChildItem -LiteralPath $cmakeBuild -Filter "xbe_symbols.exe" -Recurse -File |
    Sort-Object FullName -Descending | Select-Object -First 1)
if($symbols.Count -ne 1){throw "[TGP-XBR] xbe_symbols executable missing after build"}
$recompiler=@()
if($needRecompiler){
    $recompiler=@(Get-ChildItem -LiteralPath $cmakeBuild -Filter "xbe_recomp.exe" -Recurse -File |
        Sort-Object FullName -Descending | Select-Object -First 1)
    if($recompiler.Count -ne 1){throw "[TGP-XBR] xbe_recomp executable missing after build"}
}
if($needRecompiler){
    Write-Host "[TGP-XBR] TOOLS PASS: both independent analysis CLIs compiled"
}else{
    Write-Host "[TGP-XBR] SYMBOL SCANNER PASS: xbe_symbols ready; xbe_recomp build intentionally skipped"
}
if(-not $ScanXbe){
    Write-Host "[TGP-XBR] To scan verified retail XBE signatures: add -ScanXbe"
    exit 0
}
$xbePath=[IO.Path]::GetFullPath($Xbe)
if(-not(Test-Path -LiteralPath $xbePath -PathType Leaf)){
    throw "[TGP-XBR] Original user-local XBE missing: $xbePath; pass -Xbe"
}
$hash=(Get-FileHash -LiteralPath $xbePath -Algorithm SHA256).Hash.ToUpperInvariant()
if($hash -ne $shaExpected){throw "[TGP-XBR] WRONG RETAIL XBE SHA $hash; refusing false cross-game analysis"}
Write-Host "[TGP-XBR] Original retail SHA256 PASS; XDK signature scanner starting"
& $symbols[0].FullName $xbePath (Join-Path $sdk "xdk") --library Mercenaries.dll --out $config
if($LASTEXITCODE -ne 0 -or -not(Test-Path -LiteralPath $config -PathType Leaf)){
    throw "[TGP-XBR] Signature scan failed; check actual XDK library build/signature compatibility"
}
Write-Host "[TGP-XBR] Signature config saved PRIVATE: $config"
# Share only the scanner's generic function names and addresses, never the
# private TOML config or original retail XBE.
$scanSummarizer=Join-Path $PSScriptRoot "Summarize-TGP482Scan.py"
if(-not(Test-Path -LiteralPath $scanSummarizer -PathType Leaf)){
    throw "[TGP-XBR] Missing scan reporter - pull the latest Mercenaries branch"
}
$scanReport=Join-Path $reports "tgp482_signature_scan.txt"
$scanCsv=Join-Path $reports "tgp482_signature_symbols.csv"
& $python -u $scanSummarizer --config $config --old-zip $ReconZip --out-txt $scanReport --out-csv $scanCsv
if($LASTEXITCODE -ne 0){throw "[TGP-XBR] Scanner symbol report failed; private TOML remains saved"}
Write-Host "[TGP-XBR] SHARE THIS NEW REPORT: $scanReport"
if(-not $RunRecompiler){
    Write-Host "[TGP-XBR] For independent function inventory: add -RunRecompiler"
    exit 0
}
New-Item -ItemType Directory -Force -Path $generated | Out-Null
Write-Host "[TGP-XBR] Independent function discovery + codegen, user-local only"
& $recompiler[0].FullName $config $xbePath $generated --xdk (Join-Path $sdk "xdk")
if($LASTEXITCODE -ne 0){throw "[TGP-XBR] Independent recomp failed; Xbox build unchanged"}
$mapping=Join-Path $generated "x86_func_mapping.cpp"
if(-not(Test-Path -LiteralPath $mapping -PathType Leaf)){
    throw "[TGP-XBR] Independent function mapping not created"
}
& $python -u $auditScript @compareArgs --mapping $mapping
if($LASTEXITCODE -ne 0){throw "[TGP-XBR] Function-inventory comparison failed"}
Write-Host "[TGP-XBR] DONE: share metadata report $report"
Write-Host "[TGP-XBR] XBE, guest-source C++, and config remain PRIVATE."
Write-Host "[TGP-XBR] No Xbox build or fabricated display."
