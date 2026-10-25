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
$base=Join-Path $root "build\phase6_native_graphics\xact_async_read_xdk"
$out=Join-Path $root "build\phase6_native_graphics\post_async_getlasterror_0022b150_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cu_post_async_0022b150.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CU input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6ct-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6ct=Join-Path $PSScriptRoot "Prepare-Phase6CT.ps1"
  if(-not(Test-Path -LiteralPath $prep6ct)){
    throw "Phase 6CU baseline missing and Phase 6CT regeneration script not found"
  }
  Write-Host "[Phase6CU] Cached 6CT output missing; regenerating 6CT without solution build..."
  & $prep6ct -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CU could not regenerate 6CT baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6ct-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CT"-or$m.build_tag-ne"P6CT-XACT-ASYNC-READ-20261025-A"){
  throw "Phase 6CU baseline identity mismatch"
}
$ct=$m.phase6ct_xact_async_read
if($ct.execution_budget_inherited-ne64000000-or
   $ct.translated_pack_changed-ne$false-or
   $ct.graphics_bridge_semantics_changed-ne$false-or
   $ct.hard_fences_weakened-ne$false-or
   $ct.policy.immediate_host_completion-ne$true-or
   $ct.policy.async_guest_return-ne"STATUS_PENDING"-or
   $ct.policy.apc_context_without_callback_allowed-ne$true){
  throw "Phase 6CU inherited 6CT policy mismatch"
}

Write-Host "[Phase6CU] POST-ASYNC CONTINUATION -> DISPLAY"
Write-Host "[Phase6CU] 6CT hardware: async shl_streams.xwb read PASS, 2048 bytes"
Write-Host "[Phase6CU] 6CT guest return: STATUS_PENDING -> ERROR_IO_PENDING (997)"
Write-Host "[Phase6CU] New clean frontier: DIRECT 0023A3CE -> 0022B150"
Write-Host "[Phase6CU] Target identity: maintained support-owned GetLastError"
Write-Host "[Phase6CU] Strategy: expose canonical 0022B150 through packed direct dispatch"
Write-Host "[Phase6CU] No duplicate translated GetLastError body"
Write-Host "[Phase6CU] Preserve 6CT XACT async + Partition0 + graphics semantics"
Write-Host "[Phase6CU] Watchdog: preserve 64,000,000 translated blocks"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CU emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CU-R2"')){
  throw "Phase 6CU stale emitter detected; expected revision 6CU-R2"
}
Write-Host "[Phase6CU] Emitter revision       : 6CU-R2"

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
    Tee-Object -Variable phase6cuEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CU] EMITTER OUTPUT:"
  $phase6cuEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CU emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cu-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CU output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CU"-or$r.build_tag-ne"P6CU-POST-ASYNC-GETLASTERROR-0022B150-20261025-A"){
  throw "Phase 6CU manifest identity mismatch"
}
$k=$r.phase6cu_post_async_get_last_error
if($k.phase6ct_hardware.boundary_kind-ne"DIRECT_FRONTIER"-or
   $k.phase6ct_hardware.caller-ne"0x0023A3CE"-or
   $k.phase6ct_hardware.target-ne"0x0022B150"-or
   $k.phase6ct_hardware.fault-ne0-or
   $k.phase6ct_hardware.async_read_calls-ne1-or
   $k.phase6ct_hardware.async_read_successes-ne1-or
   $k.phase6ct_hardware.async_pending_returns-ne1-or
   $k.phase6ct_hardware.async_bytes-ne2048-or
   $k.phase6ct_hardware.d3d_device_calls-ne1-or
   $k.target-ne"0x0022B150"-or
   $k.execution_budget_inherited-ne64000000-or
   $k.translated_pack_changed-ne$false-or
   $k.async_read_semantics_changed-ne$false-or
   $k.partition0_semantics_changed-ne$false-or
   $k.graphics_bridge_semantics_changed-ne$false-or
   $k.hard_fences_weakened-ne$false){
  throw "Phase 6CU manifest gate failed"
}
if($k.dispatch_policy.canonical_support_helper_reused-ne$true-or
   $k.dispatch_policy.duplicate_translated_body_emitted-ne$false-or
   $k.dispatch_policy.phase4c_lookup_pack_func_extended-ne$true){
  throw "Phase 6CU GetLastError dispatch policy gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CU-POST-ASYNC-GETLASTERROR-0022B150-20261025-A",
  "phase6cu_env_build_cookie",
  "case 0x0022B150u: return sub_0022B150;",
  "PASS: Phase 6CU maintained GetLastError",
  "P6CU GETLASTERROR:",
  "P6CU ASYNC STREAM READ:",
  "PASS: Phase 6CU XACT async NtReadFile immediate completion",
  "partition0Config",
  "P6CU PIXEL CHASE:",
  "P6CU PRESENT PROXIMITY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CU source gate missing: $marker"}
}
if(([regex]::Matches($text,[regex]::Escape("case 0x0022B150u: return sub_0022B150;"))).Count-ne1){
  throw "Phase 6CU GetLastError lookup dispatch count mismatch"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CU translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6CU] READY"
Write-Host "[Phase6CU] 0022B150 GetLastError  : canonical support dispatch ARMED"
Write-Host "[Phase6CU] 0022B178 SetLastError  : existing shared state preserved"
Write-Host "[Phase6CU] XACT async read        : preserved"
Write-Host "[Phase6CU] Partition0 path        : preserved"
Write-Host "[Phase6CU] D3D/XGRPH state        : preserved"
Write-Host ("[Phase6CU] Generated shards       : {0}" -f $shardCount)
Write-Host "[Phase6CU] Pixel/display telemetry: preserved"
Write-Host "[Phase6CU] 64M watchdog          : preserved"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CU-POST-ASYNC-GETLASTERROR-0022B150-20261025-A"
    ExpectedEnvCookie="phase6cu_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cu-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cu-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CU-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CU] BUILD PASS"
  Write-Host ("[Phase6CU] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CU-A.xex"))
}
