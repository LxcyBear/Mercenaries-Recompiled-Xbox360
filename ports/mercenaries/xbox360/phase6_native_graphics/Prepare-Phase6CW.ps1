[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p4=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$p5=Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup"
$python=Join-Path $root ".venv\Scripts\python.exe"
$stage3=Join-Path $root "build\phase3n_final_abi_scale"
$base=Join-Path $root "build\phase6_native_graphics\shadow_ram_f0000000_xdk"
$out=Join-Path $root "build\phase6_native_graphics\dsound_sweep_002a6713_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cw_dsound_002a6713.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p5bb=Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
$p5bc=Join-Path $p5 "emit_phase5bc_broad_sweep.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$generatedRoot=Join-Path $stage3 "runtime\gen"
$functions=Join-Path $stage3 "analysis\disasm\functions.json"
$recompile=Join-Path $root "ports\mercenaries\scripts\Recompile.ps1"
$manualSource=Join-Path $root "ports\mercenaries\src\recomp_manual.c"

foreach($f in @($python,$emitter,$baseEmitter,$p5bb,$p5bc,$p6bl,$builder,$generatedRoot,$functions,$recompile,$manualSource)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CW input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cv-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cv=Join-Path $PSScriptRoot "Prepare-Phase6CV.ps1"
  if(-not(Test-Path -LiteralPath $prep6cv)){
    throw "Phase 6CW baseline missing and Phase 6CV regeneration script not found"
  }
  Write-Host "[Phase6CW] Cached 6CV output missing; regenerating 6CV without solution build..."
  & $prep6cv -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CW could not regenerate 6CV baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cv-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CV"-or$m.build_tag-ne"P6CV-SHADOW-RAM-F0000000-20261025-A"){
  throw "Phase 6CW baseline identity mismatch"
}
$cv=$m.phase6cv_shadow_ram_alias
if($cv.execution_budget_inherited-ne64000000-or
   $cv.async_read_semantics_changed-ne$false-or
   $cv.partition0_semantics_changed-ne$false-or
   $cv.graphics_mmio_semantics_changed-ne$false-or
   $cv.apu_mmio_semantics_changed-ne$false-or
   $cv.kseg_semantics_changed-ne$false-or
   $cv.hard_fences_weakened-ne$false-or
   $cv.mapping.guest_start-ne"0xF0000000"-or
   $cv.mapping.guest_end_exclusive-ne"0xF4000000"){
  throw "Phase 6CW inherited 6CV policy mismatch"
}

Write-Host "[Phase6CW] POST-SHADOW-RAM DSOUND SWEEP"
Write-Host "[Phase6CW] 6CV hardware: 3 successful F08B0000 -> 008B0000 reads"
Write-Host "[Phase6CW] New boundary : DIRECT 0023A3CE -> 002A6713, fault=0"
Write-Host "[Phase6CW] Target section: DSOUND 0029CB80-002BB274"
Write-Host "[Phase6CW] Strategy: exact-root validation + support-clean DSOUND sibling sweep"
Write-Host "[Phase6CW] Candidate cap: 1024 exact generated DSOUND starts"
Write-Host "[Phase6CW] Interior/missing-body/unresolved-support targets remain fenced"
Write-Host "[Phase6CW] Preserve 6CV shadow-RAM + XACT + D3D/XGRPH + APU semantics"
Write-Host "[Phase6CW] Watchdog: preserve 64,000,000 translated blocks"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CW emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CW-R3"')){
  throw "Phase 6CW stale emitter detected; expected revision 6CW-R3"
}
Write-Host "[Phase6CW] Emitter revision       : 6CW-R3"

$recompileText=Get-Content $recompile -Raw
$manualText=Get-Content $manualSource -Raw
if(-not$recompileText.Contains('"--manual-function", "0x002A6713"')){
  throw "Phase 6CW source policy changed: Recompile.ps1 no longer marks 0x002A6713 manual"
}
if(-not$manualText.Contains("void sub_002A6713(void)") -or
   -not$manualText.Contains("merc_dsound_rng_advance")){
  throw "Phase 6CW maintained manual DSOUND source is missing"
}
Write-Host "[Phase6CW] Manual root policy      : verified in Recompile.ps1"
Write-Host "[Phase6CW] Manual root source      : verified in recomp_manual.c"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",$baseEmitter,
  "--phase5bb-emitter",$p5bb,
  "--phase5bc-emitter",$p5bc,
  "--phase6bl-emitter",$p6bl,
  "--generated-root",$generatedRoot,
  "--functions",$functions,
  "--out-dir",$out
)

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 |
    Tee-Object -Variable phase6cwEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CW] EMITTER OUTPUT:"
  $phase6cwEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CW emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cw-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CW output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CW"-or$r.build_tag-ne"P6CW-DSOUND-SWEEP-002A6713-20261026-A"){
  throw "Phase 6CW manifest identity mismatch"
}
$k=$r.phase6cw_dsound_sweep
if($k.phase6cv_hardware.boundary_kind-ne"DIRECT_FRONTIER"-or
   $k.phase6cv_hardware.caller-ne"0x0023A3CE"-or
   $k.phase6cv_hardware.target-ne"0x002A6713"-or
   $k.phase6cv_hardware.fault-ne0-or
   $k.phase6cv_hardware.shadow_reads-ne3-or
   $k.phase6cv_hardware.shadow_guest-ne"0xF08B0000"-or
   $k.phase6cv_hardware.shadow_physical-ne"0x008B0000"-or
   $k.root-ne"0x002A6713"-or
   $k.manual_root_dispatch-ne$true-or
   $k.manual_root_source-ne"ports/mercenaries/src/recomp_manual.c"-or
   $k.target_section-ne"DSOUND"-or
   $k.execution_budget_inherited-ne64000000-or
   $k.shadow_ram_alias_preserved-ne$true-or
   $k.async_read_semantics_changed-ne$false-or
   $k.partition0_semantics_changed-ne$false-or
   $k.graphics_mmio_semantics_changed-ne$false-or
   $k.apu_mmio_semantics_changed-ne$false-or
   $k.kseg_semantics_changed-ne$false-or
   $k.hard_fences_weakened-ne$false){
  throw "Phase 6CW manifest gate failed"
}
if([int]$k.packed_new_members-lt1){
  throw "Phase 6CW packed no new DSOUND members"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CW-DSOUND-SWEEP-002A6713-20261026-A",
  "phase6cw_env_build_cookie",
  "case 0x002A6713u:",
  "PASS: Phase 6CW entered DSOUND frontier 002A6713",
  "PASS: Phase 6CW manual DSOUND decrypt",
  "GUEST_WRITE32(0x002BB168u, low);",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "#define PHASE6CV_SHADOW_END  0xF4000000u",
  "offset = address - PHASE6CV_SHADOW_BASE;",
  "P6CW SHADOW RAM:",
  "P6CW ASYNC STREAM READ:",
  "P6CW PIXEL CHASE:",
  "P6CW PRESENT PROXIMITY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CW source gate missing: $marker"}
}

if(([regex]::Matches($text,[regex]::Escape("case 0x002A6713u:"))).Count-ne1){
  throw "Phase 6CW mandatory DSOUND root dispatch count mismatch"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CW translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6CW] READY"
Write-Host ("[Phase6CW] DSOUND root                  : {0}" -f [string]$k.root)
Write-Host ("[Phase6CW] Root name                    : {0}" -f [string]$k.root_name)
Write-Host ("[Phase6CW] Generated DSOUND members     : {0}" -f [int]$k.total_generated_dsound_members)
Write-Host ("[Phase6CW] Remaining DSOUND members     : {0}" -f [int]$k.remaining_generated_dsound_members)
Write-Host ("[Phase6CW] Selected sibling candidates  : {0}" -f [int]$k.selected_candidate_members)
Write-Host ("[Phase6CW] Truncated by 1024 cap        : {0}" -f [int]$k.truncated_candidate_members)
Write-Host ("[Phase6CW] Pruned unsafe members        : {0}" -f [int]$k.pruned_members)
Write-Host ("[Phase6CW] Packed new members           : {0}" -f [int]$k.packed_new_members)
Write-Host ("[Phase6CW] Expanded pack members        : {0}" -f [int]$k.expanded_pack_members)
Write-Host ("[Phase6CW] Generated shards             : {0}" -f $shardCount)
Write-Host "[Phase6CW] Shadow RAM alias             : preserved"
Write-Host "[Phase6CW] XACT/D3D/XGRPH/APU           : preserved"
Write-Host "[Phase6CW] 64M watchdog                 : preserved"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CW-DSOUND-SWEEP-002A6713-20261026-A"
    ExpectedEnvCookie="phase6cw_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cw-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cw-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CW-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CW] BUILD PASS"
  Write-Host ("[Phase6CW] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CW-A.xex"))
}
