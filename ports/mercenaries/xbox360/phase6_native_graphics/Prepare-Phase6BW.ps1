[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\\Users\\jorda\\OneDrive\\Desktop\\My Xbox\\My Projects\\Mercenaries - Xbox 360\\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\\..\\..\\.."))
$p4=Join-Path $root "ports\\mercenaries\\xbox360\\phase4c_native_startup"
$python=Join-Path $root ".venv\\Scripts\\python.exe"
$base=Join-Path $root "build\\phase6_native_graphics\\fileobject_first_deref_xdk"
$out=Join-Path $root "build\\phase6_native_graphics\\keraiseirql129_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bw_keraiseirql129.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bv-manifest.json")
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BW input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bv-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BV"-or$m.build_tag-ne"P6BV-FILEOBJECT-FIRST-DEREF-20261024-A"){
  throw "Phase 6BW baseline identity mismatch"
}

Write-Host "[Phase6BW] KERAISEIRQLTODPCLEVEL ORDINAL 129"
Write-Host "[Phase6BW] 6BV hardware: FILE_OBJECT sentinel 04000000 survived with no guest dereference"
Write-Host "[Phase6BW] Boundary: target=80000081 ordinal=129 frame=4 fault=0"
Write-Host "[Phase6BW] Guest-only IRQL model: return previous level; raise maintained level to DISPATCH_LEVEL(2)"
Write-Host "[Phase6BW] Native Xenon processor IRQL remains untouched"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BW emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6bwEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BW] EMITTER OUTPUT:"
  $phase6bwEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6BW emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bw-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6BW output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BW"-or$r.build_tag-ne"P6BW-KERAISEIRQL129-20261024-A"){
  throw "Phase 6BW manifest identity mismatch"
}
$a=$r.phase6bw_ke_raise_irql_to_dpc_level
if($a.phase6bv_hardware.returned_sentinel-ne"0x04000000"-or
   $a.phase6bv_hardware.sentinel_guest_dereference_observed_before_next_boundary-ne$false-or
   $a.phase6bv_hardware.next_boundary_target-ne"0x80000081"-or
   $a.phase6bv_hardware.next_boundary_ordinal-ne129-or
   $a.phase6bv_hardware.frame_bytes-ne4-or
   $a.phase6bv_hardware.fault-ne0){
  throw "Phase 6BW hardware-proof gate failed"
}
if($a.continuation.dispatch_level-ne2-or
   $a.continuation.returns_previous_irql_in_eax-ne$true-or
   $a.continuation.changes_native_xenon_irql-ne$false-or
   $a.continuation.matching_lower_irql_exports_remain_fenced-ne$true){
  throw "Phase 6BW guest-IRQL policy gate failed"
}
if($a.translated_membership_changed-ne$false-or
   $a.file_object_sentinel_preserved-ne$true-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false-or
   $a.execution_budget-ne8000000){
  throw "Phase 6BW inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "_phase4c_target == 0x80000081u",
  "KeRaiseIrqlToDpcLevel LIVE FRAME:",
  "PASS: Phase 6BW KeRaiseIrqlToDpcLevel guest continuation",
  "P6BW KERAISEIRQL129:",
  "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
  "phase6bw_env_build_cookie",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BW source gate missing: $marker"}
}

Write-Host "[Phase6BW] READY ordinal=129 frame=4 guest_irql=0->2 native_irql_unchanged=1"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BW-KERAISEIRQL129-20261024-A"
    ExpectedEnvCookie="phase6bw_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bw-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bw-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BW-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BW] BUILD PASS"
  Write-Host ("[Phase6BW] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BW-A.xex"))
}
