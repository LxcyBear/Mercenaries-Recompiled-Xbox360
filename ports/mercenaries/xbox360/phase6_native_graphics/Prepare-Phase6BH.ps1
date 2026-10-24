[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\d3d_pfb_tile_bridge_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_pgraph_state_bridge_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bh_pgraph_state_bridge.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @(
  $python,$emitter,$builder,
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bg-manifest.json"),
  (Join-Path $base "translated_shards")
)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BH input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bg-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BG"-or$m.build_tag-ne"P6BG-PFB-TILE-BRIDGE-20261024-A"){
  throw "Phase 6BH baseline identity mismatch"
}

Write-Host "[Phase6BH] PGRAPH SCOPED STATE BRIDGE"
Write-Host "[Phase6BH] 6BG hardware crossed tile1 LIMIT=02627FFF and PITCH=00000A00"
Write-Host "[Phase6BH] next access WRITE32 FD400914 inside sub_00292586"
Write-Host "[Phase6BH] Mirror maintained backend generic PGRAPH store/readback semantics only in that function"
Write-Host "[Phase6BH] Other functions and every unrelated MMIO/VRAM access remain fenced"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BH emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out 2>&1 | Tee-Object -Variable phase6bhEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BH] EMITTER OUTPUT:"
  $phase6bhEmitOutput | ForEach-Object { Write-Host $_ }
  throw "Phase 6BH emission failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bh-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BH output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BH"-or$r.build_tag-ne"P6BH-PGRAPH-STATE-BRIDGE-20261024-A"){
  throw "Phase 6BH manifest identity mismatch"
}
$g=$r.phase6bh_pgraph_state_bridge
if($g.hardware_proof.next_mmio_access-ne"WRITE32 0xFD400914" -or
   $g.scope.function-ne"sub_00292586" -or
   $g.scope.access_width-ne4 -or
   $g.scope.raw_write_sites_wrapped-lt1 -or
   $g.scope.raw_read_sites_wrapped-lt1 -or
   $g.all_other_mmio_fenced-ne$true -or
   $g.other_functions_pgraph_fenced-ne$true -or
   $g.vram_fence_changed-ne$false -or
   $g.allocator_policy_changed-ne$false){
  throw "Phase 6BH semantic/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6BH-PGRAPH-STATE-BRIDGE-20261024-A",
  "phase6bh_env_build_cookie",
  "P6BH PGRAPH WRITE32",
  "P6BH PGRAPH READ32",
  "0xFD400000u",
  "0xFD402000u",
  "phase6bh_pgraph_scoped_write32",
  "phase6bh_pgraph_scoped_read32",
  "phase6bg_pfb_tile_write32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BH source gate missing: $marker"}
}

$patchedShardCount=0
Get-ChildItem $shards -Filter "*.inl" | ForEach-Object {
  $s=Get-Content $_.FullName -Raw
  if($s.Contains("phase6bh_pgraph_scoped_write32")){$patchedShardCount++}
}
if($patchedShardCount-ne1){
  throw "Phase 6BH expected exactly one patched shard, found $patchedShardCount"
}

Write-Host "[Phase6BH] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BH-PGRAPH-STATE-BRIDGE-20261024-A"
    ExpectedEnvCookie="phase6bh_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bh-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bh-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BH-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BH] BUILD PASS"
  Write-Host ("[Phase6BH] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BH-A.xex"))
}
