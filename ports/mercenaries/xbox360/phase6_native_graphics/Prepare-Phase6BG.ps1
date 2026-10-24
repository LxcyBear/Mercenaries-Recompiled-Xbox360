[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\d3d_pgraph_idle700_bridge_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_pfb_tile_bridge_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bg_pfb_tile_bridge.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @(
  $python,$emitter,$builder,
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bf-manifest.json"),
  (Join-Path $base "translated_shards")
)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BG input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bf-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BF"-or$m.build_tag-ne"P6BF-PGRAPH-IDLE700-BRIDGE-20261024-A"){
  throw "Phase 6BG baseline identity mismatch"
}

Write-Host "[Phase6BG] PFB TILE-STATE BRIDGE"
Write-Host "[Phase6BG] 6BF hardware crossed PGRAPH 0x700 twice"
Write-Host "[Phase6BG] next access WRITE32 FD100254 = tile1 LIMIT=02627FFF"
Write-Host "[Phase6BG] 02627FFF exactly matches allocation 024FC000 + 1228800 - 1"
Write-Host "[Phase6BG] Shadow only documented PFB tile base/limit/pitch fields; all other MMIO/VRAM stays fenced"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BG emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out 2>&1 | Tee-Object -Variable phase6bgEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BG] EMITTER OUTPUT:"
  $phase6bgEmitOutput | ForEach-Object { Write-Host $_ }
  throw "Phase 6BG emission failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bg-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BG output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BG"-or$r.build_tag-ne"P6BG-PFB-TILE-BRIDGE-20261024-A"){
  throw "Phase 6BG manifest identity mismatch"
}
$g=$r.phase6bg_pfb_tile_bridge
if($g.current_observation.limit_address-ne"0xFD100254" -or
   $g.current_observation.limit_value-ne"0x02627FFF" -or
   $g.all_other_mmio_fenced-ne$true -or
   $g.mmio_global_fence_changed-ne$false -or
   $g.vram_fence_changed-ne$false -or
   $g.allocator_policy_changed-ne$false){
  throw "Phase 6BG semantic/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6BG-PFB-TILE-BRIDGE-20261024-A",
  "phase6bg_env_build_cookie",
  "P6BG PFB TILE WRITE32",
  "P6BG PFB TILE READ32",
  "0xFD100240u",
  "0xFD1002C0u",
  "phase6bg_pfb_tile_write32",
  "phase6bg_pfb_tile_read32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BG source gate missing: $marker"}
}

if($text.Contains("GUEST_WRITE32(eax + 0x100244, edx);") -or
   $text.Contains("GUEST_WRITE32(eax + 0x100248, ecx);")){
  throw "Phase 6BG raw PFB tile writes remain in monolithic source"
}

$patchedShardCount=0
Get-ChildItem $shards -Filter "*.inl" | ForEach-Object {
  $s=Get-Content $_.FullName -Raw
  if($s.Contains("phase6bg_pfb_tile_write32(eax + 0x100244, edx)")){$patchedShardCount++}
}
if($patchedShardCount-ne1){
  throw "Phase 6BG expected exactly one patched shard, found $patchedShardCount"
}

Write-Host "[Phase6BG] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BG-PFB-TILE-BRIDGE-20261024-A"
    ExpectedEnvCookie="phase6bg_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bg-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bg-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BG-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BG] BUILD PASS"
  Write-Host ("[Phase6BG] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BG-A.xex"))
}
