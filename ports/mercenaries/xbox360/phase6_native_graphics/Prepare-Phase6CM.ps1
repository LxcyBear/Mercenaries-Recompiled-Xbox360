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
$out=Join-Path $root "build\phase6_native_graphics\xact_esi_continuity_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cm_xact_esi_continuity.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CM input: $f"}
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
    throw "Phase 6CM baseline missing and Phase 6CJ regeneration script not found"
  }
  Write-Host "[Phase6CM] Cached 6CJ output missing; regenerating 6CJ without solution build..."
  & $prep6cj -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CM could not regenerate 6CJ baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cj-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CJ"-or$m.build_tag-ne"P6CJ-MM166-GENERAL-TAIL-20261025-A"){
  throw "Phase 6CM baseline identity mismatch"
}
$cj=$m.phase6cj_mm166_general_tail
if($cj.translated_membership_changed-ne$false-or
   $cj.apu_gp_ep_semantics_changed-ne$false-or
   $cj.guest_irql_semantics_changed-ne$false-or
   $cj.xacteng_membership_changed-ne$false-or
   $cj.execution_budget_inherited-ne32000000){
  throw "Phase 6CM inherited 6CJ policy mismatch"
}

Write-Host "[Phase6CM] GUARDED XACT ESI CONTINUITY TEST"
Write-Host "[Phase6CM] 6CK: ESI=01B5C320 at 002832BB"
Write-Host "[Phase6CM] 6CL: ESI=00000000 at 002832CA"
Write-Host "[Phase6CM] 6CL: READ32(0)=FFFFFFFF -> READ32(FFFFFFFF) GUEST_FAULT"
Write-Host "[Phase6CM] Restore guard: current ESI=0 AND captured ESI == live XACT root"
Write-Host "[Phase6CM] Null/SEH behavior and all hard fences remain unchanged"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CM emitter syntax check failed"}

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
    Tee-Object -Variable phase6cmEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CM] EMITTER OUTPUT:"
  $phase6cmEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CM emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cm-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CM output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CM"-or$r.build_tag-ne"P6CM-XACT-ESI-CONTINUITY-20261025-A"){
  throw "Phase 6CM manifest identity mismatch"
}
$k=$r.phase6cm_xact_esi_continuity
if($k.phase6cl_hardware.entry_esi-ne"0x00000000"-or
   $k.phase6cl_hardware.read_chain[0].address-ne"0x00000000"-or
   $k.phase6cl_hardware.read_chain[0].value-ne"0xFFFFFFFF"-or
   $k.phase6cl_hardware.read_chain[1].address-ne"0xFFFFFFFF"-or
   $k.phase6ck_hardware.capture_esi-ne"0x01B5C320"-or
   $k.guard.current_esi_must_be_zero-ne$true-or
   $k.guard.captured_esi_must_equal_live_xact_root-ne$true-or
   $k.guard.null_page_semantics_changed-ne$false-or
   $k.guard.seh_terminator_semantics_changed-ne$false-or
   $k.translated_membership_changed-ne$false-or
   $k.allocator_policy_changed-ne$false-or
   $k.apu_gp_ep_semantics_changed-ne$false-or
   $k.guest_irql_semantics_changed-ne$false-or
   $k.graphics_semantics_changed-ne$false-or
   $k.hard_fences_changed-ne$false-or
   $k.execution_budget_inherited-ne32000000){
  throw "Phase 6CM hardware/guard manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CM-XACT-ESI-CONTINUITY-20261025-A",
  "phase6cm_env_build_cookie",
  "P6CM XACT ESI CAPTURE va=002832BB",
  "PASS: Phase 6CM restored XACT ESI at 002832CA",
  "P6CM XACT ESI RESTORE SKIP",
  "P6CM XACT ESI:",
  "P6CM MM166 GENERAL TAIL:",
  "P6CM APU DSP:",
  "#define PHASE4C_EXEC_BUDGET 32000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CM source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CM translated shard output is empty"}

Write-Host "[Phase6CM] READY"
Write-Host "[Phase6CM] Capture block : 002832BB"
Write-Host "[Phase6CM] Restore block : 002832CA"
Write-Host "[Phase6CM] Guard         : ESI==0 && captured==live XACT root"
Write-Host "[Phase6CM] Null page     : unchanged"
Write-Host "[Phase6CM] SEH sentinel  : unchanged"
Write-Host "[Phase6CM] 32M watchdog : unchanged"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CM-XACT-ESI-CONTINUITY-20261025-A"
    ExpectedEnvCookie="phase6cm_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cm-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cm-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CM-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CM] BUILD PASS"
  Write-Host ("[Phase6CM] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CM-A.xex"))
}
