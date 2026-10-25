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
$base=Join-Path $root "build\phase6_native_graphics\kfraiseirql160_xdk"
$out=Join-Path $root "build\phase6_native_graphics\apu_core_mmio_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6ch_apu_core_mmio.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CH input: $f"
  }
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cg-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cg=Join-Path $PSScriptRoot "Prepare-Phase6CG.ps1"
  if(-not(Test-Path -LiteralPath $prep6cg)){
    throw "Phase 6CH baseline missing and Phase 6CG regeneration script not found"
  }
  Write-Host "[Phase6CH] Cached 6CG output missing; regenerating 6CG without solution build..."
  & $prep6cg -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CH could not regenerate 6CG baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cg-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CG"-or$m.build_tag-ne"P6CG-KFRAISEIRQL160-20261025-A"){
  throw "Phase 6CH baseline identity mismatch"
}
if($m.phase6cg_kf_raise_irql.execution_budget_inherited-ne32000000-or
   $m.phase6cg_kf_raise_irql.translated_membership_changed-ne$false-or
   $m.phase6cg_kf_raise_irql.hard_fences_changed-ne$false){
  throw "Phase 6CH inherited 6CG policy mismatch"
}

Write-Host "[Phase6CH] MCPX APU CORE-MMIO BOOTSTRAP"
Write-Host "[Phase6CH] 6CG hardware: KfRaiseIrql PASS 0->2"
Write-Host "[Phase6CH] Next boundary: READ8 FE801100 at tick 26,711,305"
Write-Host "[Phase6CH] Register: NV_PAPU_FECTL (APU base FE800000 + 1100)"
Write-Host "[Phase6CH] Model: reset-zero core register shadow, FE800000-FE81FFFF"
Write-Host "[Phase6CH] Scope: translated DSOUND functions only"
Write-Host "[Phase6CH] Non-core APU/other MMIO remains fenced"
Write-Host "[Phase6CH] 32M watchdog preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){
  throw "Phase 6CH emitter syntax check failed"
}

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
    Tee-Object -Variable phase6chEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CH] EMITTER OUTPUT:"
  $phase6chEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CH emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6ch-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CH output: $f"
  }
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CH"-or$r.build_tag-ne"P6CH-APU-CORE-MMIO-20261025-A"){
  throw "Phase 6CH manifest identity mismatch"
}

$a=$r.phase6ch_apu_core_mmio
if($a.phase6cg_hardware.boundary_kind-ne"GUEST_FAULT"-or
   $a.phase6cg_hardware.target-ne"0xFE801100"-or
   $a.phase6cg_hardware.access-ne"READ8"-or
   $a.phase6cg_hardware.ticks-ne26711305-or
   $a.phase6cg_hardware.fault-ne1-or
   $a.phase6cg_hardware.prior_kf_raise_irql_pass-ne$true-or
   $a.phase6cg_hardware.guest_irql_after_raise-ne2-or
   $a.register_identity.name-ne"NV_PAPU_FECTL"-or
   $a.register_identity.base-ne"0xFE800000"-or
   $a.register_identity.offset-ne"0x00001100"-or
   $a.model.core_size-ne"0x00020000"-or
   $a.model.reset_value-ne0-or
   $a.model.actual_audio_processing-ne$false-or
   $a.model.apu_irq_delivery-ne$false-or
   $a.scope.xbox_section-ne"DSOUND"-or
   $a.scope.fault_va-ne"0x002A7254"-or
   $a.scope.patched_function_count-lt1-or
   $a.scope.site_counts.read8-lt1-or
   $a.translated_membership_changed-ne$false-or
   $a.xacteng_membership_changed-ne$false-or
   $a.executive_pool_semantics_changed-ne$false-or
   $a.guest_irql_semantics_changed-ne$false-or
   $a.execution_budget_inherited-ne32000000-or
   $a.dispatch_log_stride_inherited-ne4096-or
   $a.non_apu_mmio_fences_changed-ne$false-or
   $a.non_core_apu_mmio_fenced-ne$true){
  throw "Phase 6CH hardware/APU manifest gate failed"
}

$faultOwner=[string]$a.scope.fault_owner.name
if([string]::IsNullOrEmpty($faultOwner)){
  throw "Phase 6CH fault-owner name missing"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "#define PHASE6CH_APU_BASE      0xFE800000u",
  "#define PHASE6CH_APU_CORE_SIZE 0x00020000u",
  "phase6ch_apu_read8(",
  "phase6ch_apu_write32(",
  "PASS: Phase 6CH entered DSOUND owner of FE801100 APU access",
  "P6CH APU CORE:",
  "P6CH KFRAISEIRQL160:",
  "#define PHASE4C_EXEC_BUDGET 32000000u",
  "phase6ch_env_build_cookie"
)){
  if(-not$text.Contains($marker)){
    throw "Phase 6CH source gate missing: $marker"
  }
}

if($text.Contains("Policy: Phase 6CH")-eq$false){
  throw "Phase 6CH policy marker missing"
}

$statePos=$text.IndexOf("static uint32_t s_phase6chApuRegs[0x8000];")
$helperPos=$text.IndexOf("static uint8_t phase6ch_apu_read8(")
$optPos=$text.IndexOf('#pragma optimize("", off)')
$summaryPos=$text.IndexOf("P6CH APU CORE:")
if($statePos-lt0-or$helperPos-lt0-or$optPos-lt0-or$summaryPos-lt0-or
   $statePos-gt$summaryPos-or
   $statePos-gt$helperPos-or
   $helperPos-gt$optPos){
  throw "Phase 6CH declaration-order gate failed"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){
  throw "Phase 6CH translated shard output is empty"
}

Write-Host "[Phase6CH] READY"
Write-Host ("[Phase6CH] Fault owner              : {0}" -f $faultOwner)
Write-Host ("[Phase6CH] Patched DSOUND functions: {0}" -f [int]$a.scope.patched_function_count)
Write-Host ("[Phase6CH] READ8 sites routed       : {0}" -f [int]$a.scope.site_counts.read8)
Write-Host ("[Phase6CH] READ32 sites routed      : {0}" -f [int]$a.scope.site_counts.read32)
Write-Host ("[Phase6CH] WRITE32 sites routed     : {0}" -f [int]$a.scope.site_counts.write32)
Write-Host "[Phase6CH] APU core reset state      : all zero"
Write-Host "[Phase6CH] Other MMIO                : still fenced"
Write-Host "[Phase6CH] Actual audio processing   : not yet claimed"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CH-APU-CORE-MMIO-20261025-A"
    ExpectedEnvCookie="phase6ch_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6ch-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6ch-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CH-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CH] BUILD PASS"
  Write-Host ("[Phase6CH] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CH-A.xex"))
}
