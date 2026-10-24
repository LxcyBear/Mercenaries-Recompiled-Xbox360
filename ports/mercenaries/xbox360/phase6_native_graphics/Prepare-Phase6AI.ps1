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

$baseDir = Join-Path $root "build\phase6_native_graphics\d3d_saturation_0028e700_xdk"
$out = Join-Path $root "build\phase6_native_graphics\d3d_internal_device_global_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6ai-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6ai_d3d_internal_device_global.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    prep6ah = Join-Path $p6 "Prepare-Phase6AH.ps1"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}

foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v -PathType Leaf)) {
        throw "Missing Phase 6AI input: $v"
    }
}

$baseManifest = Join-Path $baseDir "phase6ah-manifest.json"
$baseMain = Join-Path $baseDir "main_monolithic.cpp"
$baseEnv = Join-Path $baseDir "phase5_env.cpp"

if (-not (Test-Path -LiteralPath $baseManifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseMain -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseEnv -PathType Leaf)) {
    Write-Host "[Phase6AI] Cached Phase 6AH-D sources are missing."
    Write-Host "[Phase6AI] Regenerating Phase 6AH-D source cache without VS2017..."
    & $paths.prep6ah -SkipSolutionBuild
}

foreach ($f in @($baseManifest,$baseMain,$baseEnv)) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) {
        throw "Phase 6AI required Phase 6AH-D input missing: $f"
    }
}

$bm = Get-Content -LiteralPath $baseManifest -Raw | ConvertFrom-Json
if ($bm.phase -ne "6AH" -or
    $bm.build_tag -ne "P6AH-D3D-SYNC-0028E700-20261023-D") {
    throw "Phase 6AI Phase 6AH-D baseline identity mismatch"
}

$ah = $bm.phase6ah_d3d_saturation
if ($ah.root -ne "0x0028E700" -or
    -not [bool]$ah.native_createdevice_handoff_inherited_unchanged -or
    -not [bool]$ah.d3d_sync_checkpoint_support.required_for_root) {
    throw "Phase 6AI inherited Phase 6AH model drift"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AI] RETAIL INTERNAL D3D DEVICE GLOBAL REPAIR"
Write-Host "[Phase6AI] 6AH-D hardware     : PASS, then orange READ32 80000004"
Write-Host "[Phase6AI] Forensic root      : sub_0028E700"
Write-Host "[Phase6AI] Public device out  : 007AD604 -> 00299380 (already proven)"
Write-Host "[Phase6AI] Internal D3D global: 00299378 -> 00299380 (repair)"
Write-Host "[Phase6AI] Root field +1C20   : expected 0029AFA0"
Write-Host "[Phase6AI] KSEG first page    : remains fenced"
Write-Host "[Phase6AI] Hard stops         : NV2A/MMIO/VRAM, ABI, guest faults"
Write-Host ""

& $python -m py_compile $paths.emitter
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AI emitter Python syntax check failed"
}
Write-Host "[Phase6AI] Emitter syntax     : PASS"

$emitArgs = @(
    "--base-dir",$baseDir,
    "--base-emitter",$paths.base,
    "--out-dir",$out
)

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $paths.emitter @emitArgs 2>&1 | Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[Phase6AI] PREP STOPPED BEFORE BUILD."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 220 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AI emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6ai-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AI missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AI" -or
    $m.build_tag -ne "P6AI-D3D-INTERNAL-DEVICE-GLOBAL-20261023-D") {
    throw "Phase 6AI manifest identity mismatch"
}

$ai = $m.phase6ai_internal_d3d_device_global
if (-not [bool]$ai.phase6ah_hardware_pass -or
    $ai.forensic.root -ne "0x0028E700" -or
    $ai.forensic.internal_device_global -ne "0x00299378" -or
    $ai.forensic.guest_device_identity -ne "0x00299380" -or
    $ai.forensic.expected_field_1c20_address -ne "0x0029AFA0" -or
    -not [bool]$ai.forensic.kseg_first_page_remains_fenced -or
    $ai.repair.createdevice_internal_global -ne "0x00299378" -or
    $ai.repair.published_value -ne "0x00299380" -or
    -not [bool]$ai.repair.readback_required -or
    [bool]$ai.repair.relax_kseg_fence -or
    [bool]$ai.repair.nv2a_mmio_writes -or
    $ai.source_layout.shard_prefix -ne "phase6ai_") {
    throw "Phase 6AI manifest repair gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$monolithicText = Get-Content -LiteralPath $monolithic -Raw
$envText = Get-Content -LiteralPath $env -Raw

$required = @(
    "P6AI-D3D-INTERNAL-DEVICE-GLOBAL-20261023-D",
    "GUEST_WRITE32(0x00299378u, s_phase6afGuestDevice);",
    "s_phase6aiInternalDeviceReadback = GUEST_READ32(0x00299378u);",
    "phase6ai_d3d_root_checkpoint(esi);",
    "P6AI D3D ROOT INPUT: calls=%u this=%08X internal=%08X field1C20=%08X",
    "P6AI INTERNAL D3D DEVICE: publishes=%u value=%08X readback=%08X root_calls=%u this=%08X internal=%08X field1C20=%08X",
    "PHASE 6AI INTERNAL D3D DEVICE RESULT: %s",
    "s_phase6aiRootInternalGlobal == 0x00299380u",
    "P6AI PRIOR 6AH D3D SATURATION RESULT: %s",
    "phase6ai_env_build_cookie"
)

foreach ($marker in $required) {
    if (-not $monolithicText.Contains($marker)) {
        throw "Phase 6AI generated source gate missing: $marker"
    }
}

if ($monolithicText.Contains("phase6ah_env_build_cookie") -or
    $envText.Contains("phase6ah_env_build_cookie")) {
    throw "Phase 6AI stale Phase 6AH cookie remains"
}

$policyStart = $monolithicText.IndexOf('trace("Policy:')
if ($policyStart -lt 0) {
    throw "Phase 6AI startup policy trace missing"
}
$policyEnd = $monolithicText.IndexOf('");', $policyStart)
if ($policyEnd -lt 0) {
    throw "Phase 6AI startup policy trace terminator missing"
}
$policyLength = $policyEnd - ($policyStart + 7)
if ($policyLength -gt 240) {
    throw "Phase 6AI startup policy trace exceeds safe length"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AI translated shard output is empty"
}
$wrong = @($shards | Where-Object { -not $_.Name.StartsWith("phase6ai_") })
if ($wrong.Count -gt 0) {
    throw "Phase 6AI translated shard prefix gate failed: $($wrong[0].Name)"
}

$rootInstrumented = $false
foreach ($shard in $shards) {
    if ((Get-Content -LiteralPath $shard.FullName -Raw).Contains("phase6ai_d3d_root_checkpoint(esi);")) {
        $rootInstrumented = $true
        break
    }
}
if (-not $rootInstrumented) {
    throw "Phase 6AI D3D root checkpoint did not survive sharding"
}

Write-Host ""
Write-Host "[Phase6AI] READY"
Write-Host ("[Phase6AI] Generated shards       : {0}" -f $shards.Count)
Write-Host "[Phase6AI] CreateDevice public out : 007AD604 -> 00299380"
Write-Host "[Phase6AI] Internal D3D global     : 00299378 -> 00299380 + readback"
Write-Host "[Phase6AI] Root +1C20 expectation  : 0029AFA0"
Write-Host "[Phase6AI] KSEG fence              : unchanged"
Write-Host "[Phase6AI] Expected tag            : P6AI-D3D-INTERNAL-DEVICE-GLOBAL-20261023-D"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AI] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AI-D3D-INTERNAL-DEVICE-GLOBAL-20261023-D"
        ExpectedEnvCookie = "phase6ai_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6ai-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6ai-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AI-D.xex")
    }

    & $paths.build @buildArgs

    Write-Host ""
    Write-Host "[Phase6AI] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AI] Hardware tag to verify: P6AI-D3D-INTERNAL-DEVICE-GLOBAL-20261023-D"
    Write-Host ("[Phase6AI] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AI-D.xex"))
}
else {
    Write-Host "[Phase6AI] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
