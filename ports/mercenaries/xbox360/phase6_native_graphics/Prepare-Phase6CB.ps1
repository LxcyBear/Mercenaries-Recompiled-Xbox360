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
$base=Join-Path $root "build\phase6_native_graphics\kflowerirql161_xdk"
$out=Join-Path $root "build\phase6_native_graphics\obfderef250_sentinel_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6cb_obfderef250_sentinel.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6ca-manifest.json")
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CB input: $f"}
}

$m=Get-Content (Join-Path $base "phase6ca-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CA"-or$m.build_tag-ne"P6CA-KFLOWERIRQL161-20261024-A"){
  throw "Phase 6CB baseline identity mismatch"
}

Write-Host "[Phase6CB] OBFDEREFERENCEOBJECT250 SENTINEL RELEASE"
Write-Host "[Phase6CB] 6CA hardware: KfLowerIrql PASS 2->0"
Write-Host "[Phase6CB] Boundary: target=800000FA ordinal=250 ObfDereferenceObject"
Write-Host "[Phase6CB] Frame: esp=008BF8F8 saved=008BF8FC delta=4"
Write-Host "[Phase6CB] FASTCALL object: ECX=04000000 exact Phase-6BV FILE_OBJECT sentinel"
Write-Host "[Phase6CB] Policy: balanced synthetic release only; no sentinel dereference"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CB emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6cbEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6CB] EMITTER OUTPUT:"
  $phase6cbEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CB emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cb-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6CB output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CB"-or$r.build_tag-ne"P6CB-OBFDEREF250-SENTINEL-20261024-A"){
  throw "Phase 6CB manifest identity mismatch"
}

$a=$r.phase6cb_obf_dereference_object
if($a.phase6ca_hardware.next_boundary_target-ne"0x800000FA"-or
   $a.phase6ca_hardware.next_boundary_ordinal-ne250-or
   $a.phase6ca_hardware.boundary_ecx-ne"0x04000000"-or
   $a.phase6ca_hardware.frame_bytes-ne4-or
   $a.phase6ca_hardware.guest_irql_old-ne2-or
   $a.phase6ca_hardware.guest_irql_new-ne0-or
   $a.phase6ca_hardware.fault-ne0){
  throw "Phase 6CB 6CA-hardware proof gate failed"
}

if($a.continuation.calling_convention-ne"FASTCALL"-or
   $a.continuation.argument_source-ne"ECX"-or
   $a.continuation.expected_object-ne"0x04000000"-or
   $a.continuation.expected_object_is_phase6bv_sentinel-ne$true-or
   $a.continuation.dereferences_guest_object_memory-ne$false-or
   $a.continuation.changes_host_object_refcount-ne$false-or
   $a.continuation.requires_prior_synthetic_obref-ne$true){
  throw "Phase 6CB sentinel-release continuation gate failed"
}

if($a.translated_membership_changed-ne$false-or
   $a.low_kseg_fence_changed-ne$false-or
   $a.file_object_sentinel_preserved-ne$true-or
   $a.phase5_env_semantics_changed-ne$false-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false-or
   $a.execution_budget-ne8000000){
  throw "Phase 6CB inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "_phase4c_target == 0x800000FAu",
  "phase6cb_obf_dereference_object",
  "ObfDereferenceObject LIVE FRAME:",
  "PASS: Phase 6CB ObfDereferenceObject sentinel release",
  "P6CB OBFDEREF250:",
  "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
  "phase6cb_env_build_cookie",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CB source gate missing: $marker"}
}

Write-Host "[Phase6CB] READY ordinal=250 object=04000000 synthetic_release=1 sentinel_deref=0 host_refcount_change=0"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CB-OBFDEREF250-SENTINEL-20261024-A"
    ExpectedEnvCookie="phase6cb_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cb-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cb-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CB-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CB] BUILD PASS"
  Write-Host ("[Phase6CB] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CB-A.xex"))
}
