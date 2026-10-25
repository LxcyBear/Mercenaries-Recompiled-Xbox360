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
$base=Join-Path $root "build\phase6_native_graphics\apu_core_mmio_xdk"
$out=Join-Path $root "build\phase6_native_graphics\apu_gp_ep_dsp_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6ci_apu_gp_ep_dsp.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CI input: $f"
  }
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6ch-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6ch=Join-Path $PSScriptRoot "Prepare-Phase6CH.ps1"
  if(-not(Test-Path -LiteralPath $prep6ch)){
    throw "Phase 6CI baseline missing and Phase 6CH regeneration script not found"
  }
  Write-Host "[Phase6CI] Cached 6CH output missing; regenerating 6CH without solution build..."
  & $prep6ch -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CI could not regenerate 6CH baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6ch-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CH"-or$m.build_tag-ne"P6CH-APU-CORE-MMIO-20261025-A"){
  throw "Phase 6CI baseline identity mismatch"
}
$ch=$m.phase6ch_apu_core_mmio
if($ch.execution_budget_inherited-ne32000000-or
   $ch.translated_membership_changed-ne$false-or
   $ch.non_core_apu_mmio_fenced-ne$true){
  throw "Phase 6CI inherited 6CH policy mismatch"
}

Write-Host "[Phase6CI] MCPX GP/EP DSP BOOTSTRAP"
Write-Host "[Phase6CI] 6CH APU core transactions before next fault: 19"
Write-Host "[Phase6CI] Next boundary: WRITE32 FE83FFFC at tick 26,711,365"
Write-Host "[Phase6CI] Register: GP DSP NV_PAPU_GPRST"
Write-Host "[Phase6CI] Batch: GP FE830000-FE83FFFF + EP FE850000-FE85FFFF"
Write-Host "[Phase6CI] DSP words: 24-bit preserved/read back"
Write-Host "[Phase6CI] VP and APU gap remain fenced"
Write-Host "[Phase6CI] DSP execution is NOT claimed"
Write-Host "[Phase6CI] 32M watchdog preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){
  throw "Phase 6CI emitter syntax check failed"
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
    Tee-Object -Variable phase6ciEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CI] EMITTER OUTPUT:"
  $phase6ciEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CI emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6ci-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CI output: $f"
  }
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CI"-or$r.build_tag-ne"P6CI-APU-GPEP-DSP-20261025-A"){
  throw "Phase 6CI manifest identity mismatch"
}

$a=$r.phase6ci_apu_gp_ep_dsp
if($a.phase6ch_hardware.boundary_kind-ne"GUEST_FAULT"-or
   $a.phase6ch_hardware.target-ne"0xFE83FFFC"-or
   $a.phase6ch_hardware.access-ne"WRITE32"-or
   $a.phase6ch_hardware.ticks-ne26711365-or
   $a.phase6ch_hardware.fault-ne1-or
   $a.phase6ch_hardware.apu_core_transactions_before_fault.read8-ne1-or
   $a.phase6ch_hardware.apu_core_transactions_before_fault.read32-ne5-or
   $a.phase6ch_hardware.apu_core_transactions_before_fault.write32-ne13-or
   $a.phase6ch_hardware.fectl-ne"0x00000080"-or
   $a.register_identity.name-ne"NV_PAPU_GPRST"-or
   $a.register_identity.address-ne"0xFE83FFFC"-or
   $a.register_identity.processor_offset-ne"0x0000FFFC"-or
   $a.model.gp_base-ne"0xFE830000"-or
   $a.model.ep_base-ne"0xFE850000"-or
   $a.model.window_size-ne"0x00010000"-or
   $a.model.word_width_bits-ne24-or
   $a.model.actual_dsp_microcode_execution-ne$false-or
   $a.model.actual_audio_processing-ne$false-or
   $a.translated_membership_changed-ne$false-or
   $a.apu_core_semantics_changed-ne$false-or
   $a.guest_irql_semantics_changed-ne$false-or
   $a.xacteng_membership_changed-ne$false-or
   $a.execution_budget_inherited-ne32000000-or
   $a.dispatch_log_stride_inherited-ne4096){
  throw "Phase 6CI hardware/DSP manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "#define PHASE6CI_APU_GP_BASE  0xFE830000u",
  "#define PHASE6CI_APU_EP_BASE  0xFE850000u",
  "#define PHASE6CI_DSP_RST      0x0000FFFCu",
  "phase6ci_dsp_range(",
  "phase6ci_dsp_write(",
  "P6CI APU DSP:",
  "P6CI APU CORE:",
  "#define PHASE4C_EXEC_BUDGET 32000000u",
  "phase6ci_env_build_cookie"
)){
  if(-not$text.Contains($marker)){
    throw "Phase 6CI source gate missing: $marker"
  }
}

if(-not$text.Contains("VP, the APU gap, and all non-APU MMIO fenced")){
  throw "Phase 6CI fence-policy marker missing"
}

$statePos=$text.IndexOf("static uint32_t s_phase6ciGpDsp[0x4000];")
$helperPos=$text.IndexOf("static int phase6ci_dsp_range(")
$readPos=$text.IndexOf("static uint8_t phase6ch_apu_read8(")
$optPos=$text.IndexOf('#pragma optimize("", off)')
$summaryPos=$text.IndexOf("P6CI APU DSP:")
if($statePos-lt0-or$helperPos-lt0-or$readPos-lt0-or$optPos-lt0-or$summaryPos-lt0-or
   $statePos-gt$summaryPos-or
   $statePos-gt$helperPos-or
   $helperPos-gt$readPos-or
   $readPos-gt$optPos){
  throw "Phase 6CI declaration-order gate failed"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){
  throw "Phase 6CI translated shard output is empty"
}

Write-Host "[Phase6CI] READY"
Write-Host "[Phase6CI] GP DSP window : FE830000-FE83FFFF"
Write-Host "[Phase6CI] EP DSP window : FE850000-FE85FFFF"
Write-Host "[Phase6CI] GP reset reg  : FE83FFFC"
Write-Host "[Phase6CI] EP reset reg  : FE85FFFC"
Write-Host "[Phase6CI] Word width    : 24-bit"
Write-Host "[Phase6CI] VP region     : still fenced"
Write-Host "[Phase6CI] APU 0x40000   : still fenced"
Write-Host "[Phase6CI] DSP execution : disabled/not claimed"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CI-APU-GPEP-DSP-20261025-A"
    ExpectedEnvCookie="phase6ci_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6ci-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6ci-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CI-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CI] BUILD PASS"
  Write-Host ("[Phase6CI] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CI-A.xex"))
}
