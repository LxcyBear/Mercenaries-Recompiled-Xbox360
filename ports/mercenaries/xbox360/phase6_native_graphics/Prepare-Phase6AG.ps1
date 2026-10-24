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
$p5 = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup"
$p4 = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$python = Join-Path $root ".venv\Scripts\python.exe"
$stage3 = Join-Path $root "build\phase3n_final_abi_scale"
$baseDir = Join-Path $root "build\phase6_native_graphics\native_d3d_createdevice_handoff_xdk"
$out = Join-Path $root "build\phase6_native_graphics\d3d_neighborhood_00290895_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6ag-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6ag_d3d_neighborhood_00290895.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}

foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6AG input: $v"
    }
}

$baseManifestPath = Join-Path $baseDir "phase6af-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    $baseManifestPath
)

$missing = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    $prep6af = Join-Path $p6 "Prepare-Phase6AF.ps1"
    if (-not (Test-Path -LiteralPath $prep6af)) {
        throw "Phase 6AG baseline missing and Phase 6AF prep was not found: $prep6af"
    }

    Write-Host "[Phase6AG] Cached Phase 6AF-B output is missing."
    Write-Host "[Phase6AG] Regenerating Phase 6AF-B without rebuilding the external solution..."
    & $prep6af -SkipSolutionBuild
}

foreach ($f in @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    $baseManifestPath,
    (Join-Path $stage3 "runtime\gen"),
    (Join-Path $stage3 "analysis\disasm\functions.json")
)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AG required input missing after baseline regeneration: $f"
    }
}

$baseManifest = Get-Content -LiteralPath $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6AF" -or
    $baseManifest.build_tag -ne "P6AF-NATIVE-D3D-CREATEDEVICE-HANDOFF-20261023-B") {
    throw "Phase 6AG Phase 6AF-B baseline identity mismatch"
}

$af = $baseManifest.phase6af_native_d3d_createdevice_handoff
if (-not [bool]$af.phase6ae_hardware_pass -or
    $af.native_handoff.guest_device_identity -ne "0x00299380" -or
    -not [bool]$af.native_handoff.strict_contract_validation) {
    throw "Phase 6AG inherited native CreateDevice contract drift"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AG] RETAIL D3D NEIGHBORHOOD 00290895"
Write-Host "[Phase6AG] 6AF-B hardware     : native CreateDevice handoff PASS, guest device 00299380"
Write-Host "[Phase6AG] Hardware boundary  : DIRECT_FRONTIER 0023A3CE -> 00290895"
Write-Host "[Phase6AG] Boundary state     : esp=008BF92C saved_esp=008BF92C fault=0"
Write-Host "[Phase6AG] Root closure       : depth 6 / cap 384, support-clean only"
Write-Host "[Phase6AG] Local D3D entries  : 00290881 / 00290884 / 00290887 when generated"
Write-Host "[Phase6AG] Result cleanup     : remove stale optional AV-call PASS requirements"
Write-Host "[Phase6AG] Purple             : still reserved for genuine NV2A MMIO/VRAM"

$args = @(
    "--base-dir",$baseDir,
    "--base-emitter",$paths.base,
    "--base-phase5bb-emitter",$paths.bb,
    "--base-phase5bc-emitter",$paths.bc,
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
    Write-Host "[Phase6AG] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6AG] Emitter log tail:"
    $tail = @(Get-Content -LiteralPath $log -Tail 180)
    $tail | ForEach-Object { Write-Host $_ }

    $reason = @(
        $tail | Where-Object {
            ($_ -match "\[Phase6AG\]|\[Phase5BC\]") -and
            ($_ -match "not an exact|absent|missing|unresolved|requires|refusing|lost|drift|already present|failed")
        }
    )
    if ($reason.Count -gt 0) {
        Write-Host ("[Phase6AG] PRIMARY FAILURE: {0}" -f [string]$reason[0])
    }
    throw "Phase 6AG emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6ag-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AG missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AG" -or
    $m.build_tag -ne "P6AG-D3D-NEIGHBORHOOD-00290895-20261023-A") {
    throw "Phase 6AG manifest identity mismatch"
}

$ag = $m.phase6ag_d3d_neighborhood
if (-not [bool]$ag.phase6af_hardware_pass -or
    $ag.root -ne "0x00290895" -or
    $ag.frontier_caller -ne "0x0023A3CE" -or
    [int]$ag.phase6af_hardware.next_boundary.fault -ne 0 -or
    -not [bool]$ag.stale_av_result_gate_removed -or
    -not [bool]$ag.native_createdevice_handoff_inherited_unchanged -or
    [int]$ag.packed_new_members -lt 1 -or
    $ag.source_layout.shard_prefix -ne "phase6ag_") {
    throw "Phase 6AG manifest D3D-neighborhood gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$monolithicText = Get-Content -LiteralPath $monolithic -Raw
$envText = Get-Content -LiteralPath $env -Raw

$policyMatch = [regex]::Match($monolithicText, 'trace\("Policy:([^"]*)"\);')
if (-not $policyMatch.Success) {
    throw "Phase 6AG startup policy trace missing"
}
if ($policyMatch.Groups[1].Value.Length -gt 240) {
    throw "Phase 6AG startup policy trace exceeds safe length"
}

foreach ($marker in @(
    "P6AG-D3D-NEIGHBORHOOD-00290895-20261023-A",
    "case 0x00290895u:",
    "s_phase6agRootEntered = 1;",
    "PASS: Phase 6AG retail D3D root 00290895 entered",
    "PASS: Phase 6AG native D3D CreateDevice handoff",
    "s_phase6agRootEntered &&",
    "P6AG XENOS: PASS Direct3D_CreateDevice",
    "P6AG FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
    "P6AG FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
    "phase6ag_env_build_cookie"
)) {
    if (-not $monolithicText.Contains($marker)) {
        throw "Phase 6AG generated source gate missing: $marker"
    }
}

if ($monolithicText.Contains("s_phase6aeAvEncoderCount != 0u &&") -or
    $monolithicText.Contains("s_phase6adAvGetCount != 0u &&")) {
    throw "Phase 6AG stale optional AV PASS gate remains"
}
if ($monolithicText -match "phase6af_env_build_cookie" -or
    $envText -match "phase6af_env_build_cookie") {
    throw "Phase 6AG stale Phase 6AF cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AG translated shard output is empty"
}
$wrongShards = @($shards | Where-Object { -not $_.Name.StartsWith("phase6ag_") })
if ($wrongShards.Count -gt 0) {
    throw "Phase 6AG translated shard prefix gate failed: $($wrongShards[0].Name)"
}

$rootInShard = $false
foreach ($shard in $shards) {
    if ((Get-Content -LiteralPath $shard.FullName -Raw).Contains("s_phase6agRootEntered = 1;")) {
        $rootInShard = $true
        break
    }
}
if (-not $rootInShard) {
    throw "Phase 6AG D3D root instrumentation did not survive sharding"
}

Write-Host ""
Write-Host "[Phase6AG] READY"
Write-Host ("[Phase6AG] Generated shards       : {0}" -f $shards.Count)
Write-Host ("[Phase6AG] Packed new D3D members : {0}" -f [int]$ag.packed_new_members)
Write-Host ("[Phase6AG] Pruned unsafe members   : {0}" -f [int]$ag.pruned_members)
Write-Host "[Phase6AG] Native CreateDevice     : inherited unchanged"
Write-Host "[Phase6AG] D3D root                : 00290895 exact/generated/support-clean"
Write-Host "[Phase6AG] Expected tag            : P6AG-D3D-NEIGHBORHOOD-00290895-20261023-A"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AG] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AG-D3D-NEIGHBORHOOD-00290895-20261023-A"
        ExpectedEnvCookie = "phase6ag_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6ag-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6ag-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AG.xex")
    }

    & $paths.build @buildArgs

    Write-Host ""
    Write-Host "[Phase6AG] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AG] Hardware tag to verify: P6AG-D3D-NEIGHBORHOOD-00290895-20261023-A"
    Write-Host ("[Phase6AG] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AG.xex"))
}
else {
    Write-Host "[Phase6AG] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
