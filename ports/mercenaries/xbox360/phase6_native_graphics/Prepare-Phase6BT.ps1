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
$base=Join-Path $root "build\\phase6_native_graphics\\ntsetinfo226_position_xdk"
$out=Join-Path $root "build\\phase6_native_graphics\\kedelay99_relative_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bt_kedelay99_relative.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bs-manifest.json")
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BT input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bs-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BS"-or$m.build_tag-ne"P6BS-NTSETINFO226-POSITION-20261024-A"){
  throw "Phase 6BT baseline identity mismatch"
}

Write-Host "[Phase6BT] KEDELAYEXECUTIONTHREAD ORDINAL 99"
Write-Host "[Phase6BT] 6BS hardware: class-14 NtSetInformationFile PASS x3"
Write-Host "[Phase6BT] xesrb.tga consumed completely: 786432 + 44 = 786476 bytes"
Write-Host "[Phase6BT] Boundary: ICALL_SAFE target=80000063 caller=0023A3CE fault=0"
Write-Host "[Phase6BT] Frame: 16 bytes exactly canonical for KeDelayExecutionThread@12"
Write-Host "[Phase6BT] Policy: relative/zero delay only, max 10s hardware bound; absolute delays fenced"
Write-Host "[Phase6BT] 6BS file/GPU/allocator/8M-budget invariants preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BT emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6btEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BT] EMITTER OUTPUT:"
  $phase6btEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6BT emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bt-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6BT output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BT"-or$r.build_tag-ne"P6BT-KEDELAY99-RELATIVE-20261024-A"){
  throw "Phase 6BT manifest identity mismatch"
}
$a=$r.phase6bt_kedelay99_relative
if($a.phase6bs_hardware.kernel_target-ne"0x80000063"-or
   $a.phase6bs_hardware.kernel_ordinal-ne99-or
   $a.phase6bs_hardware.observed_frame_bytes-ne16-or
   $a.phase6bs_hardware.canonical_frame_bytes-ne16-or
   $a.phase6bs_hardware.fault-ne0-or
   $a.phase6bs_hardware.xesrb_complete_file_consumed-ne$true){
  throw "Phase 6BT hardware-proof gate failed"
}
if($a.continuation.relative_negative_delays_supported-ne$true-or
   $a.continuation.positive_absolute_delays_fenced-ne$true-or
   $a.continuation.max_relative_delay_ms-ne10000){
  throw "Phase 6BT delay-policy gate failed"
}
if($a.translated_membership_changed-ne$false-or
   $a.all_phase6bs_file_and_abi_repairs_inherited-ne$true-or
   $a.all_phase6bs_gpu_bridges_inherited-ne$true-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false-or
   $a.execution_budget-ne8000000){
  throw "Phase 6BT inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "_phase4c_target == 0x80000063u",
  "KeDelayExecutionThread LIVE FRAME:",
  "milliseconds64 > 10000ui64",
  "PASS: Phase 6BT KeDelayExecutionThread relative continuation",
  "P6BT KEDELAY99:",
  "phase6bt_env_build_cookie",
  "NtSetInformationFile LIVE FRAME:",
  "P6BT NTSETINFO226:",
  "NtQueryVolumeInformationFile SAVEDESP REPAIR PROBE:",
  "RtlInitAnsiString SAVEDESP REPAIR PROBE:",
  "phase6be_pfifo_idle_write32(address, value)",
  "phase6bj_pfb_zcomp_write32",
  "phase6bg_pfb_tile_write32",
  "phase6bh_pgraph_scoped_write32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BT source gate missing: $marker"}
}

Write-Host "[Phase6BT] READY ordinal=99 frame=16 relative_delay_only=1 max_ms=10000"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BT-KEDELAY99-RELATIVE-20261024-A"
    ExpectedEnvCookie="phase6bt_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bt-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bt-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BT-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BT] BUILD PASS"
  Write-Host ("[Phase6BT] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BT-A.xex"))
}
