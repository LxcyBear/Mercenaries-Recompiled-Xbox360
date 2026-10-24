[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\d3d_pgraph_state_bridge_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_pfb_tile_base_bridge_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bi_pfb_tile_base_bridge.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @(
  $python,$emitter,$builder,
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bh-manifest.json"),
  (Join-Path $base "translated_shards")
)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BI input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bh-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BH"-or$m.build_tag-ne"P6BH-PGRAPH-STATE-BRIDGE-20261024-A"){
  throw "Phase 6BI baseline identity mismatch"
}

Write-Host "[Phase6BI] PFB TILE BASE BRIDGE"
Write-Host "[Phase6BI] 6BH hardware crossed PGRAPH writes FD400914/918/910"
Write-Host "[Phase6BI] next access WRITE32 FD100250 = tile1 BASE=024FC003"
Write-Host "[Phase6BI] Reuse the documented PFB tile BASE/LIMIT/PITCH shadow helper only inside sub_00292586"
Write-Host "[Phase6BI] Other functions and unrelated MMIO/VRAM remain fenced"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BI emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out 2>&1 | Tee-Object -Variable phase6biEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BI] EMITTER OUTPUT:"
  $phase6biEmitOutput | ForEach-Object { Write-Host $_ }
  throw "Phase 6BI emission failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bi-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BI output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BI"-or$r.build_tag-ne"P6BI-PFB-TILE-BASE-BRIDGE-20261024-A"){
  throw "Phase 6BI manifest identity mismatch"
}
$g=$r.phase6bi_pfb_tile_base_bridge
if($g.hardware_proof.next_mmio_access-ne"WRITE32 0xFD100250" -or
   $g.hardware_proof.next_mmio_value-ne"0x024FC003" -or
   $g.pgraph_scope_unchanged-ne$true -or
   $g.other_functions_mmio_fenced-ne$true -or
   $g.vram_fence_changed-ne$false -or
   $g.allocator_policy_changed-ne$false){
  throw "Phase 6BI semantic/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6BI-PFB-TILE-BASE-BRIDGE-20261024-A",
  "phase6bi_env_build_cookie",
  "phase6bg_pfb_tile_address(address, NULL)",
  "phase6bg_pfb_tile_write32(address, value)",
  "phase6bg_pfb_tile_read32(address)",
  "phase6bh_pgraph_scoped_write32",
  "phase6bh_pgraph_scoped_read32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BI source gate missing: $marker"}
}

Write-Host "[Phase6BI] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BI-PFB-TILE-BASE-BRIDGE-20261024-A"
    ExpectedEnvCookie="phase6bi_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bi-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bi-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BI-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BI] BUILD PASS"
  Write-Host ("[Phase6BI] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BI-A.xex"))
}
