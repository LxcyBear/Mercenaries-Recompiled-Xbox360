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
$base=Join-Path $root "build\phase6_native_graphics\xact_280c39_arg1_internal_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_global_0028836c_provenance_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6de_xact_global_0028836c.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$generatedRoot=Join-Path $stage3 "runtime\gen"
$functions=Join-Path $stage3 "analysis\disasm\functions.json"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder,$generatedRoot,$functions)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DE input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6dd-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6dd=Join-Path $PSScriptRoot "Prepare-Phase6DD.ps1"
  if(-not(Test-Path -LiteralPath $prep6dd)){
    throw "Phase 6DE baseline missing and Phase 6DD regeneration script not found"
  }

  Write-Host "[Phase6DE] Cached 6DD output missing; regenerating 6DD without solution build..."
  & $prep6dd -SkipSolutionBuild

  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DE could not regenerate 6DD baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6dd-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DD"-or$m.build_tag-ne"P6DD-XACT-280C39-ARG1-INTERNAL-20261026-A"){
  throw "Phase 6DE baseline identity mismatch"
}

$dd=$m.phase6dd_xact_280c39_internal
if($dd.probe_only-ne$true-or
   $dd.guest_memory_semantics_changed-ne$false-or
   $dd.value_fabrication-ne$false-or
   $dd.fault_suppression-ne$false-or
   $dd.address_range_widened-ne$false-or
   $dd.execution_budget_inherited-ne64000000-or
   $dd.hard_fences_weakened-ne$false){
  throw "Phase 6DE inherited 6DD policy mismatch"
}

Write-Host "[Phase6DE] XACT GLOBAL 0028836C INITIALIZATION PROVENANCE"
Write-Host "[Phase6DE] 6DD hardware: 00280CD2 read 0028836C -> 00000000"
Write-Host "[Phase6DE] 6DD hardware: 00280CF5 read 00000010 -> 00041D90"
Write-Host "[Phase6DE] New probe: full generated-source reader/writer audit + central WRITE32 watch"
Write-Host "[Phase6DE] Pointer substitution: NONE"
Write-Host "[Phase6DE] Fault suppression: NONE"
Write-Host "[Phase6DE] Address widening: NONE"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DE emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DE-R5"')){
  throw "Phase 6DE stale emitter detected; expected revision 6DE-R5"
}
if(-not$emitterText.Contains('wrapper_match = WRITE32_DEF_RE.search(main_text)')){
  throw "Phase 6DE shared WRITE32 compile-order matcher gate failed"
}
Write-Host "[Phase6DE] Emitter revision       : 6DE-R5"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",$baseEmitter,
  "--phase6bl-emitter",$p6bl,
  "--generated-root",$generatedRoot,
  "--functions",$functions,
  "--out-dir",$out
)

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6deEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DE] EMITTER OUTPUT:"
  $phase6deEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DE emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6de-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DE output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DE"-or$r.build_tag-ne"P6DE-XACT-GLOBAL-0028836C-PROVENANCE-20261026-A"){
  throw "Phase 6DE manifest identity mismatch"
}

$de=$r.phase6de_xact_global_0028836c
if($de.hardware_proof.global_address-ne"0x0028836C"-or
   $de.hardware_proof.global_value-ne"0x00000000"-or
   $de.hardware_proof.null_read_address-ne"0x00000010"-or
   $de.hardware_proof.null_read_value-ne"0x00041D90"-or
   $de.hardware_proof.fault_address-ne"0xCCCCCCD0"-or
   $de.central_write_watch-ne$true-or
   $de.probe_only-ne$true-or
   $de.guest_memory_semantics_changed-ne$false-or
   $de.value_fabrication-ne$false-or
   $de.fault_suppression-ne$false-or
   $de.address_range_widened-ne$false-or
   $de.execution_budget_inherited-ne64000000-or
   $de.hard_fences_weakened-ne$false){
  throw "Phase 6DE manifest gate failed"
}

if(@($de.site_audit.context).Count-lt1){
  throw "Phase 6DE 00280CF5 source context is empty"
}

$text=Get-Content $mono -Raw
$statePos=$text.IndexOf("static DWORD s_phase6deGlobalWriteReports = 0u;")
$write32Match=[regex]::Match(
  $text,
  '(?m)^void\s+recomp_guest_write32\(uint32_t address, uint32_t value\)\s*\{'
)
$write32Pos=if($write32Match.Success){$write32Match.Index}else{-1}
if($statePos-lt0-or$write32Pos-lt0-or$statePos-gt$write32Pos){
  throw "Phase 6DE compile-order gate failed: WRITE32 telemetry state must precede wrapper definition"
}
Write-Host "[Phase6DE] WRITE32 compile order      : PASS"
foreach($marker in @(
  "P6DE-XACT-GLOBAL-0028836C-PROVENANCE-20261026-A",
  "phase6de_env_build_cookie",
  "P6DE XACT GLOBAL WRITE32:",
  "P6DE XACT GLOBAL 0028836C:",
  "P6DE 280C39 READ32:",
  "P6DE 280C39 INTERNAL:",
  "P6DE FBE2 CALLER:",
  "P6DE PREFAULT ROUTER READ32:",
  "PASS: Phase 6DE ExFreePool ITAIL",
  "PASS: Phase 6DE manual DSOUND decrypt",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "P6DE APU CORE:",
  "P6DE AV/DISPLAY SUMMARY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DE source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DE translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DE] READY"
Write-Host ("[Phase6DE] Generated 0028836C refs : {0}" -f $de.generated_reference_audit.match_count)
Write-Host ("[Phase6DE] Reader candidates      : {0}" -f $de.generated_reference_audit.reader_count)
Write-Host ("[Phase6DE] Writer candidates      : {0}" -f $de.generated_reference_audit.writer_count)
Write-Host "[Phase6DE] 00280CF5 source context:"
foreach($row in @($de.site_audit.context)){
  $mark=if($row.line-eq$de.site_audit.site10.source_line){">>"}else{"  "}
  Write-Host ("[Phase6DE] {0} {1:D3}: {2}" -f $mark,[int]$row.line,$row.text)
}
foreach($row in @($de.generated_reference_audit.matches)){
  Write-Host ("[Phase6DE] GLOBAL REF {0} owner={1} {2} line={3}: {4}" -f $row.kind,$row.owner_start,$row.owner_name,$row.line,$row.source)
}
Write-Host "[Phase6DE] Money line if 0028836C is written:"
Write-Host "[Phase6DE]   P6DE XACT GLOBAL WRITE32: caller=... address=0028836C value=..."
Write-Host "[Phase6DE] If final summary says writes=0, the runtime never initialized this global before the bad read."
Write-Host "[Phase6DE] Guest-memory semantics : unchanged"
Write-Host "[Phase6DE] Pointer fabrication    : NO"
Write-Host "[Phase6DE] Fault suppression      : NO"
Write-Host ("[Phase6DE] Generated shards       : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DE-XACT-GLOBAL-0028836C-PROVENANCE-20261026-A"
    ExpectedEnvCookie="phase6de_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6de-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6de-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DE-A.xex")
  }

  & $builder @buildArgs
  Write-Host "[Phase6DE] BUILD PASS"
  Write-Host ("[Phase6DE] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DE-A.xex"))
}
