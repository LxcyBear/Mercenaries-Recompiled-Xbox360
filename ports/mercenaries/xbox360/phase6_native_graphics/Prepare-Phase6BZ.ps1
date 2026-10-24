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
$base=Join-Path $root "build\\phase6_native_graphics\\idex357_data_xdk"
$out=Join-Path $root "build\\phase6_native_graphics\\idex357_devicequeue_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bz_idex357_devicequeue.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6by-manifest.json")
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BZ input: $f"}
}

$m=Get-Content (Join-Path $base "phase6by-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BY"-or$m.build_tag-ne"P6BY-IDEX357-DATA-20261024-A"){
  throw "Phase 6BZ baseline identity mismatch"
}

Write-Host "[Phase6BZ] IDEXCHANNELOBJECT DEVICEQUEUE MODEL"
Write-Host "[Phase6BZ] 6BY hardware: thunk relocation succeeded and old 8000018D fault disappeared"
Write-Host "[Phase6BZ] Hardware access: object+28 = 0087E0C8 DeviceQueue.DeviceListHead"
Write-Host "[Phase6BZ] Queue: Type=14 Size=0C Busy=0 Flink=Blink=0087E0C8"
Write-Host "[Phase6BZ] Policy: keep low-KSEG fence unchanged"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BZ emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6bzEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BZ] EMITTER OUTPUT:"
  $phase6bzEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6BZ emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bz-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6BZ output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BZ"-or$r.build_tag-ne"P6BZ-IDEX357-DEVICEQUEUE-20261024-A"){
  throw "Phase 6BZ manifest identity mismatch"
}
$a=$r.phase6bz_idex357_devicequeue
if($a.phase6by_hardware.data_thunk_fixup_new-ne"0x0087E0A0"-or
   $a.phase6by_hardware.device_list_head_access-ne"0x0087E0C8"-or
   $a.phase6by_hardware.device_list_head_offset-ne"0x28"-or
   $a.phase6by_hardware.observed_flink_before_fix-ne"0x00000000"-or
   $a.phase6by_hardware.old_low_kseg_fault_cleared-ne$true-or
   $a.phase6by_hardware.new_fault_address-ne"0xFFFFFFFF"-or
   $a.phase6by_hardware.xapi_return-ne0){
  throw "Phase 6BZ 6BY-hardware proof gate failed"
}
if($a.device_queue_model.object_base-ne"0x0087E0A0"-or
   $a.device_queue_model.queue_header_va-ne"0x0087E0C4"-or
   $a.device_queue_model.queue_header_value-ne"0x000C0014"-or
   $a.device_queue_model.device_list_head_va-ne"0x0087E0C8"-or
   $a.device_queue_model.flink-ne"0x0087E0C8"-or
   $a.device_queue_model.blink-ne"0x0087E0C8"-or
   $a.device_queue_model.empty_circular_list-ne$true){
  throw "Phase 6BZ DeviceQueue model gate failed"
}
if($a.translated_membership_changed-ne$false-or
   $a.low_kseg_fence_changed-ne$false-or
   $a.phase5_env_semantics_changed-ne$false-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false-or
   $a.execution_budget-ne8000000){
  throw "Phase 6BZ inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "case 357u: return 0x0087E0A0u; /* IdexChannelObject IDE_CHANNEL_OBJECT */",
  "GUEST_WRITE32(0x0087E0C4u, 0x000C0014u)",
  "GUEST_WRITE32(0x0087E0C8u, 0x0087E0C8u)",
  "GUEST_WRITE32(0x0087E0CCu, 0x0087E0C8u)",
  "P6BZ IDEX LIVE BASE:",
  "P6BZ IDEX QUEUE HEAD:",
  "expected_self=0087E0C8",
  "phase6bz_env_build_cookie",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BZ source gate missing: $marker"}
}

Write-Host "[Phase6BZ] READY ordinal=357 base=0087E0A0 queue=0087E0C4 list=0087E0C8 empty_circular=1 kseg_fence_unchanged=1"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BZ-IDEX357-DEVICEQUEUE-20261024-A"
    ExpectedEnvCookie="phase6bz_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bz-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bz-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BZ-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BZ] BUILD PASS"
  Write-Host ("[Phase6BZ] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BZ-A.xex"))
}
