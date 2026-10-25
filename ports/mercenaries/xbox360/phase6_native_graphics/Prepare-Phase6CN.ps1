[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p4=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\xact_esi_continuity_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_object_read32_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cn_xact_object_read32.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CN input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cm-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cm=Join-Path $PSScriptRoot "Prepare-Phase6CM.ps1"
  if(-not(Test-Path -LiteralPath $prep6cm)){
    throw "Phase 6CN baseline missing and Phase 6CM regeneration script not found"
  }
  Write-Host "[Phase6CN] Cached 6CM output missing; regenerating 6CM without solution build..."
  & $prep6cm -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CN could not regenerate 6CM baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cm-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CM"-or$m.build_tag-ne"P6CM-XACT-ESI-CONTINUITY-20261025-A"){
  throw "Phase 6CN baseline identity mismatch"
}
$cm=$m.phase6cm_xact_esi_continuity
$guard=$cm.guard
if($cm.translated_membership_changed-ne$false-or
   $cm.hard_fences_changed-ne$false-or
   $cm.execution_budget_inherited-ne32000000-or
   $guard.current_esi_must_be_zero-ne$true-or
   $guard.captured_esi_must_equal_live_xact_root-ne$true-or
   $guard.null_page_semantics_changed-ne$false-or
   $guard.seh_terminator_semantics_changed-ne$false){
  throw "Phase 6CN inherited 6CM policy mismatch"
}

Write-Host "[Phase6CN] XACT DOWNSTREAM OBJECT READ32 TRACE"
Write-Host "[Phase6CN] 6CM hardware: ESI repair fired 2/2 and removed FFFFFFFF chain"
Write-Host "[Phase6CN] New fault: EAX=782E6567 -> READ32(EAX+18)=782E657F"
Write-Host "[Phase6CN] Trace window: current translated VA 00282B00-002833FF"
Write-Host "[Phase6CN] Existing 6CM repair and every hard fence stay armed"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CN emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CN-R5"')){
  throw "Phase 6CN stale emitter detected; expected revision 6CN-R5"
}
Write-Host "[Phase6CN] Emitter revision       : 6CN-R5"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",$baseEmitter,
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 |
    Tee-Object -Variable phase6cnEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CN] EMITTER OUTPUT:"
  $phase6cnEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CN emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cn-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CN output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CN"-or$r.build_tag-ne"P6CN-XACT-OBJECT-READ32-20261025-A"){
  throw "Phase 6CN manifest identity mismatch"
}
$k=$r.phase6cn_xact_object_read32
if($k.phase6cm_hardware.esi_restore_successes-ne2-or
   $k.phase6cm_hardware.captured_esi-ne"0x01B5C320"-or
   $k.phase6cm_hardware.new_fault_address-ne"0x782E657F"-or
   $k.phase6cm_hardware.new_fault_eax-ne"0x782E6567"-or
   $k.trace_window_start-ne"0x00282B00"-or
   $k.trace_window_end_exclusive-ne"0x00283400"-or
   $k.current_va_stamped_by_budget_tick-ne$true-or
   $k.xact_esi_repair_preserved-ne$true-or
   $k.translated_membership_changed-ne$false-or
   $k.allocator_policy_changed-ne$false-or
   $k.apu_gp_ep_semantics_changed-ne$false-or
   $k.guest_irql_semantics_changed-ne$false-or
   $k.graphics_semantics_changed-ne$false-or
   $k.null_page_semantics_changed-ne$false-or
   $k.seh_terminator_semantics_changed-ne$false-or
   $k.hard_fences_changed-ne$false-or
   $k.execution_budget_inherited-ne32000000){
  throw "Phase 6CN manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CN-XACT-OBJECT-READ32-20261025-A",
  "phase6cn_env_build_cookie",
  "s_phase6cnCurrentVa = va;",
  "P6CN XACT READ32 TRACE ARMED",
  "P6CN XACT READ32 PRE",
  "P6CN XACT READ32 POST",
  "P6CN XACT READ32 FAULT",
  "P6CN XACT READ32:",
  "PASS: Phase 6CN restored XACT ESI at 002832CA",
  "#define PHASE4C_EXEC_BUDGET 32000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CN source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CN translated shard output is empty"}

Write-Host "[Phase6CN] READY"
Write-Host "[Phase6CN] ESI continuity repair : preserved"
Write-Host "[Phase6CN] Trace arm             : 002832CA"
Write-Host "[Phase6CN] Trace window          : 00282B00-002833FF"
Write-Host "[Phase6CN] Current VA source     : phase4c_budget_tick"
Write-Host "[Phase6CN] Null/SEH fences       : unchanged"
Write-Host "[Phase6CN] 32M watchdog          : unchanged"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CN-XACT-OBJECT-READ32-20261025-A"
    ExpectedEnvCookie="phase6cn_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cn-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cn-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CN-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CN] BUILD PASS"
  Write-Host ("[Phase6CN] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CN-A.xex"))
}
