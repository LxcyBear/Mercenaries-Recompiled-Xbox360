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
$stage3=Join-Path $root "build\phase3n_final_abi_scale"
$base=Join-Path $root "build\phase6_native_graphics\read32_ccccccd0_probe_xdk"
$out=Join-Path $root "build\phase6_native_graphics\prefault_ccccccd0_provenance_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6cz_prefault_ccccccd0.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$generatedRoot=Join-Path $stage3 "runtime\gen"
$functions=Join-Path $stage3 "analysis\disasm\functions.json"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder,$generatedRoot,$functions)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CZ input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cy-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cy=Join-Path $PSScriptRoot "Prepare-Phase6CY.ps1"
  if(-not(Test-Path -LiteralPath $prep6cy)){
    throw "Phase 6CZ baseline missing and Phase 6CY regeneration script not found"
  }
  Write-Host "[Phase6CZ] Cached 6CY output missing; regenerating 6CY without solution build..."
  & $prep6cy -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CZ could not regenerate 6CY baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cy-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CY"-or$m.build_tag-ne"P6CY-READ32-CCCCCCD0-SITE-20261026-A"){
  throw "Phase 6CZ baseline identity mismatch"
}
$cy=$m.phase6cy_read32_ccccccd0_probe
if($cy.probe_only-ne$true-or
   $cy.guest_memory_semantics_changed-ne$false-or
   $cy.execution_budget_inherited-ne64000000-or
   $cy.exfreepool_itail_preserved-ne$true-or
   $cy.manual_dsound_decrypt_preserved-ne$true-or
   $cy.hard_fences_weakened-ne$false){
  throw "Phase 6CZ inherited 6CY policy mismatch"
}

Write-Host "[Phase6CZ] CCCCCCCC KILL-SHOT PROVENANCE"
Write-Host "[Phase6CZ] 6CY hardware reproduced READ32 CCCCCCD0 at tick 27021609"
Write-Host "[Phase6CZ] Correction: 6CY post-read report was unreachable after router longjmp"
Write-Host "[Phase6CZ] New probe: log BEFORE CCCCCCD0 enters checked guest router"
Write-Host "[Phase6CZ] Coverage: translated READ32 + maintained/manual/support READ32"
Write-Host "[Phase6CZ] Static audit: resolve final DSOUND VA ring 002A41EE / 002A41F7"
Write-Host "[Phase6CZ] Value fabrication: NONE"
Write-Host "[Phase6CZ] Address widening: NONE"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CZ emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CZ-R1"')){
  throw "Phase 6CZ stale emitter detected; expected revision 6CZ-R1"
}
Write-Host "[Phase6CZ] Emitter revision       : 6CZ-R1"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@("--base-dir",$base,"--base-emitter",$baseEmitter,"--phase6bl-emitter",$p6bl,"--generated-root",$generatedRoot,"--functions",$functions,"--out-dir",$out)
$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6czEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CZ] EMITTER OUTPUT:"
  $phase6czEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CZ emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cz-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CZ output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CZ"-or$r.build_tag-ne"P6CZ-PREFAULT-CCCCCCD0-PROVENANCE-20261026-A"){
  throw "Phase 6CZ manifest identity mismatch"
}
$z=$r.phase6cz_prefault_ccccccd0_provenance
if($z.phase6cy_hardware.fault_address-ne"0xCCCCCCD0"-or
   $z.phase6cy_hardware.eax-ne"0xCCCCCCCC"-or
   $z.phase6cy_hardware.ticks-ne27021609-or
   $z.translated_prefault_probe-ne$true-or
   $z.support_prefault_probe-ne$true-or
   $z.guest_memory_semantics_changed-ne$false-or
   $z.value_fabrication-ne$false-or
   $z.address_range_widened-ne$false-or
   $z.execution_budget_inherited-ne64000000-or
   $z.exfreepool_itail_preserved-ne$true-or
   $z.manual_dsound_decrypt_preserved-ne$true-or
   $z.hard_fences_weakened-ne$false){
  throw "Phase 6CZ manifest gate failed"
}
if(([int]$z.support_guest_read32_sites+[int]$z.support_direct_read32_sites)-lt1){
  throw "Phase 6CZ found no support-side READ32 sites"
}
if(@($z.final_va_source_audit.rows).Count-ne2){
  throw "Phase 6CZ final-VA source audit did not resolve two target VAs"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CZ-PREFAULT-CCCCCCD0-PROVENANCE-20261026-A",
  "phase6cz_env_build_cookie",
  "P6CZ PREFAULT TRANSLATED READ32:",
  "P6CZ PREFAULT SUPPORT READ32:",
  "P6CZ PREFAULT PROVENANCE:",
  "PASS: Phase 6CZ ExFreePool ITAIL",
  "PASS: Phase 6CZ manual DSOUND decrypt",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "P6CZ APU CORE:",
  "P6CZ AV/DISPLAY SUMMARY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CZ source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CZ translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6CZ] READY"
Write-Host ("[Phase6CZ] Support GUEST_READ32 sites     : {0}" -f [int]$z.support_guest_read32_sites)
Write-Host ("[Phase6CZ] Support direct READ32 sites    : {0}" -f [int]$z.support_direct_read32_sites)
foreach($row in @($z.final_va_source_audit.rows)){
  Write-Host ("[Phase6CZ] Final VA {0} owner={1} start={2} generated={3}" -f $row.va,$row.owner_name,$row.owner_start,$row.generated)
  foreach($line in @($row.context)){Write-Host ("[Phase6CZ]   "+$line)}
}
Write-Host "[Phase6CZ] Money line will identify TRANSLATED or SUPPORT provenance before fault"
Write-Host "[Phase6CZ] Guest-memory semantics         : unchanged"
Write-Host "[Phase6CZ] CCCCCCD0 fabrication           : NO"
Write-Host "[Phase6CZ] ExFreePool / DSOUND / APU/GPU  : preserved"
Write-Host ("[Phase6CZ] Generated shards               : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CZ-PREFAULT-CCCCCCD0-PROVENANCE-20261026-A"
    ExpectedEnvCookie="phase6cz_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cz-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cz-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CZ-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CZ] BUILD PASS"
  Write-Host ("[Phase6CZ] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CZ-A.xex"))
}
