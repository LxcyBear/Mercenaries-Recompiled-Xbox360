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
$base=Join-Path $root "build\\phase6_native_graphics\\kedelay99_relative_xdk"
$out=Join-Path $root "build\\phase6_native_graphics\\obref246_probe_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bu_obref246_probe.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bt-manifest.json")
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BU input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bt-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BT"-or$m.build_tag-ne"P6BT-KEDELAY99-RELATIVE-20261024-A"){
  throw "Phase 6BU baseline identity mismatch"
}

Write-Host "[Phase6BU] OBREFERENCEOBJECTBYHANDLE ORDINAL 246 PROBE"
Write-Host "[Phase6BU] 6BT hardware: KeDelayExecutionThread 200ms relative wait PASS"
Write-Host "[Phase6BU] Boundary: ICALL_SAFE target=800000F6 caller=0023A3CE fault=0"
Write-Host "[Phase6BU] Frame: 16 bytes exactly canonical for ObReferenceObjectByHandle@12"
Write-Host "[Phase6BU] Probe-only policy: log Handle/ObjectType/ReturnedObject*; synthesize no object"
Write-Host "[Phase6BU] 6BT file/delay/GPU/allocator/8M-budget invariants preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BU emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6buEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BU] EMITTER OUTPUT:"
  $phase6buEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6BU emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bu-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6BU output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BU"-or$r.build_tag-ne"P6BU-OBREF246-PROBE-20261024-A"){
  throw "Phase 6BU manifest identity mismatch"
}
$a=$r.phase6bu_obref246_probe
if($a.phase6bt_hardware.kernel_target-ne"0x800000F6"-or
   $a.phase6bt_hardware.kernel_ordinal-ne246-or
   $a.phase6bt_hardware.observed_frame_bytes-ne16-or
   $a.phase6bt_hardware.canonical_frame_bytes-ne16-or
   $a.phase6bt_hardware.fault-ne0-or
   $a.probe_only-ne$true-or
   $a.synthesizes_object_pointer-ne$false){
  throw "Phase 6BU hardware-proof/probe-policy gate failed"
}
if($a.translated_membership_changed-ne$false-or
   $a.all_phase6bt_file_delay_gpu_invariants_inherited-ne$true-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false-or
   $a.execution_budget-ne8000000){
  throw "Phase 6BU inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "_phase4c_target == 0x800000F6u",
  "ObReferenceObjectByHandle LIVE PROBE:",
  "no object pointer synthesized",
  "P6BU OBREF246 PROBE:",
  "P6BU KEDELAY99:",
  "phase6bu_env_build_cookie",
  "NtSetInformationFile LIVE FRAME:",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BU source gate missing: $marker"}
}

Write-Host "[Phase6BU] READY ordinal=246 frame=16 probe_only=1"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BU-OBREF246-PROBE-20261024-A"
    ExpectedEnvCookie="phase6bu_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bu-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bu-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BU-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BU] BUILD PASS"
  Write-Host ("[Phase6BU] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BU-A.xex"))
}
