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
$base=Join-Path $root "build\phase6_native_graphics\idex357_devicequeue_xdk"
$out=Join-Path $root "build\phase6_native_graphics\kflowerirql161_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6ca_kflowerirql161.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bz-manifest.json")
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CA input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bz-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BZ"-or$m.build_tag-ne"P6BZ-IDEX357-DEVICEQUEUE-20261024-A"){
  throw "Phase 6CA baseline identity mismatch"
}

Write-Host "[Phase6CA] KFLOWERIRQL161 GUEST IRQL CONTINUATION"
Write-Host "[Phase6CA] 6BZ hardware: IdexChannelObject/KDEVICE_QUEUE validated"
Write-Host "[Phase6CA] Boundary: target=800000A1 ordinal=161 KfLowerIrql"
Write-Host "[Phase6CA] Frame: esp=008BF8F8 saved=008BF8FC delta=4"
Write-Host "[Phase6CA] FASTCALL argument: ECX=0087E000 -> CL=00"
Write-Host "[Phase6CA] Expected guest IRQL transition: 2 -> 0"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CA emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6caEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6CA] EMITTER OUTPUT:"
  $phase6caEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CA emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6ca-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6CA output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CA"-or$r.build_tag-ne"P6CA-KFLOWERIRQL161-20261024-A"){
  throw "Phase 6CA manifest identity mismatch"
}

$a=$r.phase6ca_kf_lower_irql
if($a.phase6bz_hardware.next_boundary_target-ne"0x800000A1"-or
   $a.phase6bz_hardware.next_boundary_ordinal-ne161-or
   $a.phase6bz_hardware.boundary_raw_ecx-ne"0x0087E000"-or
   $a.phase6bz_hardware.boundary_cl-ne"0x00"-or
   $a.phase6bz_hardware.frame_bytes-ne4-or
   $a.phase6bz_hardware.fault-ne0){
  throw "Phase 6CA 6BZ-hardware proof gate failed"
}
if($a.continuation.calling_convention-ne"FASTCALL"-or
   $a.continuation.argument_source-ne"CL"-or
   $a.continuation.expected_first_old_irql-ne2-or
   $a.continuation.expected_first_new_irql-ne0-or
   $a.continuation.changes_native_xenon_irql-ne$false){
  throw "Phase 6CA KfLowerIrql continuation gate failed"
}
if($a.translated_membership_changed-ne$false-or
   $a.low_kseg_fence_changed-ne$false-or
   $a.file_object_sentinel_preserved-ne$true-or
   $a.phase5_env_semantics_changed-ne$false-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false-or
   $a.execution_budget-ne8000000){
  throw "Phase 6CA inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "_phase4c_target == 0x800000A1u",
  "phase6ca_kf_lower_irql",
  "KfLowerIrql LIVE FRAME:",
  "PASS: Phase 6CA KfLowerIrql guest continuation",
  "P6CA KFLOWERIRQL161:",
  "PHASE4C_BUDGET_TICK(0x0022ACE1u)",
  "phase6ca_env_build_cookie",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CA source gate missing: $marker"}
}

Write-Host "[Phase6CA] READY ordinal=161 KfLowerIrql fastcall_arg=CL expected=2->0 xenos_irql_unchanged=1"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CA-KFLOWERIRQL161-20261024-A"
    ExpectedEnvCookie="phase6ca_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6ca-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6ca-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CA-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CA] BUILD PASS"
  Write-Host ("[Phase6CA] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CA-A.xex"))
}
