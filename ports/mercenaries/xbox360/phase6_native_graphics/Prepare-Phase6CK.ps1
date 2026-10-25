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
$out=Join-Path $root "build\phase6_native_graphics\xact_ffffffff_probe_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6ck_xact_ffffffff_probe.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CK input: $f"
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
    throw "Phase 6CK baseline missing and Phase 6CJ regeneration script not found"
  }
  Write-Host "[Phase6CK] Cached 6CJ output missing; regenerating 6CJ without solution build..."
  & $prep6cj -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CK could not regenerate 6CJ baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cj-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CJ"-or$m.build_tag-ne"P6CJ-MM166-GENERAL-TAIL-20261025-A"){
  throw "Phase 6CK baseline identity mismatch"
}
$cj=$m.phase6cj_mm166_general_tail
if($cj.translated_membership_changed-ne$false-or
   $cj.apu_gp_ep_semantics_changed-ne$false-or
   $cj.guest_irql_semantics_changed-ne$false-or
   $cj.xacteng_membership_changed-ne$false-or
   $cj.execution_budget_inherited-ne32000000){
  throw "Phase 6CK inherited 6CJ policy mismatch"
}

Write-Host "[Phase6CK] XACT FFFFFFFF COMBINED STATIC/LIVE PROBE"
Write-Host "[Phase6CK] 6CJ allocator proof : 0x2000 -> 024FA000, 0x6000 -> 024F4000"
Write-Host "[Phase6CK] 6CJ remaining fault : READ32 FFFFFFFF tick=26,711,574"
Write-Host "[Phase6CK] Final path          : 00283703 ... 00283732 -> 002832BB -> 002832CA"
Write-Host "[Phase6CK] Semantics changed  : NONE"
Write-Host "[Phase6CK] 32M watchdog       : preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){
  throw "Phase 6CK emitter syntax check failed"
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
    Tee-Object -Variable phase6ckEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CK] EMITTER OUTPUT:"
  $phase6ckEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CK emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6ck-manifest.json"
$report=Join-Path $out "phase6ck-xact-fault-source.txt"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$report,$shards)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CK output: $f"
  }
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CK"-or$r.build_tag-ne"P6CK-XACT-FFFFFFFF-PROBE-20261025-A"){
  throw "Phase 6CK manifest identity mismatch"
}
$k=$r.phase6ck_xact_ffffffff_probe
if($k.phase6cj_hardware.general_tail_calls-ne2-or
   $k.phase6cj_hardware.general_tail_successes-ne2-or
   $k.phase6cj_hardware.following_boundary.target-ne"0xFFFFFFFF"-or
   $k.phase6cj_hardware.following_boundary.ticks-ne26711574-or
   $k.semantic_repair-ne$false-or
   $k.translated_membership_changed-ne$false-or
   $k.allocator_policy_changed-ne$false-or
   $k.apu_gp_ep_semantics_changed-ne$false-or
   $k.guest_irql_semantics_changed-ne$false-or
   $k.xacteng_membership_changed-ne$false-or
   $k.execution_budget_inherited-ne32000000){
  throw "Phase 6CK hardware/probe manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CK-XACT-FFFFFFFF-PROBE-20261025-A",
  "phase6ck_env_build_cookie",
  "P6CK XACT PATH va=00283703",
  "P6CK XACT PATH va=00283732",
  "P6CK XACT PATH va=002832BB",
  "P6CK XACT PATH va=002832CA",
  "P6CK XACT PATH SUMMARY:",
  "P6CK MM166 GENERAL TAIL:",
  "P6CK APU DSP:",
  "#define PHASE4C_EXEC_BUDGET 32000000u"
)){
  if(-not$text.Contains($marker)){
    throw "Phase 6CK source gate missing: $marker"
  }
}

$reportText=Get-Content $report -Raw
foreach($marker in @(
  "loc_00283703: ;",
  "loc_00283717: ;",
  "loc_00283722: ;",
  "loc_00283732: ;",
  "loc_002832BB: ;",
  "loc_002832CA: ;"
)){
  if(-not$reportText.Contains($marker)){
    throw "Phase 6CK source report missing: $marker"
  }
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){
  throw "Phase 6CK translated shard output is empty"
}

Write-Host "[Phase6CK] READY"
Write-Host "[Phase6CK] Static source report: $report"
Write-Host "[Phase6CK] Live probe blocks   : 6"
Write-Host "[Phase6CK] Semantic repairs    : 0"
Write-Host "[Phase6CK] Allocator/APU model : inherited unchanged"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CK-XACT-FFFFFFFF-PROBE-20261025-A"
    ExpectedEnvCookie="phase6ck_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6ck-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6ck-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CK-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CK] BUILD PASS"
  Write-Host ("[Phase6CK] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CK-A.xex"))
}
