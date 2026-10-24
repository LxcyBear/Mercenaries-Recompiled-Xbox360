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
$base=Join-Path $root "build\phase6_native_graphics\post_pbl_frontier_00209a70_xdk"
$out=Join-Path $root "build\phase6_native_graphics\ntsetinfo226_position_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bs_ntsetinfo226_position.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6br-manifest.json")
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BS input: $f"}
}

$m=Get-Content (Join-Path $base "phase6br-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BR"-or$m.build_tag-ne"P6BR-POST-PBL-FRONTIER-00209A70-20261024-A"){
  throw "Phase 6BS baseline identity mismatch"
}

Write-Host "[Phase6BS] NTSETINFORMATIONFILE ORDINAL 226"
Write-Host "[Phase6BS] 6BR hardware: translated root 00209A70 entered"
Write-Host "[Phase6BS] Boundary: ICALL_SAFE target=800000E2 caller=0023A3CE fault=0"
Write-Host "[Phase6BS] Frame: 24 bytes exactly canonical for NtSetInformationFile@20"
Write-Host "[Phase6BS] Policy: class 14 FilePositionInformation, length 8 only; every other class fenced"
Write-Host "[Phase6BS] Existing tagged handles + phase5h_seek_absolute reused"
Write-Host "[Phase6BS] Both ABI repairs and all GPU/allocator/8M-budget invariants preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BS emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6bsEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BS] EMITTER OUTPUT:"
  $phase6bsEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6BS emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bs-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6BS output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BS"-or$r.build_tag-ne"P6BS-NTSETINFO226-POSITION-20261024-A"){
  throw "Phase 6BS manifest identity mismatch"
}
$a=$r.phase6bs_ntsetinfo226_position
if($a.phase6br_hardware.kernel_target-ne"0x800000E2"-or
   $a.phase6br_hardware.kernel_ordinal-ne226-or
   $a.phase6br_hardware.observed_frame_bytes-ne24-or
   $a.phase6br_hardware.canonical_frame_bytes-ne24-or
   $a.phase6br_hardware.fault-ne0){
  throw "Phase 6BS hardware-proof gate failed"
}
if($a.continuation.accepted_information_class-ne14-or
   $a.continuation.accepted_length-ne8-or
   $a.continuation.all_other_information_classes_fenced-ne$true){
  throw "Phase 6BS class-14-only continuation gate failed"
}
if($a.translated_membership_changed-ne$false-or
   $a.all_phase6bq_abi_repairs_inherited-ne$true-or
   $a.all_phase6br_gpu_bridges_inherited-ne$true-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false-or
   $a.execution_budget-ne8000000){
  throw "Phase 6BS inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "_phase4c_target == 0x800000E2u",
  "NtSetInformationFile LIVE FRAME:",
  "infoClass != 14u || length != 8u",
  "phase5h_seek_absolute(nativeHandle, positionLow, positionHigh)",
  "PASS: Phase 6BS NtSetInformationFile position continuation",
  "P6BS NTSETINFO226:",
  "phase6bs_env_build_cookie",
  "NtQueryVolumeInformationFile SAVEDESP REPAIR PROBE:",
  "RtlInitAnsiString SAVEDESP REPAIR PROBE:",
  "phase6be_pfifo_idle_write32(address, value)",
  "phase6bj_pfb_zcomp_write32",
  "phase6bg_pfb_tile_write32",
  "phase6bh_pgraph_scoped_write32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BS source gate missing: $marker"}
}

Write-Host "[Phase6BS] READY ordinal=226 frame=24 class=14 len=8"
Write-Host "[Phase6BS] Unknown NtSetInformationFile classes remain hard-fenced"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BS-NTSETINFO226-POSITION-20261024-A"
    ExpectedEnvCookie="phase6bs_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bs-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bs-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BS-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BS] BUILD PASS"
  Write-Host ("[Phase6BS] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BS-A.xex"))
}
