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
$base=Join-Path $root "build\phase6_native_graphics\rtlansi_a3ce_repair_xdk"
$out=Join-Path $root "build\phase6_native_graphics\volume_a3ce_frame_repair_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bq_volume_a3ce_frame_repair.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bp-manifest.json")
)
foreach($f in $required){if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BQ input: $f"}}

$m=Get-Content (Join-Path $base "phase6bp-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BP"-or$m.build_tag-ne"P6BP-RTLANSI-A3CE-REPAIR-20261024-A"){throw "Phase 6BQ baseline identity mismatch"}

Write-Host "[Phase6BQ] NTQUERYVOLUME CALLER 0023A3CE FRAME REPAIR"
Write-Host "[Phase6BQ] 6BP hardware: RtlInitAnsi repair passed and PBL phase1 reached"
Write-Host "[Phase6BQ] Boundary: KERNEL_FRAME target=800000DA caller=0023A3CE delta=28 expected=24 fault=0"
Write-Host "[Phase6BQ] Repair requires live tagged handle + canonical class-3 24-byte query"
Write-Host "[Phase6BQ] No translated/GPU/allocator/budget widening"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BQ emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6bqEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BQ] EMITTER OUTPUT:"
  $phase6bqEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6BQ emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bq-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){if(-not(Test-Path $f)){throw "Missing Phase 6BQ output: $f"}}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BQ"-or$r.build_tag-ne"P6BQ-VOLUME-A3CE-FRAME-REPAIR-20261024-A"){throw "Phase 6BQ manifest identity mismatch"}
$a=$r.phase6bq_volume_a3ce_frame_repair
if($a.phase6bp_hardware.caller-ne"0x0023A3CE"-or
   $a.phase6bp_hardware.observed_frame_bytes-ne28-or
   $a.phase6bp_hardware.canonical_frame_bytes-ne24-or
   $a.phase6bp_hardware.fault-ne0-or
   $a.phase6bp_hardware.pbl_checkpoint_phase1-ne1){
  throw "Phase 6BQ hardware-proof gate failed"
}
if($a.translated_membership_changed-ne$false-or
   $a.all_phase6bp_gpu_bridges_inherited-ne$true-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false){
  throw "Phase 6BQ invariants gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "phase4c_current_caller() == 0x0023A3CEu",
  "NtQueryVolumeInformationFile SAVEDESP REPAIR PROBE:",
  "PASS: Phase 6BQ NtQueryVolumeInformationFile caller 0023A3CE saved-ESP repair",
  "probeLength < 24u",
  "probeClass != 3u",
  "savedEsp -= 4u;",
  "P6BQ POST-XGRPH FRONTIER 00209810:",
  "P6BQ PBL CHECKPOINT:",
  "phase6bq_env_build_cookie",
  "phase6be_pfifo_idle_write32(address, value)",
  "phase6bj_pfb_zcomp_write32",
  "phase6bg_pfb_tile_write32",
  "phase6bh_pgraph_scoped_write32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){if(-not$text.Contains($marker)){throw "Phase 6BQ source gate missing: $marker"}}

Write-Host "[Phase6BQ] READY caller=0023A3CE ordinal=218 repair=28->24 members_unchanged=$($r.pack_members)"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BQ-VOLUME-A3CE-FRAME-REPAIR-20261024-A"
    ExpectedEnvCookie="phase6bq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bq-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bq-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BQ-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BQ] BUILD PASS"
  Write-Host ("[Phase6BQ] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BQ-A.xex"))
}
