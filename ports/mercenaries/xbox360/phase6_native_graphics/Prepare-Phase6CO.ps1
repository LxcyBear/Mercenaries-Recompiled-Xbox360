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
$base=Join-Path $root "build\phase6_native_graphics\xact_object_read32_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_loop_branch_audit_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6co_xact_loop_branch_audit.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CO input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cn-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cn=Join-Path $PSScriptRoot "Prepare-Phase6CN.ps1"
  if(-not(Test-Path -LiteralPath $prep6cn)){
    throw "Phase 6CO baseline missing and Phase 6CN regeneration script not found"
  }
  Write-Host "[Phase6CO] Cached 6CN output missing; regenerating 6CN without solution build..."
  & $prep6cn -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CO could not regenerate 6CN baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cn-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CN"-or$m.build_tag-ne"P6CN-XACT-OBJECT-READ32-20261025-A"){
  throw "Phase 6CO baseline identity mismatch"
}
$cn=$m.phase6cn_xact_object_read32
if($cn.xact_esi_repair_preserved-ne$true-or
   $cn.translated_membership_changed-ne$false-or
   $cn.hard_fences_changed-ne$false-or
   $cn.execution_budget_inherited-ne32000000){
  throw "Phase 6CO inherited 6CN policy mismatch"
}

Write-Host "[Phase6CO] XACT LOOP / BRANCH AUDIT"
Write-Host "[Phase6CO] 6CN proof: ESI repair 2/2; old FFFFFFFF chain gone"
Write-Host "[Phase6CO] 6CN loop : table=0030266C pairs 2/1 -> 6/5 -> 14/13 -> 28/27"
Write-Host "[Phase6CO] 6CN field: [ESI+8]=FFFFFFFF at loop checks"
Write-Host "[Phase6CO] 6CN fault: slot28=782E6567 slot27=616D4965 -> READ32 782E657F"
Write-Host "[Phase6CO] Semantics: audit only; no branch fix yet"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CO emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CO-R1"')){
  throw "Phase 6CO stale emitter detected; expected revision 6CO-R1"
}
Write-Host "[Phase6CO] Emitter revision       : 6CO-R1"

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
    Tee-Object -Variable phase6coEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CO] EMITTER OUTPUT:"
  $phase6coEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CO emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6co-manifest.json"
$report=Join-Path $out "phase6co-xact-loop-source.txt"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$report,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CO output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CO"-or$r.build_tag-ne"P6CO-XACT-LOOP-BRANCH-AUDIT-20261025-A"){
  throw "Phase 6CO manifest identity mismatch"
}
$k=$r.phase6co_xact_loop_branch_audit
if($k.phase6cn_hardware.esi_restore_successes-ne2-or
   $k.phase6cn_hardware.field8-ne"0xFFFFFFFF"-or
   $k.phase6cn_hardware.table_base-ne"0x0030266C"-or
   $k.phase6cn_hardware.bad_slot_28_value-ne"0x782E6567"-or
   $k.phase6cn_hardware.bad_slot_27_value-ne"0x616D4965"-or
   $k.phase6cn_hardware.fault_address-ne"0x782E657F"-or
   $k.semantic_repair-ne$false-or
   $k.translated_membership_changed-ne$false-or
   $k.allocator_policy_changed-ne$false-or
   $k.apu_semantics_changed-ne$false-or
   $k.guest_irql_semantics_changed-ne$false-or
   $k.graphics_semantics_changed-ne$false-or
   $k.null_page_semantics_changed-ne$false-or
   $k.seh_terminator_semantics_changed-ne$false-or
   $k.hard_fences_changed-ne$false-or
   $k.execution_budget_inherited-ne32000000){
  throw "Phase 6CO manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CO-XACT-LOOP-BRANCH-AUDIT-20261025-A",
  "phase6co_env_build_cookie",
  "P6CO STATIC SOURCE AUDIT BEGIN",
  "P6CO SRC 00283325",
  "P6CO SRC 002832E7",
  "P6CO SRC 002832F2",
  "P6CO SRC 00282BC2",
  "P6CO LOOP va=002832F2",
  "P6CO LOOP AUDIT:",
  "PASS: Phase 6CO restored XACT ESI at 002832CA",
  "#define PHASE4C_EXEC_BUDGET 32000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CO source gate missing: $marker"}
}

$reportText=Get-Content $report -Raw
foreach($marker in @(
  "loc_00283325: ;",
  "loc_002832E7: ;",
  "loc_002832F2: ;",
  "loc_00282BC2: ;"
)){
  if(-not$reportText.Contains($marker)){throw "Phase 6CO source report missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CO translated shard output is empty"}

Write-Host "[Phase6CO] READY"
Write-Host "[Phase6CO] Source report : $report"
Write-Host "[Phase6CO] Live probes   : 00283325 / 002832E7 / 002832F2 / 00282BC2"
Write-Host "[Phase6CO] Branch repair : NONE"
Write-Host "[Phase6CO] 32M watchdog : preserved"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CO-XACT-LOOP-BRANCH-AUDIT-20261025-A"
    ExpectedEnvCookie="phase6co_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6co-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6co-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CO-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CO] BUILD PASS"
  Write-Host ("[Phase6CO] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CO-A.xex"))
}
