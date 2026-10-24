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
$phase3nPrep = Join-Path $root "ports\mercenaries\xbox360\phase3n_final_abi_scale_xex\Prepare-Phase3N.ps1"
$manualSeeds = Join-Path $root "ports\mercenaries\manual-seeds.json"

$baseDir = Join-Path $root "build\phase6_native_graphics\d3d_neighborhood_00290895_xdk"
$out = Join-Path $root "build\phase6_native_graphics\d3d_saturation_0028e700_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6ah-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6ah_d3d_saturation_0028e700.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
    prep6ag = Join-Path $p6 "Prepare-Phase6AG.ps1"
}

foreach ($v in $paths.Values + @($python,$phase3nPrep,$manualSeeds)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6AH input: $v"
    }
}

$baseManifestPath = Join-Path $baseDir "phase6ag-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    $baseManifestPath
)

$missing = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    Write-Host "[Phase6AH] Cached Phase 6AG-D output is missing."
    Write-Host "[Phase6AH] Regenerating Phase 6AG-D without rebuilding the external solution..."
    & $paths.prep6ag -SkipSolutionBuild
}

$functionsPath = Join-Path $stage3 "analysis\disasm\functions.json"
$generatedRoot = Join-Path $stage3 "runtime\gen"

foreach ($f in @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    $baseManifestPath,
    $generatedRoot,
    $functionsPath
)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AH required input missing after baseline regeneration: $f"
    }
}

$baseManifest = Get-Content -LiteralPath $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6AG" -or
    $baseManifest.build_tag -ne "P6AG-D3D-NEIGHBORHOOD-00290895-20261023-D") {
    throw "Phase 6AH Phase 6AG-D baseline identity mismatch"
}

$ag = $baseManifest.phase6ag_d3d_neighborhood
if (-not [bool]$ag.phase6af_hardware_pass -or
    -not [bool]$ag.independent_phase_result_gate -or
    -not [bool]$ag.native_createdevice_handoff_inherited_unchanged -or
    $ag.root -ne "0x00290895") {
    throw "Phase 6AH inherited Phase 6AG model drift"
}

function Test-Phase6AHExactRoot {
    if (-not (Test-Path -LiteralPath $functionsPath -PathType Leaf)) {
        return $false
    }

    $rows = @(
        (Get-Content -LiteralPath $functionsPath -Raw | ConvertFrom-Json) |
            ForEach-Object { $_ }
    )

    foreach ($row in $rows) {
        $startText = ([string]$row.start).Trim()
        if ($startText -match '^0x[0-9A-Fa-f]+$') {
            $startValue = [Convert]::ToUInt32($startText.Substring(2), 16)
        }
        else {
            $startValue = [uint32]$startText
        }

        if ($startValue -eq 0x0028E700) {
            return $true
        }
    }

    return $false
}

$manualSeedText = Get-Content -LiteralPath $manualSeeds -Raw
if ($manualSeedText -notmatch '"0x0028E700"') {
    throw "Phase 6AH reviewed manual seed 0x0028E700 is missing"
}

if (-not (Test-Phase6AHExactRoot)) {
    Write-Host ""
    Write-Host "[Phase6AH] Cached Phase-3 inventory does not expose 0028E700 as an exact entry."
    Write-Host "[Phase6AH] Regenerating isolated Phase-3 analysis/generated tree from the hardware-reviewed seed..."
    Write-Host "[Phase6AH] VS2017 has not started yet."

    & $phase3nPrep

    if (-not (Test-Phase6AHExactRoot)) {
        throw "Phase 6AH regeneration did not promote 0x0028E700 to an exact function entry"
    }

    $generatedHit = @(Select-String -Path (Join-Path $generatedRoot "recomp_*.c") -SimpleMatch "void sub_0028E700(void)" -List -ErrorAction SilentlyContinue)
    if ($generatedHit.Count -lt 1) {
        throw "Phase 6AH function inventory contains 0x0028E700 but no generated sub_0028E700 body was found"
    }

    Write-Host "[Phase6AH] ENTRY REGENERATION: PASS - 0028E700 is now an exact generated function entry."
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AH] RETAIL D3D SATURATION 0028E700"
Write-Host "[Phase6AH] 6AG-D hardware     : exact 00290895 PASS; next DIRECT_FRONTIER 0028E700 fault=0"
Write-Host "[Phase6AH] Root support       : upstream diagnostic-only recomp_d3d_sync_checkpoint maintained as guest/device no-op"
Write-Host "[Phase6AH] Root closure       : depth 8 / cap 512, support-clean"
Write-Host "[Phase6AH] Saturation round   : one D3D-only round"
Write-Host "[Phase6AH] Saturation roots   : max 6 exact/generated D3D frontiers"
Write-Host "[Phase6AH] Saturation closure : depth 2 / cap 64 each / max 192 new members"
Write-Host "[Phase6AH] Hard stops         : NV2A/MMIO/VRAM, platform, ABI, guest faults"
Write-Host "[Phase6AH] Purple             : still reserved for first genuine NV2A/MMIO/VRAM touch"

$args = @(
    "--base-dir",$baseDir,
    "--base-emitter",$paths.base,
    "--base-phase5bb-emitter",$paths.bb,
    "--base-phase5bc-emitter",$paths.bc,
    "--generated-root",$generatedRoot,
    "--functions",$functionsPath,
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
    Write-Host "[Phase6AH] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6AH] Emitter log tail:"
    $tail = @(Get-Content -LiteralPath $log -Tail 220)
    $tail | ForEach-Object { Write-Host $_ }

    $reason = @(
        $tail | Where-Object {
            ($_ -match "\[Phase6AH\]|\[Phase5BC\]") -and
            ($_ -match "not an exact|absent|missing|unresolved|requires|refusing|lost|drift|already present|failed")
        }
    )

    $primaryFailure = $null
    if ($reason.Count -gt 0) {
        $primaryFailure = [string]$reason[0]
        Write-Host ("[Phase6AH] PRIMARY FAILURE: {0}" -f $primaryFailure)
    }
    else {
        $plain = @(
            $tail | Where-Object {
                ($_ -notmatch '^At ') -and
                ($_ -notmatch '^\s*\+') -and
                ($_ -notmatch '^\s*CategoryInfo') -and
                ($_ -notmatch '^\s*FullyQualifiedErrorId') -and
                ($_ -notmatch '^\s*$')
            }
        )

        if ($plain.Count -gt 0) {
            $primaryFailure = [string]$plain[$plain.Count - 1]
            Write-Host ("[Phase6AH] PRIMARY FAILURE (fallback): {0}" -f $primaryFailure)
        }
    }

    if ($null -ne $primaryFailure) {
        throw ("Phase 6AH emission/preflight failed (exit {0}): {1}" -f $rc,$primaryFailure)
    }

    throw "Phase 6AH emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6ah-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AH missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AH" -or
    $m.build_tag -ne "P6AH-D3D-SYNC-0028E700-20261023-D") {
    throw "Phase 6AH manifest identity mismatch"
}

$ah = $m.phase6ah_d3d_saturation
if (-not [bool]$ah.phase6ag_hardware_pass -or
    $ah.root -ne "0x0028E700" -or
    $ah.frontier_caller -ne "0x0023A3CE" -or
    [int]$ah.phase6ag_hardware.next_boundary.fault -ne 0 -or
    $ah.phase6ag_hardware.next_boundary.target -ne "0x0028E700" -or
    -not [bool]$ah.native_createdevice_handoff_inherited_unchanged -or
    -not [bool]$ah.exact_00290895_split_inherited_unchanged -or
    -not [bool]$ah.d3d_sync_checkpoint_support.required_for_root -or
    [int]$ah.root_retained_new_members -lt 1 -or
    $ah.source_layout.shard_prefix -ne "phase6ah_") {
    throw "Phase 6AH manifest saturation gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$monolithicText = Get-Content -LiteralPath $monolithic -Raw
$envText = Get-Content -LiteralPath $env -Raw

$policyMatch = [regex]::Match($monolithicText, 'trace\("Policy:([^"]*)"\);')
if (-not $policyMatch.Success) {
    throw "Phase 6AH startup policy trace missing"
}
if ($policyMatch.Groups[1].Value.Length -gt 240) {
    throw "Phase 6AH startup policy trace exceeds safe length"
}

foreach ($marker in @(
    "P6AH-D3D-SYNC-0028E700-20261023-D",
    "case 0x0028E700u:",
    "s_phase6ahRootEntered = 1;",
    "PASS: Phase 6AH retail D3D root 0028E700 entered",
    "static void recomp_d3d_sync_checkpoint(uint32_t phase)",
    "++s_phase6ahD3DSyncCheckpointCalls;",
    "P6AH D3D SYNC CHECKPOINT: calls=%u last_phase=%u",
    "PHASE 6AH D3D SATURATION RESULT: %s",
    "s_phase6ahRootEntered && s_phase6agRootEntered && s_phase6afCreateDeviceBridgeCount != 0u && s_phase6ahD3DSyncCheckpointCalls != 0u",
    "P6AH PRIOR D3D ROOT 00290895 RESULT: %s",
    "PASS: Phase 6AH native D3D CreateDevice handoff",
    "P6AH XENOS: PASS Direct3D_CreateDevice",
    "P6AH FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
    "P6AH FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
    "phase6ah_env_build_cookie"
)) {
    if (-not $monolithicText.Contains($marker)) {
        throw "Phase 6AH generated source gate missing: $marker"
    }
}

if ($monolithicText -match "phase6ag_env_build_cookie" -or
    $envText -match "phase6ag_env_build_cookie") {
    throw "Phase 6AH stale Phase 6AG cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AH translated shard output is empty"
}
$wrongShards = @($shards | Where-Object { -not $_.Name.StartsWith("phase6ah_") })
if ($wrongShards.Count -gt 0) {
    throw "Phase 6AH translated shard prefix gate failed: $($wrongShards[0].Name)"
}

$rootInShard = $false
foreach ($shard in $shards) {
    if ((Get-Content -LiteralPath $shard.FullName -Raw).Contains("s_phase6ahRootEntered = 1;")) {
        $rootInShard = $true
        break
    }
}
if (-not $rootInShard) {
    throw "Phase 6AH D3D root instrumentation did not survive sharding"
}

Write-Host ""
Write-Host "[Phase6AH] READY"
Write-Host ("[Phase6AH] Generated shards             : {0}" -f $shards.Count)
Write-Host ("[Phase6AH] Root candidate members       : {0}" -f [int]$ah.root_candidate_members)
Write-Host ("[Phase6AH] Root retained new members    : {0}" -f [int]$ah.root_retained_new_members)
Write-Host ("[Phase6AH] Saturation selected roots    : {0}" -f @($ah.saturation.selected_roots).Count)
Write-Host ("[Phase6AH] Saturation retained new      : {0}" -f [int]$ah.saturation.retained_new_members)
Write-Host ("[Phase6AH] Remaining direct frontiers   : {0}" -f @($ah.remaining_direct_frontiers).Count)
Write-Host "[Phase6AH] D3D sync checkpoint           : maintained diagnostic-only no-op"
Write-Host "[Phase6AH] Native CreateDevice           : inherited unchanged"
Write-Host "[Phase6AH] Prior exact root 00290895     : inherited unchanged"
Write-Host "[Phase6AH] Current root                  : 0028E700 exact/generated/support-clean"
Write-Host "[Phase6AH] Expected tag                  : P6AH-D3D-SYNC-0028E700-20261023-D"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AH] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AH-D3D-SYNC-0028E700-20261023-D"
        ExpectedEnvCookie = "phase6ah_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6ah-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6ah-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AH-D.xex")
    }

    & $paths.build @buildArgs

    Write-Host ""
    Write-Host "[Phase6AH] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AH] Hardware tag to verify: P6AH-D3D-SYNC-0028E700-20261023-D"
    Write-Host ("[Phase6AH] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AH-D.xex"))
}
else {
    Write-Host "[Phase6AH] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
