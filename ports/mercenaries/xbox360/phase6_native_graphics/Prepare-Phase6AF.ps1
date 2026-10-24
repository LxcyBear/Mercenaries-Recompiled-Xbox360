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
$p6 = $PSScriptRoot
$p4 = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseDir = Join-Path $root "build\phase6_native_graphics\av_family_display_handoff_xdk"
$out = Join-Path $root "build\phase6_native_graphics\native_d3d_createdevice_handoff_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6af-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6af_native_d3d_createdevice_handoff.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}

foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6AF input: $v"
    }
}

$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    (Join-Path $baseDir "phase6ae-manifest.json")
)

$missing = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    $prep6ae = Join-Path $p6 "Prepare-Phase6AE.ps1"
    if (-not (Test-Path -LiteralPath $prep6ae)) {
        throw "Phase 6AF baseline missing and Phase 6AE prep was not found: $prep6ae"
    }

    Write-Host "[Phase6AF] Cached Phase 6AE output is missing."
    Write-Host "[Phase6AF] Regenerating Phase 6AE-B without rebuilding the external solution..."
    & $prep6ae -SkipSolutionBuild
}

foreach ($f in @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "phase6ae-manifest.json")
)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AF required input missing after regeneration: $f"
    }
}

$baseManifest = Get-Content (Join-Path $baseDir "phase6ae-manifest.json") -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6AE" -or
    $baseManifest.build_tag -ne "P6AE-AV-FAMILY-DISPLAY-HANDOFF-20261023-B") {
    throw "Phase 6AF Phase 6AE baseline identity mismatch"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AF] NATIVE D3D CREATEDEVICE HANDOFF"
Write-Host "[Phase6AF] Hardware proof      : 6AE-B crossed AV ordinal 2, then terminal renderer HRESULT 8007000E"
Write-Host "[Phase6AF] Retail routine      : sub_0028CAA0"
Write-Host "[Phase6AF] Retail frame        : 6 args + return slot = 28 bytes"
Write-Host "[Phase6AF] Physical device     : inherited live native Xenos device"
Write-Host "[Phase6AF] Guest device        : 00299380 (upstream renderer recovery success fixture)"
Write-Host "[Phase6AF] Presentation gate   : exact retail 640x480 contract; multisample may vary"
Write-Host "[Phase6AF] Continue policy     : resume translated D3D after handoff"
Write-Host "[Phase6AF] Hard stops          : NV2A/MMIO/VRAM, platform, ABI and guest faults"

$args = @(
    "--base-dir",$baseDir,
    "--base-emitter",$paths.base,
    "--out-dir",$out
)

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $paths.emitter @args 2>&1 | Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[Phase6AF] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6AF] Emitter log tail:"
    Get-Content -LiteralPath $log -Tail 200
    throw "Phase 6AF emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6af-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AF missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AF" -or
    $m.build_tag -ne "P6AF-NATIVE-D3D-CREATEDEVICE-HANDOFF-20261023-B") {
    throw "Phase 6AF manifest identity mismatch"
}

$af = $m.phase6af_native_d3d_createdevice_handoff
if (-not [bool]$af.phase6ae_hardware_pass -or
    $af.phase6ae_hardware.renderer_boundary.kind -ne "RENDERER_FATAL" -or
    $af.phase6ae_hardware.renderer_boundary.hresult -ne "0x8007000E" -or
    [int]$af.phase6ae_hardware.renderer_boundary.fault -ne 0 -or
    $af.upstream_recovery_contract.retail_create_device -ne "sub_0028CAA0" -or
    [int]$af.upstream_recovery_contract.frame_bytes -ne 28 -or
    $af.upstream_recovery_contract.success_guest_device -ne "0x00299380" -or
    -not [bool]$af.native_handoff.strict_contract_validation -or
    $af.source_layout.shard_prefix -ne "phase6af_") {
    throw "Phase 6AF manifest handoff gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$monolithicText = Get-Content -LiteralPath $monolithic -Raw
$envText = Get-Content -LiteralPath $env -Raw

$policyMatch = [regex]::Match($monolithicText, 'trace\("Policy:([^"]*)"\);')
if (-not $policyMatch.Success) {
    throw "Phase 6AF startup policy trace missing"
}
if ($policyMatch.Groups[1].Value.Length -gt 240) {
    throw "Phase 6AF startup policy trace exceeds safe length"
}

foreach ($marker in @(
    "P6AF-NATIVE-D3D-CREATEDEVICE-HANDOFF-20261023-B",
    "static void sub_0028CAA0(void)",
    "PASS: Phase 6AF native D3D CreateDevice handoff",
    "static int phase6af_native_xenos_ready(void)",
    "return s_phase6bXenosReady && s_phase6bXenosDevice != NULL;",
    "s_phase6afCreateDeviceBridgeCount != 0u &&",
    "P6AF D3D DEVICE:",
    "P6AF AV FAMILY:",
    "PHASE 6AF NATIVE D3D DEVICE HANDOFF RESULT",
    "P6AF XENOS: PASS Direct3D_CreateDevice",
    "PASS: Phase 6AF ordinal 2 AvSendTVEncoderOption",
    "phase6af_env_build_cookie"
)) {
    if (-not $monolithicText.Contains($marker)) {
        throw "Phase 6AF generated source gate missing: $marker"
    }
}

if ($monolithicText -match "phase6ae_env_build_cookie" -or
    $envText -match "phase6ae_env_build_cookie") {
    throw "Phase 6AF stale Phase 6AE cookie remains"
}

$createDeviceDefs = [regex]::Matches($monolithicText, 'static void sub_0028CAA0\(void\)\s*\{')
if ($createDeviceDefs.Count -ne 1) {
    throw "Phase 6AF expected exactly one sub_0028CAA0 definition, found $($createDeviceDefs.Count)"
}

$xenosReadyDefs = [regex]::Matches($monolithicText, 'static int phase6af_native_xenos_ready\(void\)\s*\{')
if ($xenosReadyDefs.Count -ne 1) {
    throw "Phase 6AF expected exactly one native-Xenos readiness helper definition, found $($xenosReadyDefs.Count)"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AF translated shard output is empty"
}
$wrongShards = @($shards | Where-Object { -not $_.Name.StartsWith("phase6af_") })
if ($wrongShards.Count -gt 0) {
    throw "Phase 6AF translated shard prefix gate failed: $($wrongShards[0].Name)"
}

Write-Host ""
Write-Host "[Phase6AF] READY"
Write-Host ("[Phase6AF] Generated shards    : {0}" -f $shards.Count)
Write-Host "[Phase6AF] CreateDevice bridge : exact sub_0028CAA0 -> native-Xenos logical handoff"
Write-Host "[Phase6AF] Guest device        : 00299380"
Write-Host "[Phase6AF] Renderer recovery   : expected to avoid terminal 8007000E if handoff is accepted"
Write-Host "[Phase6AF] Expected tag        : P6AF-NATIVE-D3D-CREATEDEVICE-HANDOFF-20261023-B"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AF] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AF-NATIVE-D3D-CREATEDEVICE-HANDOFF-20261023-B"
        ExpectedEnvCookie = "phase6af_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6af-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6af-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AF-B.xex")
    }

    & $paths.build @buildArgs

    Write-Host ""
    Write-Host "[Phase6AF] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AF] Hardware tag to verify: P6AF-NATIVE-D3D-CREATEDEVICE-HANDOFF-20261023-B"
    Write-Host ("[Phase6AF] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AF-B.xex"))
}
else {
    Write-Host "[Phase6AF] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
