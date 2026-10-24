[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\d3d_nv2a_base_restore_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_pfifo_idle_bridge_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6be_pfifo_idle_bridge.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @(
  $python,$emitter,$builder,
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bd-manifest.json"),
  (Join-Path $base "translated_shards")
)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BE input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bd-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BD"-or$m.build_tag-ne"P6BD-NV2A-BASE-RESTORE-20261024-A"){
  throw "Phase 6BE baseline identity mismatch"
}

Write-Host "[Phase6BE] PFIFO IDLE SEMANTIC BRIDGE"
Write-Host "[Phase6BE] 6BD hardware: restored FD000000 and immediately hit READ8 FD003214"
Write-Host "[Phase6BE] Map the exact 00292271 wait registers to existing NV2A backend idle semantics"
Write-Host "[Phase6BE] All other MMIO/VRAM remains hard-fenced"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BE emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out
if($LASTEXITCODE-ne0){throw "Phase 6BE emission failed"}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6be-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6BE output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BE"-or$r.build_tag-ne"P6BE-PFIFO-IDLE-BRIDGE-20261024-A"){
  throw "Phase 6BE manifest identity mismatch"
}
if($r.phase6be_pfifo_idle_bridge.matches_existing_nv2a_backend-ne$true -or
   $r.phase6be_pfifo_idle_bridge.all_other_mmio_fenced-ne$true -or
   $r.phase6be_pfifo_idle_bridge.mmio_global_fence_changed-ne$false -or
   $r.phase6be_pfifo_idle_bridge.vram_fence_changed-ne$false){
  throw "Phase 6BE semantic/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6BE-PFIFO-IDLE-BRIDGE-20261024-A",
  "phase6be_env_build_cookie",
  "P6BE PFIFO READ8",
  "P6BE PFIFO READ32",
  "P6BE PFIFO WRITE32",
  "0xFD003214u",
  "0xFD002400u",
  "0xFD003220u",
  "P6BE NV2A BASE RESTORE",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BE source gate missing: $marker"}
}

if($text.Contains("P6AZ READY3214 SHIM FIRE")){
  throw "Phase 6BE must not contain the old Phase 6AZ ready-bit shim"
}

$patchedShardCount=0
Get-ChildItem $shards -Filter "*.inl" | ForEach-Object {
  $s=Get-Content $_.FullName -Raw
  if($s.Contains("phase6be_pfifo_idle_read8(esi + 0x3214)")){$patchedShardCount++}
}
if($patchedShardCount-ne1){
  throw "Phase 6BE expected exactly one patched shard, found $patchedShardCount"
}

Write-Host "[Phase6BE] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BE-PFIFO-IDLE-BRIDGE-20261024-A"
    ExpectedEnvCookie="phase6be_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6be-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6be-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BE-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BE] BUILD PASS"
  Write-Host ("[Phase6BE] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BE-A.xex"))
}
