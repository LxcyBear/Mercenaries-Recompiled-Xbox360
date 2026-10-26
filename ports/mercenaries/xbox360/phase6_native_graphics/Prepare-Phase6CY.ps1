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
$base=Join-Path $root "build\phase6_native_graphics\exfreepool_itail_xdk"
$out=Join-Path $root "build\phase6_native_graphics\read32_ccccccd0_probe_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6cy_read32_ccccccd0_probe.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CY input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cx-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cx=Join-Path $PSScriptRoot "Prepare-Phase6CX.ps1"
  if(-not(Test-Path -LiteralPath $prep6cx)){
    throw "Phase 6CY baseline missing and Phase 6CX regeneration script not found"
  }
  Write-Host "[Phase6CY] Cached 6CX output missing; regenerating 6CX without solution build..."
  & $prep6cx -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CY could not regenerate 6CX baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cx-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CX"-or$m.build_tag-ne"P6CX-EXFREEPOOL-ITAIL-80000011-20261026-A"){
  throw "Phase 6CY baseline identity mismatch"
}
$cx=$m.phase6cx_exfreepool_itail
if($cx.execution_budget_inherited-ne64000000-or
   $cx.kernel_itail_ordinal24_preserved-ne$true-or
   $cx.packed_itail_dispatch_preserved-ne$true-or
   $cx.hard_fences_weakened-ne$false){
  throw "Phase 6CY inherited 6CX policy mismatch"
}

Write-Host "[Phase6CY] EXACT READ32 SOURCE-SITE PROBE"
Write-Host "[Phase6CY] 6CX hardware: ExFreePool ITAIL PASS, DSOUND continued"
Write-Host "[Phase6CY] New boundary : GUEST_FAULT READ32 CCCCCCD0"
Write-Host "[Phase6CY] Registers    : eax=CCCCCCCC caller=0023A3CE fault=1"
Write-Host "[Phase6CY] Interpretation: probable uninitialized/poisoned pointer +4 read"
Write-Host "[Phase6CY] Probe policy : tag translated READ32 sites only; do not fabricate data"
Write-Host "[Phase6CY] Preserve     : ExFreePool ITAIL / DSOUND / shadow RAM / XACT / APU / graphics"
Write-Host "[Phase6CY] Watchdog     : 64,000,000 translated blocks"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CY emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CY-R2"')){
  throw "Phase 6CY stale emitter detected; expected revision 6CY-R2"
}
Write-Host "[Phase6CY] Emitter revision       : 6CY-R2"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@("--base-dir",$base,"--base-emitter",$baseEmitter,"--phase6bl-emitter",$p6bl,"--out-dir",$out)
$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6cyEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CY] EMITTER OUTPUT:"
  $phase6cyEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CY emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cy-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CY output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CY"-or$r.build_tag-ne"P6CY-READ32-CCCCCCD0-SITE-20261026-A"){
  throw "Phase 6CY manifest identity mismatch"
}
$y=$r.phase6cy_read32_ccccccd0_probe
if($y.phase6cx_hardware.exfreepool_itail_pass-ne$true-or
   $y.phase6cx_hardware.next_boundary.kind-ne"GUEST_FAULT"-or
   $y.phase6cx_hardware.next_boundary.guest-ne"0xCCCCCCD0"-or
   $y.phase6cx_hardware.next_boundary.eax-ne"0xCCCCCCCC"-or
   $y.phase6cx_hardware.next_boundary.caller-ne"0x0023A3CE"-or
   $y.phase6cx_hardware.next_boundary.fault-ne1-or
   $y.probe_only-ne$true-or
   $y.guest_memory_semantics_changed-ne$false-or
   $y.exfreepool_itail_preserved-ne$true-or
   $y.manual_dsound_decrypt_preserved-ne$true-or
   $y.shadow_ram_alias_preserved-ne$true-or
   $y.execution_budget_inherited-ne64000000-or
   $y.hard_fences_weakened-ne$false){
  throw "Phase 6CY manifest gate failed"
}
if([int]$y.instrumented_read32_sites-lt1-or[int]$y.instrumented_functions-lt1){
  throw "Phase 6CY failed to instrument translated READ32 sites"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CY-READ32-CCCCCCD0-SITE-20261026-A",
  "phase6cy_env_build_cookie",
  "P6CY READ32 FAULT SITE:",
  "phase6cy_read32_site(phase6cy_function_va",
  "PASS: Phase 6CY ExFreePool ITAIL",
  "PASS: Phase 6CY manual DSOUND decrypt",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "P6CY APU CORE:",
  "P6CY AV/DISPLAY SUMMARY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CY source gate missing: $marker"}
}
if($text.Contains("P6AL READ32 FAULT SITE:")){
  throw "Phase 6CY stale Phase6AL READ32 probe leaked into source"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CY translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6CY] READY"
Write-Host ("[Phase6CY] Instrumented READ32 sites     : {0}" -f [int]$y.instrumented_read32_sites)
Write-Host ("[Phase6CY] Instrumented functions        : {0}" -f [int]$y.instrumented_functions)
Write-Host "[Phase6CY] Guest-memory semantics        : unchanged"
Write-Host "[Phase6CY] CCCCCCD0 value fabrication    : NO"
Write-Host "[Phase6CY] ExFreePool ITAIL              : preserved"
Write-Host "[Phase6CY] DSOUND decrypt                : preserved"
Write-Host "[Phase6CY] Shadow RAM / APU / graphics   : preserved"
Write-Host "[Phase6CY] Hardware money line           : P6CY READ32 FAULT SITE: func=... line=... address=CCCCCCD0"
Write-Host ("[Phase6CY] Generated shards              : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CY-READ32-CCCCCCD0-SITE-20261026-A"
    ExpectedEnvCookie="phase6cy_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cy-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cy-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CY-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CY] BUILD PASS"
  Write-Host ("[Phase6CY] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CY-A.xex"))
}
