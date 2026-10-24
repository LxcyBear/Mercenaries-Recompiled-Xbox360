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
$base=Join-Path $root "build\\phase6_native_graphics\\lowkseg_origin_probe_xdk"
$out=Join-Path $root "build\\phase6_native_graphics\\idex357_data_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6by_idex357_data.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bx-manifest.json")
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BY input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bx-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BX"-or$m.build_tag-ne"P6BX-LOWKSEG-ORIGIN-PROBE-20261024-A"){
  throw "Phase 6BY baseline identity mismatch"
}

Write-Host "[Phase6BY] IDEXCHANNELOBJECT ORDINAL 357 DATA RELOCATION"
Write-Host "[Phase6BY] 6BX hardware: 0022AC8F loads slot 002DBDBC then faults READ32 8000018D"
Write-Host "[Phase6BY] Phase-4A exact slot identity: 55 / ordinal 357 / IdexChannelObject / DATA"
Write-Host "[Phase6BY] Guest model: thunk -> 0087E0A0 pointer slot -> 0087E0A4 IDEX object"
Write-Host "[Phase6BY] Policy: DO NOT relax low-KSEG fence"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BY emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6byEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BY] EMITTER OUTPUT:"
  $phase6byEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6BY emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6by-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6BY output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BY"-or$r.build_tag-ne"P6BY-IDEX357-DATA-20261024-A"){
  throw "Phase 6BY manifest identity mismatch"
}
$a=$r.phase6by_idex357_data
if($a.phase6bx_hardware.probe_hits-ne4-or
   $a.phase6bx_hardware.last_probe_edx_before_slot_load-ne"0x00406298"-or
   $a.phase6bx_hardware.boundary_edx_after_slot_load-ne"0x8000018D"-or
   $a.phase6bx_hardware.fault_address-ne"0x8000018D"-or
   $a.phase6bx_hardware.fault-ne1-or
   $a.phase6bx_hardware.xapi_return-ne0){
  throw "Phase 6BY 6BX-hardware proof gate failed"
}
if($a.phase4a_identity.thunk_slot-ne55-or
   $a.phase4a_identity.thunk_va-ne"0x002DBDBC"-or
   $a.phase4a_identity.ordinal-ne357-or
   $a.phase4a_identity.name-ne"IdexChannelObject"-or
   $a.phase4a_identity.kind-ne"data"){
  throw "Phase 6BY Phase-4A identity gate failed"
}
if($a.continuation.raw_ordinal_token_expected-ne"0x80000165"-or
   $a.continuation.pointer_slot_va-ne"0x0087E0A0"-or
   $a.continuation.object_va-ne"0x0087E0A4"-or
   $a.continuation.object_marker-ne"0x49444558"-or
   $a.continuation.pointer_valued_data_export-ne$true-or
   $a.continuation.low_kseg_fence_changed-ne$false-or
   $a.continuation.phase5_env_semantics_changed-ne$false){
  throw "Phase 6BY Idex DATA-model gate failed"
}
if($a.translated_membership_changed-ne$false-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false-or
   $a.execution_budget-ne8000000){
  throw "Phase 6BY inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "case 357u: return 0x0087E0A0u",
  "GUEST_WRITE32(0x0087E0A0u, 0x0087E0A4u)",
  "GUEST_WRITE32(0x0087E0A4u, 0x49444558u)",
  "idexThunkBefore != 0x80000165u",
  "if (ordinal == 357u) ++seen357",
  "P6BY IDEX LIVE THUNK:",
  "P6BY IDEX LIVE OBJECT:",
  "phase6by_env_build_cookie",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BY source gate missing: $marker"}
}

Write-Host "[Phase6BY] READY ordinal=357 thunk=002DBDBC pointer_slot=0087E0A0 object=0087E0A4 marker=49444558 kseg_fence_unchanged=1"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BY-IDEX357-DATA-20261024-A"
    ExpectedEnvCookie="phase6by_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\\phase6_native_graphics\\phase6by-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\\phase6_native_graphics\\phase6by-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BY-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BY] BUILD PASS"
  Write-Host ("[Phase6BY] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BY-A.xex"))
}
