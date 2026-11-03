[CmdletBinding()]
param(
    [switch]$Build,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
# Windows PowerShell 5.1; default is source-only. No game bytes or
# existing 64 translated .cpp files are modified.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$parentRoot = Join-Path $root "build\phase6_integration_map\k1_three_lane"
$parentMain = Join-Path $parentRoot "main.cpp"
$parentManifest = Join-Path $parentRoot "k1-three-lane-manifest.json"
$outRoot = Join-Path $root "build\phase6_integration_map\k1_text_direct_batch"
$nextMain = Join-Path $outRoot "main.cpp"
$nextManifest = Join-Path $outRoot "k1-text-direct-manifest.json"
$shards = Join-Path $root "build\phase6_integration_map\k1_ntquerydirectory207_native\translated_shards"
$original = Join-Path $root "build\phase3n_final_abi_scale"
$generated = Join-Path $original "runtime\gen"
$functions = Join-Path $original "analysis\disasm\functions.json"
$cache = Join-Path $original "analysis\disasm\.disasm_cache.json"
$base = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$p5bb = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bb_frontier22dda4.py"
$p5bc = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bc_broad_sweep.py"
$stage = Join-Path $PSScriptRoot "Stage-K1TextDirectBatch.py"
$parentRunner = Join-Path $PSScriptRoot "Advance-K1ThreeLaneGraphics.ps1"
$envFile = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$builder = Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$xdk = Join-Path $outRoot "xdk"
$xex = Join-Path $xdk "Merc-K1Text-Direct0017A0A0.xex"

foreach ($path in @($stage,$base,$p5bb,$p5bc,$parentRunner,$builder,$envFile,$functions,$cache)) {
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
        throw "[K1-TEXT] Missing real source/prior stage: $path"
    }
}
if(-not(Test-Path -LiteralPath $generated -PathType Container)){
    throw "[K1-TEXT] Missing original xboxrecomp C corpus: $generated"
}
if(-not(Test-Path -LiteralPath $shards -PathType Container)){
    throw "[K1-TEXT] Missing original 64 TrueTUs: $shards"
}

# Re-run inherited DAC+quiet+three-lane gates, but keep their verbose
# repetition out of this console. Preserve EVERY raw preflight line on disk.
# Child PowerShell exit code remains the sole pass/fail authority.
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null
$parentLog = Join-Path $outRoot "inherited-source-preflight.log"
$parentOutput = @(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $parentRunner 2>&1)
$parentExit = $LASTEXITCODE
$parentOutput | Out-File -LiteralPath $parentLog -Encoding UTF8
if($parentExit -ne 0) {
    Write-Host "[K1-TEXT] Inherited source preflight failed; last 25 lines:"
    $parentOutput | Select-Object -Last 25 | ForEach-Object { Write-Host $_ }
    throw "[K1-TEXT] Three-lane parent preflight failed; XDK blocked. Full log: $parentLog"
}
Write-Host "[K1-TEXT] INHERITED CHECKS: SUCCESS (DAC + quiet + PFIFO + hotpath + presentation)"
Write-Host "[K1-TEXT] Inherited full diagnostics preserved: $parentLog"
foreach ($path in @($parentMain,$parentManifest)) {
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
        throw "[K1-TEXT] Missing staged three-lane parent: $path"
    }
}

$parent = Get-Content -LiteralPath $parentManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$parentHash = (Get-FileHash -LiteralPath $parentMain -Algorithm SHA256).Hash.ToLowerInvariant()
if($parent.marker -ne "P6K1-THREELANE-20261103" -or
   $parent.new_main_sha256 -ne $parentHash -or
   $parent.status -ne "K1_THREE_LANE_SOURCE_STAGED_NO_XDK" -or
   [int]$parent.translated_tus_changed -ne 0 -or
   $parent.unknown_mmio_still_fenced -ne $true -or
   $parent.synthetic_pixels -ne $false){
    throw "[K1-TEXT] Parent source/hash or guest safety contract drift"
}

$python = (Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){ throw "[K1-TEXT] Python syntax failed; XDK blocked" }
$moduleArgs = @("--base-module",$base,"--p5bb-module",$p5bb,"--p5bc-module",$p5bc)
& $python -u $stage --self-test @moduleArgs
if($LASTEXITCODE -ne 0){ throw "[K1-TEXT] Source-pack regression failed; XDK blocked" }
$stageArgs = @("--parent",$parentMain,"--shards",$shards,"--functions",$functions,"--generated-root",$generated,"--out",$nextMain,"--manifest",$nextManifest)
& $python -u $stage @moduleArgs @stageArgs
if($LASTEXITCODE -ne 0){ throw "[K1-TEXT] Exact original source pack failed; XDK blocked" }

$doc = Get-Content -LiteralPath $nextManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$nextHash = (Get-FileHash -LiteralPath $nextMain -Algorithm SHA256).Hash.ToLowerInvariant()
$nextText = Get-Content -LiteralPath $nextMain -Raw -Encoding UTF8
if($doc.status -ne "K1_TEXT_DIRECT_SOURCE_ONLY_NO_XDK" -or
   $doc.original_root -ne "0x0017A0A0" -or
   $doc.parent_sha256 -ne $parentHash -or
   $doc.new_main_sha256 -ne $nextHash -or
   [int]$doc.compiled_tus_unchanged -ne 64 -or
   $doc.synthetic_guest_results -ne $false -or
   $doc.unknown_mmio_fences_changed -ne $false -or
   $doc.xdk_verified -ne $false -or
   @($doc.promoted_vas) -notcontains "0x0017A0A0" -or
   $nextText.Contains("case 0x0017A0A0u: return sub_0017A0A0;") -ne $true -or
   $nextText.Contains("P6DQ ROCKET HARD STOP") -ne $true -or
   $nextText.Contains("K1NV2A DAC PALETTE COMMIT:") -ne $true -or
   $nextText.Contains("K1PERF WINDOW:") -ne $true -or
   $nextText.Contains("K1PRESENT FRONTIER ROUTE:") -ne $true){
    throw "[K1-TEXT] Source-stage output or safety-gate mismatch; XDK blocked"
}
$actualShards = @(Get-ChildItem -LiteralPath $shards -Filter "translated_???.cpp" -File)
if($actualShards.Count -ne 64){
    throw "[K1-TEXT] 64 true-TU source set changed before build; XDK blocked"
}
Write-Host "[K1-TEXT] PREFLIGHT PASS: authentic original .text 0017A0A0 + support-clean direct closure"
Write-Host ("[K1-TEXT] Promoted={0} remaining_direct={1}; original 64 TrueTUs reused" -f [int]$doc.promoted_count,@($doc.remaining_direct_frontiers).Count)
Write-Host "[K1-TEXT] PFIFO, DAC, K1PERF, presentation logger and all hard fences inherited"
if(-not $Build){
    Write-Host "[K1-TEXT] SOURCE ONLY (no XDK). Add -Build for one incremental XEX."
    exit 0
}

New-Item -ItemType Directory -Force -Path $xdk | Out-Null
$buildArgs = @{
    GeneratedMain=$nextMain
    GeneratedEnv=$envFile
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $xdk "xdk-clean.log")
    BuildLog=(Join-Path $xdk "xdk-build.log")
    PublishedXex=$xex
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[K1-TEXT] ONE INCREMENTAL XDK BUILD: original 64 compiled TrueTUs reused, new source in main only"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){ throw "[K1-TEXT] XDK build failed; see $($buildArgs.BuildLog)" }
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1-TEXT] XDK build did not publish expected XEX"
}
Write-Host "[K1-TEXT] XDK BUILD PASS: $xex"
Write-Host "[K1-TEXT] Hardware not verified; next log must prove authentic 0017A0A0 execution"
