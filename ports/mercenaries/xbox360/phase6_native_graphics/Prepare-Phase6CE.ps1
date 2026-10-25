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
$base=Join-Path $root "build\phase6_native_graphics\longrun32m_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xacteng_sweep_0027db5c_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6ce_xacteng_sibling_sweep.py"
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
    throw "Missing Phase 6CE input: $f"
  }
}

$baseFiles=@(
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cd-manifest.json")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cd=Join-Path $PSScriptRoot "Prepare-Phase6CD.ps1"
  if(-not(Test-Path -LiteralPath $prep6cd)){
    throw "Phase 6CE baseline missing and Phase 6CD regeneration script not found"
  }
  Write-Host "[Phase6CE] Cached 6CD output missing; regenerating 6CD without solution build..."
  & $prep6cd -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CE could not regenerate 6CD baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cd-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CD"-or$m.build_tag-ne"P6CD-LONGRUN32M-20261025-A"){
  throw "Phase 6CE baseline identity mismatch"
}
if($m.phase6cd_longrun32m.new_budget_ticks-ne32000000-or
   $m.phase6cd_longrun32m.translated_membership_changed-ne$false-or
   $m.phase6cd_longrun32m.hard_fences_changed-ne$false){
  throw "Phase 6CE inherited 6CD policy mismatch"
}

$generatedRoot=Join-Path $stage3 "runtime\gen"
$functions=Join-Path $stage3 "analysis\disasm\functions.json"
foreach($f in @($generatedRoot,$functions)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Phase 6CE generated-code analysis input missing: $f"
  }
}

Write-Host "[Phase6CE] XACTENG SIBLING SWEEP"
Write-Host "[Phase6CE] 6CD hardware frontier: 0023A3CE -> 0027DB5C"
Write-Host "[Phase6CE] 6CD reached 26,711,180 ticks with fault=0"
Write-Host "[Phase6CE] Section: XACTENG 0027D5C0-00288630"
Write-Host "[Phase6CE] Strategy: root-forward sibling saturation, then pre-frontier siblings"
Write-Host "[Phase6CE] Candidate cap: 1024 exact generated functions"
Write-Host "[Phase6CE] 32M budget and 4096-dispatch quiet logging preserved"
Write-Host "[Phase6CE] Unresolved support remains a hard stop"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){
  throw "Phase 6CE emitter syntax check failed"
}

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
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6ceEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CE] EMITTER OUTPUT:"
  $phase6ceEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CE emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6ce-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CE output: $f"
  }
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CE"-or$r.build_tag-ne"P6CE-XACTENG-SIBLING-SWEEP-0027DB5C-20261025-A"){
  throw "Phase 6CE manifest identity mismatch"
}

$a=$r.phase6ce_xacteng_sibling_sweep
if($a.phase6cd_hardware.boundary_kind-ne"DIRECT_FRONTIER"-or
   $a.phase6cd_hardware.caller-ne"0x0023A3CE"-or
   $a.phase6cd_hardware.target-ne"0x0027DB5C"-or
   $a.phase6cd_hardware.ticks-ne26711180-or
   $a.phase6cd_hardware.fault-ne0-or
   $a.phase6cd_hardware.xapi_return-ne0-or
   $a.root-ne"0x0027DB5C"-or
   $a.target_section-ne"XACTENG"-or
   $a.target_section_start-ne"0x0027D5C0"-or
   $a.target_section_end-ne"0x00288630"-or
   $a.candidate_cap-ne1024-or
   $a.packed_new_members-lt1-or
   $a.execution_budget_inherited-ne32000000-or
   $a.dispatch_log_stride_inherited-ne4096-or
   $a.hard_fences_changed-ne$false){
  throw "Phase 6CE hardware/XACTENG manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "case 0x0027DB5Cu:",
  "PASS: Phase 6CE entered XACTENG frontier 0027DB5C",
  "P6CE XACTENG ROOT:",
  "#define PHASE4C_EXEC_BUDGET 32000000u",
  "(s_phase5bcPackedIcallDispatchCount & 0xFFFu) == 0u",
  "case 0x001F9D70u: return phase6cc_pbl_sin_001f9d70;",
  "phase6ce_env_build_cookie"
)){
  if(-not$text.Contains($marker)){
    throw "Phase 6CE source gate missing: $marker"
  }
}

Write-Host "[Phase6CE] READY"
Write-Host ("[Phase6CE] Root name                : {0}" -f [string]$a.root_name)
Write-Host ("[Phase6CE] Generated XACTENG funcs : {0}" -f [int]$a.total_generated_xacteng_members)
Write-Host ("[Phase6CE] Remaining before sweep  : {0}" -f [int]$a.remaining_generated_xacteng_members)
Write-Host ("[Phase6CE] Selected candidates     : {0}" -f [int]$a.selected_candidate_members)
Write-Host ("[Phase6CE] Pruned unsafe members   : {0}" -f [int]$a.pruned_members)
Write-Host ("[Phase6CE] Packed new members      : {0}" -f [int]$a.packed_new_members)
Write-Host ("[Phase6CE] Total pack members      : {0}" -f [int]$a.expanded_pack_members)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CE-XACTENG-SIBLING-SWEEP-0027DB5C-20261025-A"
    ExpectedEnvCookie="phase6ce_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6ce-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6ce-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CE-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CE] BUILD PASS"
  Write-Host ("[Phase6CE] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CE-A.xex"))
}
