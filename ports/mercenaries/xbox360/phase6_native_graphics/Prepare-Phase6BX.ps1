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
$base=Join-Path $root "build\\phase6_native_graphics\\keraiseirql129_xdk"
$out=Join-Path $root "build\\phase6_native_graphics\\lowkseg_origin_probe_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bx_lowkseg_origin_probe.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bw-manifest.json")
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BX input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bw-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BW"-or$m.build_tag-ne"P6BW-KERAISEIRQL129-20261024-A"){
  throw "Phase 6BX baseline identity mismatch"
}

Write-Host "[Phase6BX] LOW-KSEG ORIGIN PROBE"
Write-Host "[Phase6BX] 6BW hardware: KeRaiseIrqlToDpcLevel PASS old=0 new=2"
Write-Host "[Phase6BX] Next access: READ32 8000018D fault=1"
Write-Host "[Phase6BX] 8000018D is inside the intentionally fenced 80000000-80000FFF page"
Write-Host "[Phase6BX] Exact retail import audit has no ordinal 397 / 0x18D"
Write-Host "[Phase6BX] Policy: instrument origin only; DO NOT relax KSEG fence"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BX emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6bxEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BX] EMITTER OUTPUT:"
  $phase6bxEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6BX emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bx-manifest.json"
$shards=Join-Path $out "translated_shards"
$forensic=Join-Path $out "phase6bx-sub_0022AC56-forensic.txt"
foreach($f in @($main,$mono,$env,$manifest,$shards,$forensic)){
  if(-not(Test-Path $f)){throw "Missing Phase 6BX output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BX"-or$r.build_tag-ne"P6BX-LOWKSEG-ORIGIN-PROBE-20261024-A"){
  throw "Phase 6BX manifest identity mismatch"
}
$a=$r.phase6bx_low_kseg_origin_probe
if($a.phase6bw_hardware.ke_raise_irql_successes-ne1-or
   $a.phase6bw_hardware.guest_irql_old-ne0-or
   $a.phase6bw_hardware.guest_irql_new-ne2-or
   $a.phase6bw_hardware.fault_address-ne"0x8000018D"-or
   $a.phase6bw_hardware.fault-ne1){
  throw "Phase 6BX hardware-proof gate failed"
}
if($a.classification.inside_low_kseg_synthetic_fence-ne$true-or
   $a.classification.phase4a_exact_import_ordinal_397_present-ne$false-or
   $a.classification.do_not_route_as_kernel_export-ne$true-or
   $a.classification.low_kseg_alias_not_relaxed-ne$true){
  throw "Phase 6BX low-KSEG classification gate failed"
}
if($a.probe.non_mutating-ne$true-or
   $a.translated_membership_changed-ne$false-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false-or
   $a.execution_budget-ne8000000){
  throw "Phase 6BX inheritance/probe gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6BX LOWKSEG ORIGIN: va=%08X",
  "P6BX LOWKSEG ORIGIN: hits=%u",
  "MERC_SYNTH_FENCE_BASE",
  "MERC_SYNTH_FENCE_END",
  "phase6bx_env_build_cookie",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BX source gate missing: $marker"}
}

Write-Host "[Phase6BX] READY probe_vas=0022AC56,0022AC78,0022AC89,0022AC8F fence_unchanged=1 semantics_changed=0"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BX-LOWKSEG-ORIGIN-PROBE-20261024-A"
    ExpectedEnvCookie="phase6bx_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bx-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\\phase6_native_graphics\\phase6bx-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BX-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BX] BUILD PASS"
  Write-Host ("[Phase6BX] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BX-A.xex"))
}
