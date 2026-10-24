[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\d3d_pfifo_idle_bridge_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_pgraph_idle700_bridge_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bf_pgraph_idle700_bridge.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @(
  $python,$emitter,$builder,
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6be-manifest.json"),
  (Join-Path $base "translated_shards")
)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BF input: $f"}
}

$m=Get-Content (Join-Path $base "phase6be-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BE"-or$m.build_tag-ne"P6BE-PFIFO-IDLE-BRIDGE-20261024-A"){
  throw "Phase 6BF baseline identity mismatch"
}

Write-Host "[Phase6BF] PGRAPH 0x700 IDLE-STATUS BRIDGE"
Write-Host "[Phase6BF] 6BE hardware: PFIFO wait completed and next access is READ32 FD400700"
Write-Host "[Phase6BF] Existing NV2A backend documents PGRAPH+0x700 as XDK idle-status and returns zero-initialized state"
Write-Host "[Phase6BF] Only that exact read is bridged; every other MMIO/VRAM access remains fenced"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BF emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out
if($LASTEXITCODE-ne0){throw "Phase 6BF emission failed"}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bf-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BF output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BF"-or$r.build_tag-ne"P6BF-PGRAPH-IDLE700-BRIDGE-20261024-A"){
  throw "Phase 6BF manifest identity mismatch"
}
if($r.phase6bf_pgraph_idle700_bridge.all_other_mmio_fenced-ne$true -or
   $r.phase6bf_pgraph_idle700_bridge.mmio_global_fence_changed-ne$false -or
   $r.phase6bf_pgraph_idle700_bridge.vram_fence_changed-ne$false -or
   $r.phase6bf_pgraph_idle700_bridge.bridge_value-ne"0x00000000"){
  throw "Phase 6BF semantic/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6BF-PGRAPH-IDLE700-BRIDGE-20261024-A",
  "phase6bf_env_build_cookie",
  "P6BF PGRAPH IDLE700 READ32",
  "0xFD400700u",
  "phase6bf_pgraph_idle700_read32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BF source gate missing: $marker"}
}

$patchedShardCount=0
Get-ChildItem $shards -Filter "*.inl" | ForEach-Object {
  $s=Get-Content $_.FullName -Raw
  if($s.Contains("phase6bf_pgraph_idle700_read32")){$patchedShardCount++}
}
if($patchedShardCount-ne1){
  throw "Phase 6BF expected exactly one patched shard, found $patchedShardCount"
}

Write-Host "[Phase6BF] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BF-PGRAPH-IDLE700-BRIDGE-20261024-A"
    ExpectedEnvCookie="phase6bf_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bf-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bf-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BF-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BF] BUILD PASS"
  Write-Host ("[Phase6BF] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BF-A.xex"))
}
