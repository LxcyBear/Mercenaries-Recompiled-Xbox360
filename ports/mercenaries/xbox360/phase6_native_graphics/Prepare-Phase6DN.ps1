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
$base=Join-Path $root "build\phase6_native_graphics\xact_release_pretrace_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_mm166_subpage_repair_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6dn_xact_mm166_subpage_repair.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DN input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6dk-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6dk=Join-Path $PSScriptRoot "Prepare-Phase6DK.ps1"
  if(-not(Test-Path -LiteralPath $prep6dk)){
    throw "Phase 6DN baseline missing and Phase 6DK regeneration script not found"
  }

  Write-Host "[Phase6DN] Cached 6DK output missing; regenerating 6DK without solution build..."
  & $prep6dk -SkipSolutionBuild

  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DN could not regenerate 6DK baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6dk-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DK"-or$m.build_tag-ne"P6DK-XACT-RELEASE-PRETRACE-20261026-A"){
  throw "Phase 6DN baseline identity mismatch"
}

Write-Host "[Phase6DN] XACT MM166 SUBPAGE REPAIR"
Write-Host "[Phase6DN] Hardware: 0027F3DC -> 0027DC5B returned 8007000E"
Write-Host "[Phase6DN] Immediately preceding Mm166: size=4 align=4096 protect=4 base=0"
Write-Host "[Phase6DN] Repair: permit nonzero canonical +24 requests in safe tail fallback"
Write-Host "[Phase6DN] Retained: align>=4096, power-of-two, low=0, high=FFFFFFFF, protect=4"
Write-Host "[Phase6DN] Retained: exact free-tail/live-heap/unmanaged-page safety checks"
Write-Host "[Phase6DN] 96-byte align=4 audio fallback remains fenced"
Write-Host "[Phase6DN] XACT refcount/destructor/free semantics: UNCHANGED"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DN emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DN-R1"')){
  throw "Phase 6DN stale emitter detected; expected revision 6DN-R1"
}
Write-Host "[Phase6DN] Emitter revision       : 6DN-R1"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",$baseEmitter,
  "--phase6bl-emitter",$p6bl,
  "--out-dir",$out
)

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6dnEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DN] EMITTER OUTPUT:"
  $phase6dnEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DN emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6dn-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DN output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DN"-or$r.build_tag-ne"P6DN-XACT-MM166-SUBPAGE-REPAIR-20261026-A"){
  throw "Phase 6DN manifest identity mismatch"
}

$dn=$r.phase6dn_xact_mm166_subpage_repair
if($dn.hardware_proof.factory-ne"0x0027F3DC"-or
   $dn.hardware_proof.initializer-ne"0x0027DC5B"-or
   $dn.hardware_proof.failure_hresult-ne"0x8007000E"-or
   $dn.hardware_proof.request_size-ne4-or
   $dn.hardware_proof.alignment-ne4096-or
   $dn.repair.old_minimum_requested_size-ne4096-or
   $dn.repair.new_minimum_requested_size-ne1-or
   $dn.repair.page_rounding_unchanged-ne$true-or
   $dn.repair.minimum_alignment-ne4096-or
   $dn.repair.alignment_power_of_two_required-ne$true-or
   $dn.repair.audio_96_align4_still_ineligible-ne$true-or
   $dn.xact_refcount_semantics_changed-ne$false-or
   $dn.destructor_suppressed-ne$false-or
   $dn.free_suppressed-ne$false-or
   $dn.dispatch_semantics_changed-ne$false-or
   $dn.guest_memory_fences_changed-ne$false-or
   $dn.generated_c4146_scope_inherited-ne$true-or
   $dn.execution_budget_inherited-ne64000000){
  throw "Phase 6DN manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DN-XACT-MM166-SUBPAGE-REPAIR-20261026-A",
  "phase6dn_env_build_cookie",
  "size!=0u",
  "align>=0x00001000u",
  "(align & (align - 1u))==0u",
  "frameBytes==24u",
  "PASS: Phase 6DN canonical subpage Mm166 tail claim",
  "P6DN XACT RELEASE PRETRACE:",
  "P6DN XACT GLOBAL WRITE SITE:",
  "#pragma warning(disable:4146)",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DN source gate missing: $marker"}
}

$gate = @"
frameBytes==24u &&
           low==0u &&
           high==0xFFFFFFFFu &&
           prot==0x00000004u &&
           size!=0u &&
           align>=0x00001000u &&
"@
if(-not$text.Contains($gate)){
  throw "Phase 6DN canonical subpage gate shape mismatch"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DN translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DN] READY"
Write-Host "[Phase6DN] Expected money line:"
Write-Host "[Phase6DN]   PASS: Phase 6DN canonical subpage Mm166 tail claim requested=4 rounded=4096 align=4096 base=..."
Write-Host "[Phase6DN] Then we want 0027F3DC to avoid its 8007000E cleanup path."
Write-Host "[Phase6DN] C4146 cleanup           : inherited"
Write-Host "[Phase6DN] XACT teardown suppression: NONE"
Write-Host ("[Phase6DN] Generated shards        : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DN-XACT-MM166-SUBPAGE-REPAIR-20261026-A"
    ExpectedEnvCookie="phase6dn_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6dn-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6dn-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DN-A.xex")
  }

  & $builder @buildArgs
  Write-Host "[Phase6DN] BUILD PASS"
  Write-Host ("[Phase6DN] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DN-A.xex"))
}
