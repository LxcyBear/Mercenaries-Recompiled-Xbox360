[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\d3d_spin_probe_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_ready3214_shim_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6az_d3d_ready3214_shim.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @(
  $python,$emitter,$builder,
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6aw-manifest.json"),
  (Join-Path $base "translated_shards")
)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6AZ input: $f"}
}

$m=Get-Content (Join-Path $base "phase6aw-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6AW"-or$m.build_tag-ne"P6AW-D3D-SPIN-PROBE-20261024-A"){
  throw "Phase 6AZ baseline identity mismatch"
}

Write-Host "[Phase6AZ] D3D READY3214 ONE-SHOT COMPLETION SHIM"
Write-Host "[Phase6AZ] 6AY static audit: +0x3214 writer count=0"
Write-Host "[Phase6AZ] Scope: exact sub_00292271 spin, post-create init active only"
Write-Host "[Phase6AZ] Force only +0x3214 bit 0x10 after 4096 loop entries"
Write-Host "[Phase6AZ] +0x2400/+0x3220, allocator, budget, NV2A/MMIO/VRAM fences unchanged"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6AZ emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out
if($LASTEXITCODE-ne0){throw "Phase 6AZ emission failed"}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6az-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6AZ output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6AZ"-or$r.build_tag-ne"P6AZ-D3D-READY3214-SHIM-20261024-A"){
  throw "Phase 6AZ manifest identity mismatch"
}
$z=$r.phase6az_ready3214_shim
if([int]$z.phase6ay_static_audit_writer_count-ne0){throw "Phase 6AZ writer-count proof gate failed"}
if($z.device_state_offset-ne"0x3214"-or$z.forced_bit-ne"0x10"){throw "Phase 6AZ shim identity gate failed"}
if($z.one_shot-ne$true-or$z.hard_fences_changed-ne$false){throw "Phase 6AZ safety gate failed"}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6AZ-D3D-READY3214-SHIM-20261024-A",
  "phase6az_env_build_cookie",
  "P6AZ READY3214 SHIM FIRE",
  "s_phase6azReady3214Entries",
  "GUEST_WRITE8(",
  "esi + 0x3214"
)){
  if(-not$text.Contains($marker)){throw "Phase 6AZ source gate missing: $marker"}
}

$shimShardCount=0
Get-ChildItem $shards -Filter "*.inl" | ForEach-Object {
  $s=Get-Content $_.FullName -Raw
  if($s.Contains("P6AZ READY3214 SHIM FIRE")){$shimShardCount++}
}
if($shimShardCount-ne1){throw "Phase 6AZ expected exactly one patched shard, found $shimShardCount"}

Write-Host "[Phase6AZ] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6AZ-D3D-READY3214-SHIM-20261024-A"
    ExpectedEnvCookie="phase6az_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6az-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6az-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6AZ-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6AZ] BUILD PASS"
  Write-Host ("[Phase6AZ] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AZ-A.xex"))
}
