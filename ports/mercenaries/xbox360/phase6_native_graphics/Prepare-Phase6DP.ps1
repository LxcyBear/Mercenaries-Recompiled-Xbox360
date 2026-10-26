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
$base=Join-Path $root "build\\phase6_native_graphics\\mm166_alignment_gap_repair_xdk"
$out=Join-Path $root "build\\phase6_native_graphics\\apu_vp_free_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6dp_apu_vp_free.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DP input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6do-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6do=Join-Path $PSScriptRoot "Prepare-Phase6DO.ps1"
  if(-not(Test-Path -LiteralPath $prep6do)){ throw "Phase 6DP baseline missing and Phase 6DO regeneration script not found" }
  Write-Host "[Phase6DP] Cached 6DO output missing; regenerating 6DO without solution build..."
  & $prep6do -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){ throw ("Phase 6DP could not regenerate 6DO baseline. Missing: "+($missing-join", ")) }
}

$m=Get-Content (Join-Path $base "phase6do-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DO"-or$m.build_tag-ne"P6DO-MM166-ALIGNMENT-GAP-REPAIR-20261026-A"){ throw "Phase 6DP baseline identity mismatch" }

Write-Host "[Phase6DP] APU VP FREE REGISTER MODEL"
Write-Host "[Phase6DP] 6DO hardware: CCCCCCD0 eliminated; XACT root remains alive"
Write-Host "[Phase6DP] New boundary: READ32 FE820010 at tick 26,712,001"
Write-Host "[Phase6DP] FE820010 = VP offset 0010 / NV1BA0_PIO_FREE"
Write-Host "[Phase6DP] Reference behavior: return 00000080 (queue reported empty)"
Write-Host "[Phase6DP] All other FE820000-FE82FFFF reads/writes remain fenced"
Write-Host "[Phase6DP] Voice methods/audio processing/output: NOT modeled"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DP emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DP-R1"')){ throw "Phase 6DP stale emitter detected; expected revision 6DP-R1" }
Write-Host "[Phase6DP] Emitter revision       : 6DP-R1"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@("--base-dir",$base,"--base-emitter",$baseEmitter,"--phase6bl-emitter",$p6bl,"--out-dir",$out)
$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6dpEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DP] EMITTER OUTPUT:"
  $phase6dpEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DP emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6dp-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){ if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DP output: $f"} }

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DP"-or$r.build_tag-ne"P6DP-APU-VP-FREE-20261026-A"){ throw "Phase 6DP manifest identity mismatch" }
$dp=$r.phase6dp_apu_vp_free
if($dp.hardware_proof.old_failure_eliminated-ne"0xCCCCCCD0"-or
   $dp.hardware_proof.xact_final_release_observed-ne$false-or
   $dp.hardware_proof.xact_global_zero_write_observed-ne$false-or
   $dp.hardware_proof.new_boundary-ne"0xFE820010"-or
   $dp.register_identity.name-ne"NV1BA0_PIO_FREE"-or
   $dp.register_identity.read_value-ne"0x00000080"-or
   $dp.scope.exact_read32_only-ne$true-or
   $dp.scope.other_vp_reads_fenced-ne$true-or
   $dp.scope.all_vp_writes_fenced-ne$true-or
   $dp.scope.voice_methods_modeled-ne$false-or
   $dp.scope.actual_audio_processing-ne$false-or
   $dp.scope.actual_host_audio_output-ne$false-or
   $dp.xact_refcount_semantics_changed-ne$false-or
   $dp.destructor_suppressed-ne$false-or
   $dp.free_suppressed-ne$false-or
   $dp.guest_memory_fences_changed-ne$false-or
   $dp.generated_c4146_scope_inherited-ne$true-or
   $dp.execution_budget_inherited-ne64000000){ throw "Phase 6DP manifest gate failed" }

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DP-APU-VP-FREE-20261026-A","phase6dp_env_build_cookie","address == 0xFE820010u","0x00000080u",
  "NV1BA0_PIO_FREE","P6DP APU VP READ32","other_vp_accesses_fenced=1","return GUEST_READ32(address);",
  "P6DP APU CORE:","P6DP APU DSP:","#pragma warning(disable:4146)","#define PHASE4C_EXEC_BUDGET 64000000u"
)){ if(-not$text.Contains($marker)){throw "Phase 6DP source gate missing: $marker"} }

$readStart=$text.IndexOf("static uint32_t phase6ch_apu_read32(uint32_t address)")
$readEnd=$text.IndexOf("static void phase6ch_apu_write8(uint32_t address",$readStart)
if($readStart-lt0-or$readEnd-lt0-or$readEnd-le$readStart){ throw "Phase 6DP read32 helper verification bounds missing" }
$readText=$text.Substring($readStart,$readEnd-$readStart)
if(([regex]::Matches($readText,[regex]::Escape("address == 0xFE820010u"))).Count-ne1){ throw "Phase 6DP exact VP FREE gate count mismatch" }
if(([regex]::Matches($readText,[regex]::Escape("return GUEST_READ32(address);"))).Count-ne1){ throw "Phase 6DP checked read32 fallback count mismatch" }

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DP translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DP] READY"
Write-Host "[Phase6DP] Expected money line:"
Write-Host "[Phase6DP]   P6DP APU VP READ32 addr=FE820010 method=NV1BA0_PIO_FREE value=00000080 count=1"
Write-Host "[Phase6DP] Then we want a NEW VP method/register frontier, not CCCCCCD0."
Write-Host "[Phase6DP] C4146 cleanup          : inherited"
Write-Host "[Phase6DP] Other VP accesses      : fenced"
Write-Host ("[Phase6DP] Generated shards      : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main; GeneratedEnv=$env; GeneratedShardDir=$shards;
    ExpectedBuildTag="P6DP-APU-VP-FREE-20261026-A"; ExpectedEnvCookie="phase6dp_env_build_cookie";
    SolutionRoot=$SolutionRoot; Configuration="Release"; Platform="Xbox 360";
    CleanLog=(Join-Path $root "build\\phase6_native_graphics\\phase6dp-vs2017-clean.log");
    BuildLog=(Join-Path $root "build\\phase6_native_graphics\\phase6dp-vs2017-build.log");
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DP-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6DP] BUILD PASS"
  Write-Host ("[Phase6DP] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DP-A.xex"))
}
