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
$base=Join-Path $root "build\phase6_native_graphics\apu_gp_ep_dsp_xdk"
$out=Join-Path $root "build\phase6_native_graphics\mm166_general_tail_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cj_mm166_general_tail.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$phase6blEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CJ input: $f"
  }
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6ci-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6ci=Join-Path $PSScriptRoot "Prepare-Phase6CI.ps1"
  if(-not(Test-Path -LiteralPath $prep6ci)){
    throw "Phase 6CJ baseline missing and Phase 6CI regeneration script not found"
  }
  Write-Host "[Phase6CJ] Cached 6CI output missing; regenerating 6CI without solution build..."
  & $prep6ci -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CJ could not regenerate 6CI baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6ci-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CI"-or$m.build_tag-ne"P6CI-APU-GPEP-DSP-20261025-A"){
  throw "Phase 6CJ baseline identity mismatch"
}
$ci=$m.phase6ci_apu_gp_ep_dsp
if($ci.execution_budget_inherited-ne32000000-or
   $ci.translated_membership_changed-ne$false-or
   $ci.apu_core_semantics_changed-ne$false-or
   $ci.guest_irql_semantics_changed-ne$false){
  throw "Phase 6CJ inherited 6CI policy mismatch"
}

Write-Host "[Phase6CJ] GENERAL MM166 TAIL ALLOCATION"
Write-Host "[Phase6CJ] 6CI GP reset write : FE83FFFC <- 00000000"
Write-Host "[Phase6CJ] 6CI EP reset write : FE85FFFC <- 00000001"
Write-Host "[Phase6CJ] 6CI failed Mm166    : size=00002000 align=00001000 protect=00000004 frame=24"
Write-Host "[Phase6CJ] 6CI following fault : READ32 FFFFFFFF at tick 26,711,516"
Write-Host "[Phase6CJ] Strategy: normal allocator first, then safety-checked free-tail claim"
Write-Host "[Phase6CJ] Eligibility: canonical +24, low=0, high=FFFFFFFF, protect=4"
Write-Host "[Phase6CJ] Eligibility: size>=1000h, align>=1000h power-of-two"
Write-Host "[Phase6CJ] 96-byte align=4 fallback remains unchanged"
Write-Host "[Phase6CJ] 32M watchdog preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){
  throw "Phase 6CJ emitter syntax check failed"
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
    Tee-Object -Variable phase6cjEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CJ] EMITTER OUTPUT:"
  $phase6cjEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CJ emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cj-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CJ output: $f"
  }
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CJ"-or$r.build_tag-ne"P6CJ-MM166-GENERAL-TAIL-20261025-A"){
  throw "Phase 6CJ manifest identity mismatch"
}

$j=$r.phase6cj_mm166_general_tail
if($j.phase6ci_hardware.failed_mm166.size-ne"0x00002000"-or
   $j.phase6ci_hardware.failed_mm166.low-ne"0x00000000"-or
   $j.phase6ci_hardware.failed_mm166.high-ne"0xFFFFFFFF"-or
   $j.phase6ci_hardware.failed_mm166.alignment-ne"0x00001000"-or
   $j.phase6ci_hardware.failed_mm166.protect-ne"0x00000004"-or
   $j.phase6ci_hardware.failed_mm166.frame_bytes-ne24-or
   $j.phase6ci_hardware.failed_mm166.base-ne"0x00000000"-or
   $j.phase6ci_hardware.following_boundary.target-ne"0xFFFFFFFF"-or
   $j.phase6ci_hardware.following_boundary.access-ne"READ32"-or
   $j.phase6ci_hardware.following_boundary.ticks-ne26711516-or
   $j.repair.normal_allocator_first-ne$true-or
   $j.repair.helper_safety_checks_preserved-ne$true-or
   $j.repair.minimum_size-ne"0x00001000"-or
   $j.repair.minimum_alignment-ne"0x00001000"-or
   $j.repair.subpage_fallback_unchanged-ne$true-or
   $j.translated_membership_changed-ne$false-or
   $j.apu_gp_ep_semantics_changed-ne$false-or
   $j.guest_irql_semantics_changed-ne$false-or
   $j.xacteng_membership_changed-ne$false-or
   $j.execution_budget_inherited-ne32000000){
  throw "Phase 6CJ hardware/repair manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CJ-MM166-GENERAL-TAIL-20261025-A",
  "phase6cj_env_build_cookie",
  "s_phase6cjGeneralTailCalls",
  "size>=0x00001000u",
  "align>=0x00001000u",
  "frameBytes==24u",
  "prot==0x00000004u",
  "general_tail_claim=%u",
  "P6CJ MM166 GENERAL TAIL:",
  "P6CJ APU DSP:",
  "#define PHASE4C_EXEC_BUDGET 32000000u"
)){
  if(-not$text.Contains($marker)){
    throw "Phase 6CJ source gate missing: $marker"
  }
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){
  throw "Phase 6CJ translated shard output is empty"
}

Write-Host "[Phase6CJ] READY"
Write-Host "[Phase6CJ] Observed request : 8192 bytes / align 4096 / RW / canonical +24"
Write-Host "[Phase6CJ] Expected tail    : 024FA000 if page frontier remains 024FC000"
Write-Host "[Phase6CJ] Sub-page fallback: unchanged"
Write-Host "[Phase6CJ] GP/EP APU model  : unchanged"
Write-Host "[Phase6CJ] XACTENG pack     : unchanged"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CJ-MM166-GENERAL-TAIL-20261025-A"
    ExpectedEnvCookie="phase6cj_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cj-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cj-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CJ-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CJ] BUILD PASS"
  Write-Host ("[Phase6CJ] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CJ-A.xex"))
}
