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
$base=Join-Path $root "build\phase6_native_graphics\xact_mm166_subpage_repair_xdk"
$out=Join-Path $root "build\phase6_native_graphics\mm166_alignment_gap_repair_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6do_mm166_alignment_gap_repair.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DO input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6dn-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6dn=Join-Path $PSScriptRoot "Prepare-Phase6DN.ps1"
  if(-not(Test-Path -LiteralPath $prep6dn)){
    throw "Phase 6DO baseline missing and Phase 6DN regeneration script not found"
  }

  Write-Host "[Phase6DO] Cached 6DN output missing; regenerating 6DN without solution build..."
  & $prep6dn -SkipSolutionBuild

  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DO could not regenerate 6DN baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6dn-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DN"-or$m.build_tag-ne"P6DN-XACT-MM166-SUBPAGE-REPAIR-20261026-A"){
  throw "Phase 6DO baseline identity mismatch"
}

Write-Host "[Phase6DO] MM166 ALIGNMENT-GAP REPAIR"
Write-Host "[Phase6DO] 6DN proved size=4 align=4096 now succeeds at 024F3000"
Write-Host "[Phase6DO] New blocker: size=32768 align=32768 returns NULL"
Write-Host "[Phase6DO] Expected base=024E8000 end=024F0000 pad=12288 old_page_next=024F3000"
Write-Host "[Phase6DO] Repair: consume safe alignment padding from free tail"
Write-Host "[Phase6DO] Guest allocation size remains 32768"
Write-Host "[Phase6DO] Heap-overlap/page-state/reservation fences: UNCHANGED"
Write-Host "[Phase6DO] XACT teardown semantics: UNCHANGED"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DO emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DO-R2"')){
  throw "Phase 6DO stale emitter detected; expected revision 6DO-R2"
}
Write-Host "[Phase6DO] Emitter revision       : 6DO-R2"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",$baseEmitter,
  "--phase6bl-emitter",$p6bl,
  "--out-dir",$out
)

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6doEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DO] EMITTER OUTPUT:"
  $phase6doEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DO emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6do-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DO output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DO"-or$r.build_tag-ne"P6DO-MM166-ALIGNMENT-GAP-REPAIR-20261026-A"){
  throw "Phase 6DO manifest identity mismatch"
}

$do=$r.phase6do_mm166_alignment_gap_repair
if($do.hardware_proof.prior_subpage_request_succeeded-ne$true-or
   $do.hardware_proof.next_failed_request_size-ne32768-or
   $do.hardware_proof.next_failed_alignment-ne32768-or
   $do.hardware_proof.alignment_padding-ne12288-or
   $do.repair.exact_end_requirement_removed-ne$true-or
   $do.repair.allocation_end_must_not_exceed_old_frontier-ne$true-or
   $do.repair.alignment_padding_must_be_less_than_alignment-ne$true-or
   $do.repair.alignment_padding_consumed_from_free_tail-ne$true-or
   $do.repair.alignment_padding_reported_to_guest-ne$false-or
   $do.repair.guest_allocation_size_unchanged-ne$true-or
   $do.repair.tail_heap_overlap_checks_unchanged-ne$true-or
   $do.repair.unmanaged_page_checks_unchanged-ne$true-or
   $do.xact_refcount_semantics_changed-ne$false-or
   $do.destructor_suppressed-ne$false-or
   $do.free_suppressed-ne$false-or
   $do.guest_memory_fences_changed-ne$false-or
   $do.generated_c4146_scope_inherited-ne$true-or
   $do.execution_budget_inherited-ne64000000){
  throw "Phase 6DO manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DO-MM166-ALIGNMENT-GAP-REPAIR-20261026-A",
  "phase6do_env_build_cookie",
  "uint32_t alignmentPad = 0u;",
  "base + size > oldPageNext",
  "alignmentPad = oldPageNext - (base + size);",
  "if (alignmentPad >= alignment)",
  "PASS: Phase 6DO aligned tail claim",
  "alignment_pad=%u",
  "PASS: Phase 6DO canonical subpage Mm166 tail claim",
  "P6DO XACT RELEASE PRETRACE:",
  "#pragma warning(disable:4146)",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DO source gate missing: $marker"}
}

if($text.Contains("base + size != oldPageNext")){
  throw "Phase 6DO stale exact-end restriction remains"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DO translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DO] READY"
Write-Host "[Phase6DO] Expected money line:"
Write-Host "[Phase6DO]   PASS: Phase 6DO aligned tail claim ... requested=32768 rounded=32768 align=32768 alignment_pad=12288 ..."
Write-Host "[Phase6DO] Then we want 0027F3DC to stop returning 8007000E."
Write-Host "[Phase6DO] C4146 cleanup           : inherited"
Write-Host "[Phase6DO] XACT teardown suppression: NONE"
Write-Host ("[Phase6DO] Generated shards        : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DO-MM166-ALIGNMENT-GAP-REPAIR-20261026-A"
    ExpectedEnvCookie="phase6do_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6do-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6do-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DO-A.xex")
  }

  & $builder @buildArgs
  Write-Host "[Phase6DO] BUILD PASS"
  Write-Host ("[Phase6DO] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DO-A.xex"))
}
