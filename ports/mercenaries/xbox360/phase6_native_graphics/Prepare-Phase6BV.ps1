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
$base=Join-Path $root "build\\phase6_native_graphics\\obref246_probe_xdk"
$out=Join-Path $root "build\\phase6_native_graphics\\fileobject_first_deref_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bv_fileobject_first_deref.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bu-manifest.json")
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BV input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bu-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BU"-or$m.build_tag-ne"P6BU-OBREF246-PROBE-20261024-A"){
  throw "Phase 6BV baseline identity mismatch"
}

Write-Host "[Phase6BV] FILE_OBJECT FIRST-DEREFERENCE PROBE"
Write-Host "[Phase6BV] 6BU hardware: handle=48000001 path=game:\xesrb.tga object_type=80000047"
Write-Host "[Phase6BV] 80000047 = ordinal 71 IoFileObjectType"
Write-Host "[Phase6BV] Canonical ordinal-246 frame: 16 bytes, fault=0"
Write-Host "[Phase6BV] Diagnostic policy: return STATUS_SUCCESS and unmapped FILE_OBJECT sentinel 04000000"
Write-Host "[Phase6BV] Goal: next checked guest access reveals exact FILE_OBJECT field offset"
Write-Host "[Phase6BV] No final FILE_OBJECT semantics are fabricated"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BV emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6bvEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BV] EMITTER OUTPUT:"
  $phase6bvEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6BV emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bv-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6BV output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BV"-or$r.build_tag-ne"P6BV-FILEOBJECT-FIRST-DEREF-20261024-A"){
  throw "Phase 6BV manifest identity mismatch"
}
$a=$r.phase6bv_fileobject_first_deref
if($a.phase6bu_hardware.handle-ne"0x48000001"-or
   $a.phase6bu_hardware.handle_resolved-ne$true-or
   $a.phase6bu_hardware.object_type-ne"0x80000047"-or
   $a.phase6bu_hardware.object_type_export_ordinal-ne71-or
   $a.phase6bu_hardware.frame_bytes-ne16-or
   $a.phase6bu_hardware.fault-ne0){
  throw "Phase 6BV hardware-proof gate failed"
}
if($a.diagnostic_continuation.returned_guest_pointer-ne"0x04000000"-or
   $a.diagnostic_continuation.sentinel_is_exact_one_past_guest_arena-ne$true-or
   $a.diagnostic_continuation.final_file_object_model-ne$false){
  throw "Phase 6BV sentinel-policy gate failed"
}
if($a.translated_membership_changed-ne$false-or
   $a.all_phase6bu_file_delay_gpu_invariants_inherited-ne$true-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false-or
   $a.execution_budget-ne8000000){
  throw "Phase 6BV inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
  "objectType != 0x80000047u",
  "PASS: Phase 6BV ObReferenceObjectByHandle diagnostic continuation",
  "P6BV OBREF246 SENTINEL:",
  "P6BV KEDELAY99:",
  "phase6bv_env_build_cookie",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BV source gate missing: $marker"}
}

Write-Host "[Phase6BV] READY ordinal=246 object_type=80000047 sentinel=04000000 first_deref_probe=1"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BV-FILEOBJECT-FIRST-DEREF-20261024-A"
    ExpectedEnvCookie="phase6bv_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bv-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bv-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BV-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BV] BUILD PASS"
  Write-Host ("[Phase6BV] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BV-A.xex"))
}
