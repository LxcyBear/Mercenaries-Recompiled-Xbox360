[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild,
  [switch]$FullClean
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p4=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$p5=Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup"
$python=Join-Path $root ".venv\Scripts\python.exe"
$stage3=Join-Path $root "build\phase3n_final_abi_scale"
$base=Join-Path $root "build\phase6_native_graphics\apu_vp_free_xdk"
$out=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6dq_rocket_frontier_journal.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase5bbEmitter=Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
$phase5bcEmitter=Join-Path $p5 "emit_phase5bc_broad_sweep.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @(
  $python,$emitter,$baseEmitter,$phase5bbEmitter,$phase5bcEmitter,
  $phase6blEmitter,$builder
)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6DQ ROCKET input: $f"
  }
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6dp-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6dp=Join-Path $PSScriptRoot "Prepare-Phase6DP.ps1"
  if(-not(Test-Path -LiteralPath $prep6dp)){
    throw "Phase 6DQ baseline missing and Phase 6DP regeneration script not found"
  }

  Write-Host "[Phase6DQ] Cached 6DP output missing; regenerating 6DP without solution build..."
  & $prep6dp -SkipSolutionBuild

  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DQ could not regenerate 6DP baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6dp-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DP"-or$m.build_tag-ne"P6DP-APU-VP-FREE-20261026-A"){
  throw "Phase 6DQ baseline identity mismatch"
}

$generatedRoot=Join-Path $stage3 "runtime\gen"
$functions=Join-Path $stage3 "analysis\disasm\functions.json"
foreach($f in @($generatedRoot,$functions)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Phase 6DQ generated-code analysis input missing: $f"
  }
}

Write-Host "[Phase6DQ] ================================================"
Write-Host "[Phase6DQ]          ROCKET FRONTIER JOURNAL"
Write-Host "[Phase6DQ] ================================================"
Write-Host "[Phase6DQ] Hardware seed: 6DP crossed VP FREE FE820010 -> 00000080"
Write-Host "[Phase6DQ] Next proven boundary: WRITE32 FE8202A4 at tick 26,712,259"
Write-Host "[Phase6DQ] Historical early CCCCCCD0 path: ELIMINATED; R16 deep DSOUND recurrence: CLASSIFIED + R17 QUARANTINED"
Write-Host "[Phase6DQ] XACT root teardown/global-zero regression: ABSENT"
Write-Host "[Phase6DQ] Static pack cap: 4096 new support-clean functions"
Write-Host "[Phase6DQ] Priority: D3D -> XGRPH -> DSOUND -> TEXT_HOT -> XACTENG -> WMADEC/XPP/XMV"
Write-Host "[Phase6DQ] VP aligned WRITE32: diagnostic continue + journal"
Write-Host "[Phase6DQ] Unknown VP reads: HARD FENCE"
Write-Host "[Phase6DQ] IOAPIC FEC00000-0FFF: DEFAULT-OFFSET BATCH BRIDGE (xemu/QEMU semantics)"
Write-Host "[Phase6DQ] Kernel ordinal 151 KeStallExecutionProcessor: QPC BUSY-WAIT BRIDGE ARMED"
Write-Host "[Phase6DQ] DSOUND poison dispatch 002A41F7: EXACT SLOT QUARANTINE ARMED (CCCCCCCC -> journaled DS_OK no-op)"
Write-Host "[Phase6DQ] Non-VP MMIO/NV2A unknowns: HARD FENCE"
Write-Host "[Phase6DQ] Dispatch logging: first unique + aggregate, progress every 65536"
Write-Host "[Phase6DQ] Build mode: $(if($FullClean){'FULL CLEAN'}else{'INCREMENTAL (clean skipped)'})"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){
  throw "Phase 6DQ emitter syntax check failed"
}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DQ-R22"')){
  throw "Phase 6DQ stale emitter detected; expected revision 6DQ-R22"
}
Write-Host "[Phase6DQ] Emitter revision: 6DQ-R22"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",$baseEmitter,
  "--phase5bb-emitter",$phase5bbEmitter,
  "--phase5bc-emitter",$phase5bcEmitter,
  "--phase6bl-emitter",$phase6blEmitter,
  "--generated-root",$generatedRoot,
  "--functions",$functions,
  "--out-dir",$out
)

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6dqEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DQ] EMITTER OUTPUT:"
  $phase6dqEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DQ emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6dq-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6DQ output: $f"
  }
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DQ"-or$r.build_tag-ne"P6DQ-ROCKET-FRONTIER-JOURNAL-20261026-A"){
  throw "Phase 6DQ manifest identity mismatch"
}

$q=$r.phase6dq_rocket_frontier_journal
if($q.emitter_revision-ne"6DQ-R22"-or
   $q.phase6dp_hardware.vp_free_read_passed-ne$true-or
   $q.phase6dp_hardware.new_boundary_target-ne"0xFE8202A4"-or
   $q.phase6dp_hardware.new_boundary_ticks-ne26712259-or
   $q.phase6dp_hardware.historical_ccccccd0_observed-ne$false-or
   $q.phase6dp_hardware.xact_final_release_entries-ne0-or
   $q.phase6dp_hardware.xact_global_zero_writes-ne0-or
   $q.static_pack.candidate_cap-ne4096-or
   $q.static_pack.expanded_pack_members-lt$q.static_pack.base_pack_members-or
   $q.runtime_journal.dispatch_unique_capacity-ne96-or
   $q.runtime_journal.hard_stop_unique_capacity-ne24-or
   $q.runtime_journal.vp_write_unique_capacity-ne64-or
   $q.runtime_journal.dispatch_log_stride-ne65536-or
   $q.vp_diagnostic_continue.aligned_write32_continue-ne$true-or
   $q.vp_diagnostic_continue.write32_semantics_complete-ne$false-or
   $q.vp_diagnostic_continue.unknown_read32_fenced-ne$true-or
   $q.vp_diagnostic_continue.audio_fidelity_claimed-ne$false-or
   $q.dsound_poison_slot_bridge.fault_site-ne"0x002A41F7"-or
   $q.dsound_poison_slot_bridge.poison_value-ne"0xCCCCCCCC"-or
   $q.dsound_poison_slot_bridge.synthetic_noop_target-ne"0xF6DCCCD0"-or
   $q.dsound_poison_slot_bridge.ordinary_guest_faults_bypassed-ne$false-or
   $q.dsound_poison_slot_bridge.emitter_source_shape_guard-ne$true-or
   $q.dsound_poison_slot_bridge.definition_not_forward_declaration_guard-ne$true-or
   $q.dsound_poison_slot_bridge.function_local_unique_dispatch_pair_guard-ne$true-or
   $q.dsound_poison_slot_bridge.guarded_dereference_postcheck-ne$true-or
   $q.dsound_poison_slot_bridge.accepts_inherited_apu_routed_accessor-ne$true-or
   $q.kernel_timing_bridge.hardware_seed_microseconds-ne20-or
   $q.kernel_timing_bridge.hardware_seed_calls-ne1000-or
   $q.execution_budget-ne64000000-or
   $q.generated_c4146_scope_inherited-ne$true-or
   $q.allocator_repairs_inherited-ne$true-or
   $q.xact_refcount_semantics_changed-ne$false-or
   $q.destructor_suppressed-ne$false-or
   $q.free_suppressed-ne$false-or
   $q.ordinary_guest_memory_fences_changed-ne$false-or
   $q.vp_write32_fence_changed_for_diagnostics-ne$true-or
   $q.unknown_vp_read_fences_changed-ne$false-or
   $q.non_vp_mmio_fences_changed-ne$false-or
   $q.nv2a_mmio_policy_changed-ne$false){
  throw "Phase 6DQ manifest policy gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DQ-ROCKET-FRONTIER-JOURNAL-20261026-A",
  "phase6dq_env_build_cookie",
  "P6DQ ROCKET DISPATCH FIRST",
  "P6DQ ROCKET HARD STOP",
  "P6DQ ROCKET VP WRITE FIRST",
  "P6DQ ROCKET VP READ HARD",
  "P6DQ ROCKET JOURNAL SUMMARY",
  "phase6dq_dump_journals();",
  "vp_write32_diagnostic_continue=1 unknown_vp_reads_fenced=1",
  "(s_phase5bcPackedIcallDispatchCount & 0xFFFFu) == 0u",
  "(s_phase5bcPackedDirectDispatchCount & 0xFFFFu) == 0u",
  "P6DQ PIXEL CHASE:",
  "P6DQ PRESENT PROXIMITY:",
  "P6DQ DSOUND POISON SLOT:",
  "P6DQ DSOUND POISON NOOP:",
  "target == 0xF6DCCCD0u",
  "#define PHASE4C_EXEC_BUDGET 64000000u",
  "#pragma warning(disable:4146)"
)){
  if(-not$text.Contains($marker)){
    throw "Phase 6DQ source gate missing: $marker"
  }
}

if($text.Contains("(s_phase5bcPackedIcallDispatchCount & 0xFFFu) == 0u")){
  throw "Phase 6DQ stale 4096 ICALL logging cadence remains"
}
if($text.Contains("(s_phase5bcPackedDirectDispatchCount & 0xFFFu) == 0u")){
  throw "Phase 6DQ stale 4096 DIRECT logging cadence remains"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){
  throw "Phase 6DQ translated shard output is empty"
}

Write-Host ""
Write-Host "[Phase6DQ] ================= ROCKET READY ================="
Write-Host ("[Phase6DQ] Base pack members       : {0}" -f [int]$q.static_pack.base_pack_members)
Write-Host ("[Phase6DQ] Candidate functions     : {0}" -f [int]$q.static_pack.candidate_members)
Write-Host ("[Phase6DQ] Pruned unsafe functions : {0}" -f [int]$q.static_pack.pruned_members)
Write-Host ("[Phase6DQ] Packed new functions    : {0}" -f [int]$q.static_pack.packed_new_members)
Write-Host ("[Phase6DQ] Total pack members      : {0}" -f [int]$q.static_pack.expanded_pack_members)
Write-Host ("[Phase6DQ] Generated shards        : {0}" -f $shardCount)
Write-Host ("[Phase6DQ] D3D selected            : {0}" -f [int]$q.static_pack.selected_by_section_before_prune.D3D)
Write-Host ("[Phase6DQ] XGRPH selected          : {0}" -f [int]$q.static_pack.selected_by_section_before_prune.XGRPH)
Write-Host ("[Phase6DQ] DSOUND selected         : {0}" -f [int]$q.static_pack.selected_by_section_before_prune.DSOUND)
Write-Host ("[Phase6DQ] TEXT_HOT selected       : {0}" -f [int]$q.static_pack.selected_by_section_before_prune.TEXT_HOT)
Write-Host ("[Phase6DQ] WMADEC selected         : {0}" -f [int]$q.static_pack.selected_by_section_before_prune.WMADEC)
Write-Host ("[Phase6DQ] XPP selected            : {0}" -f [int]$q.static_pack.selected_by_section_before_prune.XPP)
Write-Host ("[Phase6DQ] XMV selected            : {0}" -f [int]$q.static_pack.selected_by_section_before_prune.XMV)
Write-Host ("[Phase6DQ] XACTENG selected        : {0}" -f [int]$q.static_pack.selected_by_section_before_prune.XACTENG)
Write-Host "[Phase6DQ] VP WRITE32 diagnostic continuation: ARMED"
Write-Host "[Phase6DQ] Unknown VP READs: HARD FENCED"
Write-Host "[Phase6DQ] IOAPIC default offsets: ZERO/NO-OP BATCH ARMED; 00/10/40 remain HARD FENCED"
Write-Host "[Phase6DQ] Detailed bounded runtime journals: ARMED"
Write-Host "[Phase6DQ] DSOUND CCCCCCCC poison-slot quarantine: ARMED at exact site 002A41F7"
Write-Host "[Phase6DQ] Pixel/present instrumentation: INHERITED"
Write-Host "[Phase6DQ] C4146 generated-code suppression: INHERITED"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DQ-ROCKET-FRONTIER-JOURNAL-20261026-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6dq-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6dq-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DQ-ROCKET-A.xex")
  }

  if(-not$FullClean){
    $buildArgs["SkipClean"]=$true
  }

  & $builder @buildArgs

  Write-Host "[Phase6DQ] BUILD PASS"
  Write-Host ("[Phase6DQ] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DQ-ROCKET-A.xex"))
  Write-Host "[Phase6DQ] Default build was incremental. Use -FullClean only if a stale-build issue is suspected."
}
