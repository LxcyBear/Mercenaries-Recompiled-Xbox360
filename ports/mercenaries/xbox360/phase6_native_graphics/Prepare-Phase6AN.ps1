[CmdletBinding()]
param(
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$Configuration = "Release",
    [string]$Platform = "Xbox 360",
    [switch]$SkipSolutionBuild
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseEmitter = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$emitter = Join-Path $PSScriptRoot "emit_phase6an_d3d_state_stack_probe.py"
$prep6aj = Join-Path $PSScriptRoot "Prepare-Phase6AJ.ps1"
$builder = Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$baseDir = Join-Path $root "build\phase6_native_graphics\d3d_orange_source_probe_xdk"
$out = Join-Path $root "build\phase6_native_graphics\d3d_state_stack_probe_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6an-emitter.log"

foreach ($path in @($python,$baseEmitter,$emitter,$prep6aj,$builder)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6AN input: $path"
    }
}

$baseManifest = Join-Path $baseDir "phase6aj-manifest.json"
$baseMain = Join-Path $baseDir "main_monolithic.cpp"
$baseEnv = Join-Path $baseDir "phase5_env.cpp"

if (-not (Test-Path -LiteralPath $baseManifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseMain -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseEnv -PathType Leaf)) {
    Write-Host "[Phase6AN] Cached Phase 6AJ-A source output is missing."
    Write-Host "[Phase6AN] Regenerating 6AJ-A sources only; VS2017 remains skipped."
    & $prep6aj -SkipSolutionBuild
}

foreach ($path in @($baseManifest,$baseMain,$baseEnv)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AN could not obtain cached Phase 6AJ-A input: $path"
    }
}

$m = Get-Content -LiteralPath $baseManifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AJ" -or
    $m.build_tag -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A") {
    throw "Phase 6AN cached Phase 6AJ-A baseline identity mismatch"
}

Write-Host "[Phase6AN] D3D DEVICE STATE-STACK PROBE"
Write-Host "[Phase6AN] 6AL hardware       : exact fault func=0028BC60 line=1957"
Write-Host "[Phase6AN] 6AM exact source   : ebp = GUEST_READ32(eax + 4)"
Write-Host "[Phase6AN] Fault eax/address   : 80000000 / 80000004"
Write-Host "[Phase6AN] Probe fields        : +1A04/+1A08/+1A0C/+1A10/+1A14/+1A18/+1A1C"
Write-Host "[Phase6AN] KSEG/MMIO/VRAM      : unchanged / hard fenced"
Write-Host ""

& $python -m py_compile $emitter
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AN emitter Python syntax check failed"
}
Write-Host "[Phase6AN] Emitter syntax      : PASS"

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

$argsList = @(
    "--base-dir",$baseDir,
    "--base-emitter",$baseEmitter,
    "--out-dir",$out
)

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $emitter @argsList 2>&1 | Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[Phase6AN] PREP STOPPED BEFORE BUILD."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 260 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AN emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$mono = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6an-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($path in @($main,$mono,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Phase 6AN missing output: $path"
    }
}

$r = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($r.phase -ne "6AN" -or
    $r.build_tag -ne "P6AN-D3D-STATE-STACK-PROBE-20261023-A") {
    throw "Phase 6AN manifest identity mismatch"
}

$an = $r.phase6an_d3d_state_stack_probe
if (-not [bool]$an.probe_only -or
    [bool]$an.guest_semantics_changed -or
    $an.phase6al_hardware.function -ne "0x0028BC60" -or
    $an.phase6al_hardware.source -ne "ebp = GUEST_READ32(eax + 4)") {
    throw "Phase 6AN manifest probe gate mismatch"
}

$monoText = Get-Content -LiteralPath $mono -Raw
$envText = Get-Content -LiteralPath $env -Raw
foreach ($marker in @(
    "P6AN-D3D-STATE-STACK-PROBE-20261023-A",
    "P6AN D3D STACK ENTRY:",
    "P6AN D3D STACK SENTINEL:",
    "P6AN D3D STACK SUMMARY:",
    "phase6an_env_build_cookie"
)) {
    if (-not $monoText.Contains($marker)) {
        throw "Phase 6AN generated source gate missing: $marker"
    }
}
if ($monoText.Contains("phase6aj_env_build_cookie") -or
    $envText.Contains("phase6aj_env_build_cookie")) {
    throw "Phase 6AN stale Phase 6AJ cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AN translated shard output is empty"
}
$wrong = @($shards | Where-Object { -not $_.Name.StartsWith("phase6an_") })
if ($wrong.Count -gt 0) {
    throw "Phase 6AN translated shard prefix gate failed: $($wrong[0].Name)"
}

Write-Host ""
Write-Host "[Phase6AN] READY"
Write-Host ("[Phase6AN] Generated shards      : {0}" -f $shards.Count)
Write-Host "[Phase6AN] Guest semantics       : UNCHANGED"
Write-Host "[Phase6AN] Expected tag          : P6AN-D3D-STATE-STACK-PROBE-20261023-A"
Write-Host "[Phase6AN] Hardware money line 1 : P6AN D3D STACK ENTRY: ..."
Write-Host "[Phase6AN] Hardware money line 2 : P6AN D3D STACK SENTINEL: ..."

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AN] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AN-D3D-STATE-STACK-PROBE-20261023-A"
        ExpectedEnvCookie = "phase6an_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6an-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6an-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AN-A.xex")
    }

    & $builder @buildArgs

    Write-Host ""
    Write-Host "[Phase6AN] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AN] Hardware tag to verify: P6AN-D3D-STATE-STACK-PROBE-20261023-A"
    Write-Host ("[Phase6AN] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AN-A.xex"))
}
else {
    Write-Host "[Phase6AN] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
