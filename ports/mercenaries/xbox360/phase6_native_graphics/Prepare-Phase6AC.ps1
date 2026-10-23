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
$stage3 = Join-Path $root "build\phase3n_final_abi_scale"
$baseDir = Join-Path $root "build\phase6_native_graphics\hal_boot_video_mode_data_xdk"
$out = Join-Path $root "build\phase6_native_graphics\mm166_wrapper_reuse_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6ac-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6ac_mm166_wrapper_reuse.py"
    aaEmitter = Join-Path $p6 "emit_phase6aa_post_graphics_pool_frontier_0020fae0.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6AC input: $v"
    }
}

$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    (Join-Path $baseDir "phase6ab-manifest.json")
)

$missing = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    $prep6ab = Join-Path $p6 "Prepare-Phase6AB.ps1"
    if (-not (Test-Path -LiteralPath $prep6ab)) {
        throw "Phase 6AC baseline missing and Phase 6AB prep was not found: $prep6ab"
    }

    Write-Host "[Phase6AC] Cached Phase 6AB output is missing."
    Write-Host "[Phase6AC] Regenerating Phase 6AB without rebuilding the external solution..."
    & $prep6ab -SkipSolutionBuild
}

foreach ($f in @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "phase6ab-manifest.json"),
    (Join-Path $stage3 "runtime\gen"),
    (Join-Path $stage3 "analysis\disasm\functions.json")
)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AC required input missing after regeneration: $f"
    }
}

$baseManifest = Get-Content (Join-Path $baseDir "phase6ab-manifest.json") -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6AB" -or
    $baseManifest.build_tag -ne "P6AB-HAL-BOOT-VIDEO-MODE-DATA-20261023-A") {
    throw "Phase 6AC Phase 6AB baseline identity mismatch"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AC] MM166 WRAPPER REUSE"
Write-Host "[Phase6AC] Hardware: KERNEL_FRAME target=800000A6 ordinal=166"
Write-Host "[Phase6AC] Hardware frame: esp=008BF7C0 saved_esp=008BF7DC delta=28"
Write-Host "[Phase6AC] Hardware registers: eax=FFFFFFFF ecx=00000060 edx=00000000 esi=00299380"
Write-Host "[Phase6AC] Last translated direct: 0022AEE9 (the already-proven physical-allocation wrapper)"
Write-Host "[Phase6AC] Offline gate: sub_0022AEE9 must still prove saved ESI + five Mm166 args + dummy return"
Write-Host "[Phase6AC] Runtime gate: +28 accepted only while that exact wrapper ICALL is active and c+24 spill == live ESI"
Write-Host "[Phase6AC] Canonical +24 Mm166 calls remain unchanged"
Write-Host "[Phase6AC] Retail graphics-pool special case remains exact and unchanged"
Write-Host "[Phase6AC] Purple remains reserved for genuine NV2A MMIO/VRAM"

$args = @(
    "--base-dir",$baseDir,
    "--base-emitter",$paths.base,
    "--phase6aa-emitter",$paths.aaEmitter,
    "--generated-root",(Join-Path $stage3 "runtime\gen"),
    "--functions",(Join-Path $stage3 "analysis\disasm\functions.json"),
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
    Write-Host "[Phase6AC] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6AC] Emitter log tail:"
    $tail = @(Get-Content -LiteralPath $log -Tail 160)
    $tail | ForEach-Object { Write-Host $_ }

    $reason = @(
        $tail | Where-Object {
            ($_ -match "\[Phase6AC\]") -and
            ($_ -notmatch "CategoryInfo|FullyQualifiedErrorId")
        }
    )
    if (@($reason).Count -gt 0) {
        $primary = [string]@($reason)[@($reason).Count - 1]
    }
    else {
        $primary = "see $log"
    }
    throw ("Phase 6AC emission/preflight failed (exit {0}); PRIMARY: {1}" -f $rc, $primary)
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6ac-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AC missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AC" -or
    $m.build_tag -ne "P6AC-MM166-WRAPPER-REUSE-20261023-A") {
    throw "Phase 6AC manifest identity mismatch"
}

$ac = $m.phase6ac_mm166_wrapper_reuse
if (-not [bool]$ac.phase6ab_hardware_pass -or
    [int]$ac.phase6ab_hardware.boundary.ordinal -ne 166 -or
    [int]$ac.phase6ab_hardware.boundary.frame_bytes -ne 28 -or
    [int]$ac.generated_wrapper_proof.wrapper_frame_bytes -ne 28 -or
    $ac.decoded_boundary_request.size -ne "0x00000060" -or
    -not [bool]$ac.graphics_pool_special_case_inherited_unchanged -or
    -not [bool]$ac.hal_boot_video_mode_data_inherited_unchanged) {
    throw "Phase 6AC manifest wrapper-reuse gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($marker in @(
    "P6AC-MM166-WRAPPER-REUSE-20261023-A",
    "static int s_phase6acMm166WrapperActive;",
    "s_phase6acMm166WrapperActive = 1;",
    "s_phase6acMm166WrapperActive = 0;",
    "if(!s_phase6acMm166WrapperActive || extra!=g_esi)",
    "PASS: Phase 6AC Mm166 wrapper provenance",
    "resumeEsp=c+24u",
    "PASS: Phase 6AC retail graphics pool claim",
    "case 356u: return 0x0087E098u; /* HalBootSMCVideoMode ULONG */",
    "PASS: Phase 6AC HalBootSMCVideoMode initialized ordinal=356 va=0087E098 value=00000000",
    "P6AC MM166WRAP SUMMARY:",
    "PHASE 6AC MM166 WRAPPER REUSE RESULT",
    "phase6ac_env_build_cookie"
)) {
    if (-not $mainText.Contains($marker)) {
        throw "Phase 6AC generated main gate missing: $marker"
    }
}

if ($mainText.Contains("size!=0x01680000u || extra!=g_esi")) {
    throw "Phase 6AC stale one-size-only +28 gate remains"
}
if ($envText -notmatch "phase6ac_env_build_cookie") {
    throw "Phase 6AC env cookie gate missing"
}
if ($mainText -match "phase6ab_env_build_cookie" -or
    $envText -match "phase6ab_env_build_cookie") {
    throw "Phase 6AC stale Phase 6AB cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AC translated shard output is empty"
}

Write-Host ""
Write-Host "[Phase6AC] READY"
Write-Host ("[Phase6AC] Generated shards              : {0}" -f $shards.Count)
Write-Host "[Phase6AC] MM166 canonical frame         : +24 unchanged"
Write-Host "[Phase6AC] Proven wrapper frame          : +28 (= +24 Mm166 + saved ESI)"
Write-Host "[Phase6AC] New request                   : size 00000060 / low 0 / high FFFFFFFF"
Write-Host "[Phase6AC] +28 repair scope              : exact active sub_0022AEE9 wrapper only"
Write-Host "[Phase6AC] Graphics pool                 : inherited 02880000-03EFFFFF"
Write-Host "[Phase6AC] Expected tag                  : P6AC-MM166-WRAPPER-REUSE-20261023-A"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AC] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AC-MM166-WRAPPER-REUSE-20261023-A"
        ExpectedEnvCookie = "phase6ac_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6ac-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6ac-vs2017-build.log")
    }

    & $paths.build @buildArgs
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "Phase 6AC Visual Studio 2017/Xbox 360 build failed (exit $LASTEXITCODE)"
    }

    Write-Host ""
    Write-Host "[Phase6AC] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AC] Hardware tag to verify: P6AC-MM166-WRAPPER-REUSE-20261023-A"
}
else {
    Write-Host "[Phase6AC] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
