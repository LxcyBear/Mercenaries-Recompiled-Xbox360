[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\dsound_sweep_002a6713_xdk"
$out=Join-Path $root "build\phase6_native_graphics\exfreepool_itail_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6cx_exfreepool_itail.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CX input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cw-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cw=Join-Path $PSScriptRoot "Prepare-Phase6CW.ps1"
  if(-not(Test-Path -LiteralPath $prep6cw)){
    throw "Phase 6CX baseline missing and Phase 6CW regeneration script not found"
  }
  Write-Host "[Phase6CX] Cached 6CW output missing; regenerating 6CW without solution build..."
  & $prep6cw -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CX could not regenerate 6CW baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cw-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CW"-or$m.build_tag-ne"P6CW-DSOUND-SWEEP-002A6713-20261026-A"){
  throw "Phase 6CX baseline identity mismatch"
}
$cw=$m.phase6cw_dsound_sweep
if($cw.root-ne"0x002A6713"-or
   $cw.manual_root_dispatch-ne$true-or
   $cw.shadow_ram_alias_preserved-ne$true-or
   $cw.execution_budget_inherited-ne64000000-or
   $cw.hard_fences_weakened-ne$false){
  throw "Phase 6CX inherited 6CW policy mismatch"
}

Write-Host "[Phase6CX] POST-DSOUND EXFREEPOOL ITAIL CONTINUATION"
Write-Host "[Phase6CX] 6CW hardware: manual dsstdfx decrypt executed; old 002A6713 frontier crossed"
Write-Host "[Phase6CX] New boundary : ITAIL 0023A3CE -> 80000011, fault=0"
Write-Host "[Phase6CX] Kernel export: ordinal 17 ExFreePool"
Write-Host "[Phase6CX] Tail ABI     : [esp]=dummy return, [esp+4]=pool address, consume 8 bytes"
Write-Host "[Phase6CX] Reuse        : maintained Phase6CF guest-heap ExFreePool semantics"
Write-Host "[Phase6CX] Preserve     : shadow RAM / XACT async / APU / D3D-XGRPH / AV telemetry"
Write-Host "[Phase6CX] Goal         : run beyond DSOUND cleanup toward audible/playback or display handoff"
Write-Host "[Phase6CX] Watchdog     : 64,000,000 translated blocks"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CX emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CX-R1"')){
  throw "Phase 6CX stale emitter detected; expected revision 6CX-R1"
}
Write-Host "[Phase6CX] Emitter revision       : 6CX-R1"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter "--base-dir" $base "--out-dir" $out 2>&1 |
    Tee-Object -Variable phase6cxEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CX] EMITTER OUTPUT:"
  $phase6cxEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CX emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cx-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CX output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CX"-or$r.build_tag-ne"P6CX-EXFREEPOOL-ITAIL-80000011-20261026-A"){
  throw "Phase 6CX manifest identity mismatch"
}
$x=$r.phase6cx_exfreepool_itail
if($x.phase6cw_hardware.boundary_kind-ne"ITAIL"-or
   $x.phase6cw_hardware.caller-ne"0x0023A3CE"-or
   $x.phase6cw_hardware.target-ne"0x80000011"-or
   $x.phase6cw_hardware.ordinal-ne17-or
   $x.phase6cw_hardware.fault-ne0-or
   $x.phase6cw_hardware.dsound_manual_decrypt_entered-ne$true-or
   $x.tail_frame.total_consumed_bytes-ne8-or
   $x.execution_budget_inherited-ne64000000-or
   $x.kernel_itail_ordinal24_preserved-ne$true-or
   $x.packed_itail_dispatch_preserved-ne$true-or
   $x.hard_fences_weakened-ne$false){
  throw "Phase 6CX manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CX-EXFREEPOOL-ITAIL-80000011-20261026-A",
  "phase6cx_env_build_cookie",
  "phase6cx_ex_free_pool_itail();",
  "PASS: Phase 6CX ExFreePool ITAIL",
  "P6CX EXFREEPOOL ITAIL:",
  "static void phase6cf_ex_free_pool(uint32_t savedEsp)",
  "PASS: Phase 6CX manual DSOUND decrypt",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "P6CX APU CORE:",
  "P6CX AV/DISPLAY SUMMARY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CX source gate missing: $marker"}
}

$itailStart=$text.IndexOf("#define RECOMP_ITAIL(xbox_va)")
$itailEnd=$text.IndexOf("#define RECOMP_ITAIL_SAFE",$itailStart)
if($itailStart-lt0-or$itailEnd-lt0){throw "Phase 6CX ITAIL macro range missing"}
$itail=$text.Substring($itailStart,$itailEnd-$itailStart)
if(([regex]::Matches($itail,[regex]::Escape("0x80000011u"))).Count-ne1){
  throw "Phase 6CX ExFreePool ITAIL branch count mismatch"
}
if(-not$itail.Contains("0x80000018u")-or
   -not$itail.Contains("phase4c_ex_query_nonvolatile_setting")-or
   -not$itail.Contains("phase6cq_dispatch_packed_itail")){
  throw "Phase 6CX inherited ITAIL policy was weakened"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CX translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6CX] READY"
Write-Host "[Phase6CX] Kernel tail                  : ordinal 17 ExFreePool"
Write-Host "[Phase6CX] Tail frame bytes             : 8"
Write-Host "[Phase6CX] DSOUND decrypt               : preserved"
Write-Host "[Phase6CX] Shadow RAM F0000000-F3FFFFFF : preserved"
Write-Host "[Phase6CX] APU core/DSP                  : preserved"
Write-Host "[Phase6CX] D3D/XGRPH/Xenos              : preserved"
Write-Host "[Phase6CX] AV/display telemetry          : preserved"
Write-Host "[Phase6CX] 64M watchdog                 : preserved"
Write-Host ("[Phase6CX] Generated shards             : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CX-EXFREEPOOL-ITAIL-80000011-20261026-A"
    ExpectedEnvCookie="phase6cx_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cx-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cx-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CX-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CX] BUILD PASS"
  Write-Host ("[Phase6CX] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CX-A.xex"))
}
