[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\d3d_pfb_tile_base_bridge_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_pfb_zcomp_bridge_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bj_pfb_zcomp_bridge.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @(
  $python,$emitter,$builder,
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bi-manifest.json"),
  (Join-Path $base "translated_shards")
)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BJ input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bi-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BI"-or$m.build_tag-ne"P6BI-PFB-TILE-BASE-BRIDGE-20261024-A"){
  throw "Phase 6BJ baseline identity mismatch"
}

Write-Host "[Phase6BJ] PFB ZCOMP BRIDGE"
Write-Host "[Phase6BJ] 6BI crossed tile1 BASE write/readback and PGRAPH state readback"
Write-Host "[Phase6BJ] next access WRITE32 FD100304 = PFB ZCOMP tile1 value 84000000"
Write-Host "[Phase6BJ] documented companion offset is FD100324"
Write-Host "[Phase6BJ] Bridge only these ZCOMP dwords through sub_00292586's scoped wrapper"
Write-Host "[Phase6BJ] All unrelated MMIO/VRAM remains fenced"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BJ emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out 2>&1 | Tee-Object -Variable phase6bjEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BJ] EMITTER OUTPUT:"
  $phase6bjEmitOutput | ForEach-Object { Write-Host $_ }
  throw "Phase 6BJ emission failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bj-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BJ output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BJ"-or$r.build_tag-ne"P6BJ-PFB-ZCOMP-BRIDGE-20261024-A"){
  throw "Phase 6BJ manifest identity mismatch"
}
$g=$r.phase6bj_pfb_zcomp_bridge
if($g.hardware_proof.next_mmio_access-ne"WRITE32 0xFD100304" -or
   $g.hardware_proof.next_mmio_value-ne"0x84000000" -or
   $g.register_semantics.pfb_zcomp_offset-ne"0xFD100324" -or
   $g.pfb_tile_scope_unchanged-ne$true -or
   $g.pgraph_scope_unchanged-ne$true -or
   $g.all_other_mmio_fenced-ne$true -or
   $g.vram_fence_changed-ne$false -or
   $g.allocator_policy_changed-ne$false){
  throw "Phase 6BJ semantic/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6BJ-PFB-ZCOMP-BRIDGE-20261024-A",
  "phase6bj_env_build_cookie",
  "phase6bj_pfb_zcomp_address",
  "phase6bj_pfb_zcomp_write32",
  "phase6bj_pfb_zcomp_read32",
  "0xFD100300u",
  "0xFD100324u",
  "phase6bg_pfb_tile_write32",
  "phase6bh_pgraph_scoped_write32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BJ source gate missing: $marker"}
}

Write-Host "[Phase6BJ] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BJ-PFB-ZCOMP-BRIDGE-20261024-A"
    ExpectedEnvCookie="phase6bj_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bj-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bj-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BJ-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BJ] BUILD PASS"
  Write-Host ("[Phase6BJ] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BJ-A.xex"))
}
