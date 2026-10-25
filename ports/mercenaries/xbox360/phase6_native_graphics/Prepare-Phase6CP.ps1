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
$base=Join-Path $root "build\phase6_native_graphics\xact_loop_branch_audit_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_field8_sentinel_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cp_xact_field8_sentinel.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CP input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6co-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6co=Join-Path $PSScriptRoot "Prepare-Phase6CO.ps1"
  if(-not(Test-Path -LiteralPath $prep6co)){
    throw "Phase 6CP baseline missing and Phase 6CO regeneration script not found"
  }
  Write-Host "[Phase6CP] Cached 6CO output missing; regenerating 6CO without solution build..."
  & $prep6co -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CP could not regenerate 6CO baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6co-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CO"-or$m.build_tag-ne"P6CO-XACT-LOOP-BRANCH-AUDIT-20261025-A"){
  throw "Phase 6CP baseline identity mismatch"
}
$co=$m.phase6co_xact_loop_branch_audit
if($co.semantic_repair-ne$false-or
   $co.translated_membership_changed-ne$false-or
   $co.hard_fences_changed-ne$false-or
   $co.execution_budget_inherited-ne32000000){
  throw "Phase 6CP inherited 6CO policy mismatch"
}

Write-Host "[Phase6CP] BATCHED XACT FIELD+8 REPAIR"
Write-Host "[Phase6CP] 6CO proof: decoded unsigned jb/jae are intact"
Write-Host "[Phase6CP] 6CO proof: XACT+8 changes 00000000 -> FFFFFFFF"
Write-Host "[Phase6CP] 6CO proof: FFFFFFFF drives 2/1 -> 6/5 -> 14/13 -> 28/27"
Write-Host "[Phase6CP] 6CO proof: slot 28/27 are string bytes, then READ32 782E657F faults"
Write-Host "[Phase6CP] Batch A: record exact global WRITE32 writer to live XACT root+8"
Write-Host "[Phase6CP] Batch B: exact root/table/sentinel no-walk exit at 002832E0"
Write-Host "[Phase6CP] Goal: move directly to the next real frontier in the same 32M run"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CP emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CP-R2"')){
  throw "Phase 6CP stale emitter detected; expected revision 6CP-R2"
}
Write-Host "[Phase6CP] Emitter revision       : 6CP-R2"

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
    Tee-Object -Variable phase6cpEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CP] EMITTER OUTPUT:"
  $phase6cpEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CP emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cp-manifest.json"
$report=Join-Path $out "phase6cp-xact-loop-source.txt"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$report,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CP output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CP"-or$r.build_tag-ne"P6CP-XACT-FIELD8-SENTINEL-20261025-A"){
  throw "Phase 6CP manifest identity mismatch"
}
$k=$r.phase6cp_xact_field8_sentinel
if($k.phase6co_hardware.field8_visit1-ne"0x00000000"-or
   $k.phase6co_hardware.field8_visit2-ne"0xFFFFFFFF"-or
   $k.phase6co_hardware.table-ne"0x0030266C"-or
   $k.phase6co_hardware.fault_address-ne"0x782E657F"-or
   $k.phase6co_hardware.esi_restore_successes-ne2-or
   $k.sentinel_entry_va-ne"0x002832E0"-or
   $k.sentinel_exit_va-ne"0x00283334"-or
   $k.sentinel_table-ne"0x0030266C"-or
   $k.sentinel_value-ne"0xFFFFFFFF"-or
   $k.translated_membership_changed-ne$false-or
   $k.allocator_policy_changed-ne$false-or
   $k.apu_semantics_changed-ne$false-or
   $k.guest_irql_semantics_changed-ne$false-or
   $k.graphics_semantics_changed-ne$false-or
   $k.null_page_semantics_changed-ne$false-or
   $k.seh_terminator_semantics_changed-ne$false-or
   $k.hard_fences_changed-ne$false-or
   $k.execution_budget_inherited-ne32000000){
  throw "Phase 6CP manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CP-XACT-FIELD8-SENTINEL-20261025-A",
  "phase6cp_env_build_cookie",
  "P6CP XACT FIELD8 WRITE",
  "PASS: Phase 6CP XACT field8 sentinel exit",
  "P6CP XACT FIELD8:",
  "PASS: Phase 6CP restored XACT ESI at 002832CA",
  "phase6cp_inherited_guest_write32",
  "s_phase6cpCurrentVa = va;",
  "#define PHASE4C_EXEC_BUDGET 32000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CP source gate missing: $marker"}
}

$reportText=Get-Content $report -Raw
foreach($marker in @(
  "loc_002832CA: ;",
  "loc_002832E0: ;",
  "loc_002832E7: ;",
  "loc_002832F2: ;",
  "loc_00283325: ;",
  "loc_00283334: ;"
)){
  if(-not$reportText.Contains($marker)){throw "Phase 6CP source report missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CP translated shard output is empty"}

Write-Host "[Phase6CP] READY"
Write-Host "[Phase6CP] Writer provenance : GLOBAL exact live XACT root+8"
Write-Host "[Phase6CP] Sentinel repair   : 002832E0 -> 00283334 only for root/table/FFFFFFFF proof"
Write-Host "[Phase6CP] 6CM ESI repair   : preserved"
Write-Host "[Phase6CP] 32M watchdog     : preserved"
Write-Host "[Phase6CP] Source report    : $report"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CP-XACT-FIELD8-SENTINEL-20261025-A"
    ExpectedEnvCookie="phase6cp_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cp-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cp-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CP-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CP] BUILD PASS"
  Write-Host ("[Phase6CP] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CP-A.xex"))
}
