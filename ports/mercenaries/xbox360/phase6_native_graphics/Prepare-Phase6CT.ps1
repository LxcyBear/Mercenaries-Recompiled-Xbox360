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
$base=Join-Path $root "build\phase6_native_graphics\pixel_chase_0027e780_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_async_read_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6ct_xact_async_read.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CT input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cs-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cs=Join-Path $PSScriptRoot "Prepare-Phase6CS.ps1"
  if(-not(Test-Path -LiteralPath $prep6cs)){
    throw "Phase 6CT baseline missing and Phase 6CS regeneration script not found"
  }
  Write-Host "[Phase6CT] Cached 6CS output missing; regenerating 6CS without solution build..."
  & $prep6cs -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CT could not regenerate 6CS baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cs-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CS"-or$m.build_tag-ne"P6CS-PIXEL-CHASE-0027E780-20261025-A"){
  throw "Phase 6CT baseline identity mismatch"
}
$cs=$m.phase6cs_pixel_chase
if($cs.execution_budget_inherited-ne64000000-or
   $cs.xact_continuity_repair_preserved-ne$true-or
   $cs.xact_sentinel_repair_preserved-ne$true-or
   $cs.hard_fences_changed-ne$false){
  throw "Phase 6CT inherited 6CS policy mismatch"
}

Write-Host "[Phase6CT] XACT ASYNC STREAM READ CONTINUATION"
Write-Host "[Phase6CT] 6CS crossed XACT stream root 0027E780"
Write-Host "[Phase6CT] Hardware read: shl_streams.xwb len=2048 offset=0"
Write-Host "[Phase6CT] Frame: event=0 apc=0 context=01B5D648 iosb=01B5D648"
Write-Host "[Phase6CT] 6CS stopped only on blanket async NtReadFile fence"
Write-Host "[Phase6CT] Policy: immediate host completion; final IOSB; STATUS_PENDING for async handles"
Write-Host "[Phase6CT] Event/APC callback forms remain fenced"
Write-Host "[Phase6CT] 64M watchdog and 6CS translated pack preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CT emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CT-R3"')){
  throw "Phase 6CT stale emitter detected; expected revision 6CT-R3"
}
Write-Host "[Phase6CT] Emitter revision       : 6CT-R3"

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
    Tee-Object -Variable phase6ctEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CT] EMITTER OUTPUT:"
  $phase6ctEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CT emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6ct-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CT output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CT"-or$r.build_tag-ne"P6CT-XACT-ASYNC-READ-20261025-A"){
  throw "Phase 6CT manifest identity mismatch"
}
$k=$r.phase6ct_xact_async_read
if($k.phase6cs_hardware.boundary_kind-ne"STORAGE_IO"-or
   $k.phase6cs_hardware.caller-ne"0x0023A3CE"-or
   $k.phase6cs_hardware.target-ne"0x800000DB"-or
   $k.phase6cs_hardware.fault-ne0-or
   $k.phase6cs_hardware.length-ne2048-or
   $k.execution_budget_inherited-ne64000000-or
   $k.translated_pack_changed-ne$false-or
   $k.graphics_bridge_semantics_changed-ne$false-or
   $k.null_page_semantics_changed-ne$false-or
   $k.seh_terminator_semantics_changed-ne$false-or
   $k.hard_fences_weakened-ne$false){
  throw "Phase 6CT manifest gate failed"
}
if($k.policy.immediate_host_completion-ne$true-or
   $k.policy.async_guest_return-ne"STATUS_PENDING"-or
   $k.policy.event_forms_fenced-ne$true-or
   $k.policy.apc_callback_forms_fenced-ne$true-or
   $k.policy.apc_context_without_callback_allowed-ne$true){
  throw "Phase 6CT async-read policy gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CT-XACT-ASYNC-READ-20261025-A",
  "phase6ct_env_build_cookie",
  "P6CT ASYNC STREAM READ:",
  "PASS: Phase 6CT XACT async NtReadFile immediate completion",
  "s_phase6ctHandleCreateOptions",
  "phase6ct_record_handle_options(token, options);",
  "0x00000103u; /* STATUS_PENDING */",
  "STORAGE IO UNSUPPORTED: NtReadFile Event/APC callback form",
  "case 0x0027E780u:",
  "P6CT PIXEL CHASE:",
  "P6CT PRESENT PROXIMITY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CT source gate missing: $marker"}
}
if($text.Contains("STORAGE IO UNSUPPORTED: asynchronous NtReadFile event/APC form")){
  throw "Phase 6CT old blanket async read fence still present"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CT translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6CT] READY"
Write-Host "[Phase6CT] XACT stream request     : immediate-completion async bridge armed"
Write-Host "[Phase6CT] Handle create options  : tracked"
Write-Host "[Phase6CT] Guest async return     : STATUS_PENDING"
Write-Host "[Phase6CT] Final IOSB             : completion status + bytes"
Write-Host "[Phase6CT] Event/APC callbacks    : still hard-fenced"
Write-Host ("[Phase6CT] Generated shards       : {0}" -f $shardCount)
Write-Host "[Phase6CT] Pixel/display telemetry: preserved"
Write-Host "[Phase6CT] 64M watchdog          : preserved"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CT-XACT-ASYNC-READ-20261025-A"
    ExpectedEnvCookie="phase6ct_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6ct-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6ct-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CT-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CT] BUILD PASS"
  Write-Host ("[Phase6CT] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CT-A.xex"))
}
