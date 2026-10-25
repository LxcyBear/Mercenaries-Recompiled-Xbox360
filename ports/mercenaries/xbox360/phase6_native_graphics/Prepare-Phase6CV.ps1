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
$base=Join-Path $root "build\phase6_native_graphics\post_async_getlasterror_0022b150_xdk"
$out=Join-Path $root "build\phase6_native_graphics\shadow_ram_f0000000_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cv_shadow_ram_f0000000.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CV input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cu-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cu=Join-Path $PSScriptRoot "Prepare-Phase6CU.ps1"
  if(-not(Test-Path -LiteralPath $prep6cu)){
    throw "Phase 6CV baseline missing and Phase 6CU regeneration script not found"
  }
  Write-Host "[Phase6CV] Cached 6CU output missing; regenerating 6CU without solution build..."
  & $prep6cu -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CV could not regenerate 6CU baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cu-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CU"-or$m.build_tag-ne"P6CU-POST-ASYNC-GETLASTERROR-0022B150-20261025-A"){
  throw "Phase 6CV baseline identity mismatch"
}
$cu=$m.phase6cu_post_async_get_last_error
if($cu.execution_budget_inherited-ne64000000-or
   $cu.async_read_semantics_changed-ne$false-or
   $cu.partition0_semantics_changed-ne$false-or
   $cu.graphics_bridge_semantics_changed-ne$false-or
   $cu.hard_fences_weakened-ne$false-or
   $cu.dispatch_policy.canonical_support_helper_reused-ne$true){
  throw "Phase 6CV inherited 6CU policy mismatch"
}

Write-Host "[Phase6CV] RETAIL NV2A BAR1 / SHADOW-RAM CONTINUATION"
Write-Host "[Phase6CV] 6CU hardware: GUEST_FAULT READ32 F08B0000"
Write-Host "[Phase6CV] 6CU marker  : FIRST GRAPHICS TOUCH / NV2A VRAM aperture"
Write-Host "[Phase6CV] Map only   : F0000000-F3FFFFFF -> 00000000-03FFFFFF"
Write-Host "[Phase6CV] Proof      : F08B0000 -> 008B0000"
Write-Host "[Phase6CV] FD/FE MMIO : existing scoped bridges unchanged"
Write-Host "[Phase6CV] F4000000+  : remains outside this alias"
Write-Host "[Phase6CV] XACT/GetLastError/D3D/Partition0 semantics preserved"
Write-Host "[Phase6CV] Watchdog   : preserve 64,000,000 translated blocks"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CV emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CV-R1"')){
  throw "Phase 6CV stale emitter detected; expected revision 6CV-R1"
}
Write-Host "[Phase6CV] Emitter revision       : 6CV-R1"

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
    Tee-Object -Variable phase6cvEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CV] EMITTER OUTPUT:"
  $phase6cvEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CV emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cv-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CV output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CV"-or$r.build_tag-ne"P6CV-SHADOW-RAM-F0000000-20261025-A"){
  throw "Phase 6CV manifest identity mismatch"
}
$k=$r.phase6cv_shadow_ram_alias
if($k.phase6cu_hardware.boundary_kind-ne"GUEST_FAULT"-or
   $k.phase6cu_hardware.caller-ne"0x0023A3CE"-or
   $k.phase6cu_hardware.target-ne"0xF08B0000"-or
   $k.phase6cu_hardware.access-ne"READ"-or
   $k.phase6cu_hardware.width-ne4-or
   $k.phase6cu_hardware.fault-ne1-or
   $k.phase6cu_hardware.get_last_error_value-ne"0x000003E5"-or
   $k.mapping.guest_start-ne"0xF0000000"-or
   $k.mapping.guest_end_exclusive-ne"0xF4000000"-or
   $k.mapping.physical_start-ne"0x00000000"-or
   $k.mapping.physical_end_exclusive-ne"0x04000000"-or
   $k.mapping.fault_example_physical-ne"0x008B0000"-or
   $k.execution_budget_inherited-ne64000000-or
   $k.translated_pack_changed-ne$false-or
   $k.async_read_semantics_changed-ne$false-or
   $k.partition0_semantics_changed-ne$false-or
   $k.graphics_mmio_semantics_changed-ne$false-or
   $k.apu_mmio_semantics_changed-ne$false-or
   $k.kseg_semantics_changed-ne$false-or
   $k.hard_fences_weakened-ne$false){
  throw "Phase 6CV manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CV-SHADOW-RAM-F0000000-20261025-A",
  "phase6cv_env_build_cookie",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "#define PHASE6CV_SHADOW_END  0xF4000000u",
  "offset = address - PHASE6CV_SHADOW_BASE;",
  "P6CV SHADOW RAM READ",
  "P6CV SHADOW RAM:",
  "PASS: Phase 6CV maintained GetLastError",
  "P6CV ASYNC STREAM READ:",
  "P6CV PIXEL CHASE:",
  "P6CV PRESENT PROXIMITY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CV source gate missing: $marker"}
}

$shadowBasePos=$text.IndexOf("else if (address >= PHASE6CV_SHADOW_BASE &&")
$ksegPos=$text.IndexOf("else if (address >= KSEG_BASE && address < KSEG_END)")
if($shadowBasePos-lt0-or$ksegPos-lt0-or$shadowBasePos-ge$ksegPos){
  throw "Phase 6CV shadow alias must precede the inherited KSEG branch"
}

if(([regex]::Matches($text,[regex]::Escape("#define PHASE6CV_SHADOW_BASE 0xF0000000u"))).Count-ne1){
  throw "Phase 6CV shadow base definition count mismatch"
}
if(([regex]::Matches($text,[regex]::Escape("#define PHASE6CV_SHADOW_END  0xF4000000u"))).Count-ne1){
  throw "Phase 6CV shadow end definition count mismatch"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CV translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6CV] READY"
Write-Host "[Phase6CV] Shadow RAM alias       : F0000000-F3FFFFFF -> 00000000-03FFFFFF"
Write-Host "[Phase6CV] First proven address   : F08B0000 -> 008B0000"
Write-Host "[Phase6CV] Read/write telemetry   : ARMED"
Write-Host "[Phase6CV] FD/FE scoped MMIO      : preserved"
Write-Host "[Phase6CV] XACT/GetLastError      : preserved"
Write-Host "[Phase6CV] D3D/XGRPH state        : preserved"
Write-Host ("[Phase6CV] Generated shards       : {0}" -f $shardCount)
Write-Host "[Phase6CV] 64M watchdog           : preserved"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CV-SHADOW-RAM-F0000000-20261025-A"
    ExpectedEnvCookie="phase6cv_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cv-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cv-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CV-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CV] BUILD PASS"
  Write-Host ("[Phase6CV] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CV-A.xex"))
}
