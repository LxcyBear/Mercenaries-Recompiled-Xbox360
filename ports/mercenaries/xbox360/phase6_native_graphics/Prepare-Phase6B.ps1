[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phase6Root = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phase6Root "..\..\..\.."))
$phase5Root = Join-Path $repoRoot "ports\mercenaries\xbox360\phase5_subsystem_bringup"
$phase4cRoot = Join-Path $repoRoot "ports\mercenaries\xbox360\phase4c_native_startup"

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$stage3Root = Join-Path $repoRoot "build\phase3n_final_abi_scale"
$generatedRoot = Join-Path $stage3Root "runtime\gen"
$functionsPath = Join-Path $stage3Root "analysis\disasm\functions.json"
$entryReport = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-startup-closure.json"
$threadReport = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-thread-routine.json"

$baseEmitter = Join-Path $phase4cRoot "emit_phase4c_startup_slice.py"
$basePhase5bbEmitter = Join-Path $phase5Root "emit_phase5bb_frontier22dda4.py"
$basePhase5bcEmitter = Join-Path $phase5Root "emit_phase5bc_broad_sweep.py"
$basePhase5bdEmitter = Join-Path $phase5Root "emit_phase5bd_regional_sweep.py"
$basePhase5beEmitter = Join-Path $phase5Root "emit_phase5be_forward_sweep.py"
$basePhase5bfEmitter = Join-Path $phase5Root "emit_phase5bf_forward_sweep.py"
$basePhase5bgEmitter = Join-Path $phase5Root "emit_phase5bg_text_tail_sweep.py"
$basePhase5bhEmitter = Join-Path $phase5Root "emit_phase5bh_direct_frontier_mop.py"
$basePhase5biEmitter = Join-Path $phase5Root "emit_phase5bi_low_text_sweep.py"
$basePhase5bjEmitter = Join-Path $phase5Root "emit_phase5bj_deep_low_text_sweep.py"
$basePhase5bkEmitter = Join-Path $phase5Root "emit_phase5bk_diagnostic_mop.py"
$basePhase5blEmitter = Join-Path $phase5Root "emit_phase5bl_high_tail_sweep.py"
$basePhase5bmEmitter = Join-Path $phase5Root "emit_phase5bm_low_text_sweep.py"
$basePhase5bnEmitter = Join-Path $phase5Root "emit_phase5bn_deep_low_sweep.py"
$basePhase5boEmitter = Join-Path $phase5Root "emit_phase5bo_mid_text_sweep.py"
$basePhase5bpEmitter = Join-Path $phase5Root "emit_phase5bp_low_text_sweep.py"
$basePhase5bqEmitter = Join-Path $phase5Root "emit_phase5bq_low_text_sweep.py"
$basePhase5brEmitter = Join-Path $phase5Root "emit_phase5br_low_text_sweep.py"
$basePhase5bsEmitter = Join-Path $phase5Root "emit_phase5bs_low_text_sweep.py"
$basePhase5btEmitter = Join-Path $phase5Root "emit_phase5bt_mid_text_sweep.py"
$basePhase5buEmitter = Join-Path $phase5Root "emit_phase5bu_mid_text_sweep.py"
$basePhase5bvEmitter = Join-Path $phase5Root "emit_phase5bv_repeatability.py"

$emitter = Join-Path $phase6Root "emit_phase6b_first_graphics_touch.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase6_native_graphics\first_graphics_touch_xdk"

foreach ($required in @(
    $python,
    $generatedRoot,
    $functionsPath,
    $entryReport,
    $threadReport,
    $baseEmitter,
    $basePhase5bbEmitter,
    $basePhase5bcEmitter,
    $basePhase5bdEmitter,
    $basePhase5beEmitter,
    $basePhase5bfEmitter,
    $basePhase5bgEmitter,
    $basePhase5bhEmitter,
    $basePhase5biEmitter,
    $basePhase5bjEmitter,
    $basePhase5bkEmitter,
    $basePhase5blEmitter,
    $basePhase5bmEmitter,
    $basePhase5bnEmitter,
    $basePhase5boEmitter,
    $basePhase5bpEmitter,
    $basePhase5bqEmitter,
    $basePhase5brEmitter,
    $basePhase5bsEmitter,
    $basePhase5btEmitter,
    $basePhase5buEmitter,
    $basePhase5bvEmitter,
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 6B input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase6B] FIRST MERCENARIES -> XENOS GRAPHICS TOUCH"
Write-Host "[Phase6B] Base: Phase 5BV 3/3 repeatable runtime + Phase 6A native Xenos surface."
Write-Host "[Phase6B] Resume root: 0x0014CD30 (exact generated title function)."
Write-Host "[Phase6B] Policy: continue through bounded exact translated code and stop at the first new genuine graphics/platform boundary."
Write-Host "[Phase6B] No fake GPU success. Purple is a diagnostic marker only if Mercenaries reaches NV2A MMIO/VRAM."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase6_native_graphics\phase6b-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $emitArgs = @(
        "--base-phase5bv-emitter", $basePhase5bvEmitter,
        "--base-phase5bu-emitter", $basePhase5buEmitter,
        "--base-phase5bt-emitter", $basePhase5btEmitter,
        "--base-phase5bs-emitter", $basePhase5bsEmitter,
        "--base-phase5br-emitter", $basePhase5brEmitter,
        "--base-phase5bq-emitter", $basePhase5bqEmitter,
        "--base-phase5bp-emitter", $basePhase5bpEmitter,
        "--base-phase5bo-emitter", $basePhase5boEmitter,
        "--base-phase5bn-emitter", $basePhase5bnEmitter,
        "--base-phase5bm-emitter", $basePhase5bmEmitter,
        "--base-phase5bl-emitter", $basePhase5blEmitter,
        "--base-phase5bk-emitter", $basePhase5bkEmitter,
        "--base-phase5bj-emitter", $basePhase5bjEmitter,
        "--base-phase5bi-emitter", $basePhase5biEmitter,
        "--base-phase5bh-emitter", $basePhase5bhEmitter,
        "--base-phase5bg-emitter", $basePhase5bgEmitter,
        "--base-phase5bf-emitter", $basePhase5bfEmitter,
        "--base-phase5be-emitter", $basePhase5beEmitter,
        "--base-phase5bd-emitter", $basePhase5bdEmitter,
        "--base-phase5bc-emitter", $basePhase5bcEmitter,
        "--base-phase5bb-emitter", $basePhase5bbEmitter,
        "--base-emitter", $baseEmitter,
        "--generated-root", $generatedRoot,
        "--functions", $functionsPath,
        "--entry-report", $entryReport,
        "--thread-report", $threadReport,
        "--phase3n-template", $phase3nTemplate,
        "--phase2e-source", $phase2eSource,
        "--out-dir", $outDir
    )

    & $python $emitter @emitArgs 2>&1 | Tee-Object -FilePath $emitLog
    $emitExit = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

if ($emitExit -ne 0) {
    Write-Host ""
    Write-Host "[Phase6B] Emitter log tail:"
    $tailText = ""
    if (Test-Path -LiteralPath $emitLog) {
        Get-Content -LiteralPath $emitLog -Tail 180 | ForEach-Object {
            Write-Host $_
        }
        $tailText = (Get-Content -LiteralPath $emitLog -Tail 80) -join [Environment]::NewLine
    }
    Write-Host ""
    throw ("Phase 6B emission failed (exit {0}). Full emitter output: {1}{2}{3}" -f $emitExit, $emitLog, [Environment]::NewLine, $tailText)
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase6b-manifest.json"

foreach ($generatedFile in @($main, $env, $manifest)) {
    if (-not (Test-Path -LiteralPath $generatedFile)) {
        throw "Phase 6B emitter did not produce required file: $generatedFile"
    }
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json

foreach ($requiredText in @(
    "P6B-FIRST-GRAPHICS-TOUCH-20261021-A",
    "#include <d3d9.h>",
    "case 0x0014CD30u: return sub_0014CD30;",
    "s_phase6bRootEntered = 1;",
    "P6B XENOS: PASS Direct3D_CreateDevice",
    "P6B FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
    "P6B FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
    "PHASE 6B FIRST GRAPHICS TOUCH RESULT",
    "without fabricating backend success"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 6B main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 6B RETAIL ENVIRONMENT PREP START",
    "PHASE 6B EXACT RETAIL VERIFICATION: PASS",
    "PHASE 6B EXECUTION ENVIRONMENT RESULT: PASS",
    "phase6b_env_build_cookie",
    "50364242",
    "PHASE 6B RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 6B phase5_env.cpp is missing marker: $requiredText"
    }
}

if ($manifestJson.phase -ne "6B" -or
    $manifestJson.build_tag -ne "P6B-FIRST-GRAPHICS-TOUCH-20261021-A") {
    throw "Phase 6B manifest identity mismatch"
}

$gate = $manifestJson.phase6b_first_graphics_touch
if ($gate.source_phase -ne "5BV" -or
    -not [bool]$gate.phase5_frozen_baseline -or
    -not [bool]$gate.phase6a_xenos_visual_proof -or
    $gate.root -ne "0x0014CD30" -or
    [int]$gate.direct_closure_depth -ne 12 -or
    [int]$gate.direct_closure_cap -ne 512 -or
    [int]$gate.xenos_surface.width -ne 640 -or
    [int]$gate.xenos_surface.height -ne 480 -or
    $gate.xenos_surface.format -ne "D3DFMT_A8R8G8B8") {
    throw "Phase 6B manifest contract mismatch"
}

if ([int]$gate.packed_new_members -lt 1) {
    throw "Phase 6B packed no new translated title code"
}

Write-Host ""
Write-Host "[Phase6B] READY"
Write-Host ("[Phase6B] New translated members : {0}" -f [int]$gate.packed_new_members)
Write-Host ("[Phase6B] Direct closure          : depth={0} cap={1}" -f [int]$gate.direct_closure_depth, [int]$gate.direct_closure_cap)
Write-Host "[Phase6B] Native Xenos surface     : 640x480 A8R8G8B8, vsync"
Write-Host "[Phase6B] Root                     : 0x0014CD30"
Write-Host "[Phase6B] Build BOTH freshly generated sources:"
Write-Host "[Phase6B]   $main"
Write-Host "[Phase6B]   $env"
Write-Host "[Phase6B] Link d3d9.lib in the Xbox 360 XDK project."
Write-Host "[Phase6B] Expected build tag: P6B-FIRST-GRAPHICS-TOUCH-20261021-A"
Write-Host ""
Write-Host "[Phase6B] Hardware interpretation:"
Write-Host "[Phase6B]   dark near-black = Xenos device alive while Mercenaries starts"
Write-Host "[Phase6B]   purple          = Mercenaries reached NV2A MMIO/VRAM hard boundary"
Write-Host "[Phase6B]   dark blue       = another new translated/kernel/ABI frontier"
Write-Host "[Phase6B] Purple is NOT yet a guest-rendered frame; send the full xbWatson log."
