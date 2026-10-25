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
$base=Join-Path $root "build\phase6_native_graphics\mm166_general_tail_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_read32_chain_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cl_xact_read32_chain.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CL input: $f"
  }
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cj-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cj=Join-Path $PSScriptRoot "Prepare-Phase6CJ.ps1"
  if(-not(Test-Path -LiteralPath $prep6cj)){
    throw "Phase 6CL baseline missing and Phase 6CJ regeneration script not found"
  }
  Write-Host "[Phase6CL] Cached 6CJ output missing; regenerating 6CJ without solution build..."
  & $prep6cj -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CL could not regenerate 6CJ baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cj-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CJ"-or$m.build_tag-ne"P6CJ-MM166-GENERAL-TAIL-20261025-A"){
  throw "Phase 6CL baseline identity mismatch"
}
$cj=$m.phase6cj_mm166_general_tail
if($cj.translated_membership_changed-ne$false-or
   $cj.apu_gp_ep_semantics_changed-ne$false-or
   $cj.guest_irql_semantics_changed-ne$false-or
   $cj.xacteng_membership_changed-ne$false-or
   $cj.execution_budget_inherited-ne32000000){
  throw "Phase 6CL inherited 6CJ policy mismatch"
}

Write-Host "[Phase6CL] XACT READ32 CHAIN PROBE"
Write-Host "[Phase6CL] 6CK proof : ECX enters 002832CA as 00000000"
Write-Host "[Phase6CL] Fault     : next boundary READ32 FFFFFFFF, ECX=FFFFFFFF"
Write-Host "[Phase6CL] Strategy  : arm at 002832CA; trace every central READ32 until boundary"
Write-Host "[Phase6CL] Semantics : unchanged"
Write-Host "[Phase6CL] Watchdog  : 32M preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){
  throw "Phase 6CL emitter syntax check failed"
}

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
    Tee-Object -Variable phase6clEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CL] EMITTER OUTPUT:"
  $phase6clEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CL emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cl-manifest.json"
$report=Join-Path $out "phase6cl-002832ca-source.txt"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$report,$shards)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CL output: $f"
  }
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CL"-or$r.build_tag-ne"P6CL-XACT-READ32-CHAIN-20261025-A"){
  throw "Phase 6CL manifest identity mismatch"
}
$k=$r.phase6cl_xact_read32_chain
if($k.phase6ck_hardware_provenance.arm_entry-ne"0x002832CA"-or
   $k.phase6ck_hardware_provenance.entry_ecx-ne"0x00000000"-or
   $k.phase6ck_hardware_provenance.following_fault_target-ne"0xFFFFFFFF"-or
   $k.read32_trace_cap-ne32-or
   $k.semantic_repair-ne$false-or
   $k.translated_membership_changed-ne$false-or
   $k.allocator_policy_changed-ne$false-or
   $k.apu_gp_ep_semantics_changed-ne$false-or
   $k.guest_irql_semantics_changed-ne$false-or
   $k.xacteng_membership_changed-ne$false-or
   $k.execution_budget_inherited-ne32000000){
  throw "Phase 6CL hardware/probe manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CL-XACT-READ32-CHAIN-20261025-A",
  "phase6cl_env_build_cookie",
  "P6CL READ32 TRACE ARMED va=002832CA",
  "P6CL READ32 PRE",
  "P6CL READ32 POST",
  "P6CL READ32 INVALID",
  "P6CL READ32 CHAIN:",
  "P6CL MM166 GENERAL TAIL:",
  "P6CL APU DSP:",
  "#define PHASE4C_EXEC_BUDGET 32000000u"
)){
  if(-not$text.Contains($marker)){
    throw "Phase 6CL source gate missing: $marker"
  }
}

$reportText=Get-Content $report -Raw
if(-not$reportText.Contains("loc_002832CA: ;")){
  throw "Phase 6CL source report lost 002832CA label"
}
if($reportText.Length-lt20){
  throw "Phase 6CL source report unexpectedly short"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){
  throw "Phase 6CL translated shard output is empty"
}

Write-Host "[Phase6CL] READY"
Write-Host "[Phase6CL] Source block report: $report"
Write-Host "[Phase6CL] READ32 trace cap    : 32"
Write-Host "[Phase6CL] Semantic repairs    : 0"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CL-XACT-READ32-CHAIN-20261025-A"
    ExpectedEnvCookie="phase6cl_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cl-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cl-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CL-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CL] BUILD PASS"
  Write-Host ("[Phase6CL] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CL-A.xex"))
}
