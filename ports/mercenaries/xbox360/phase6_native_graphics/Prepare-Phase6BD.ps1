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
$out=Join-Path $root "build\phase6_native_graphics\d3d_nv2a_base_restore_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bd_nv2a_base_restore.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @(
  $python,$emitter,$builder,
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6aw-manifest.json"),
  (Join-Path $base "translated_shards")
)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BD input: $f"}
}

$m=Get-Content (Join-Path $base "phase6aw-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6AW"-or$m.build_tag-ne"P6AW-D3D-SPIN-PROBE-20261024-A"){
  throw "Phase 6BD baseline identity mismatch"
}

Write-Host "[Phase6BD] PROVEN RETAIL NV2A BASE RESTORE"
Write-Host "[Phase6BD] 6BC proof: sub_00291F31 writes child[0]=FD000000 then touches FD001804"
Write-Host "[Phase6BD] Baseline: clean 6AW; 6AZ ready-bit shim is NOT inherited"
Write-Host "[Phase6BD] Restore only [0029AFA8]=FD000000 if zero during post-create init"
Write-Host "[Phase6BD] MMIO/VRAM fences, allocator, translated membership and 8M budget unchanged"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BD emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out
if($LASTEXITCODE-ne0){throw "Phase 6BD emission failed"}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bd-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6BD output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BD"-or$r.build_tag-ne"P6BD-NV2A-BASE-RESTORE-20261024-A"){
  throw "Phase 6BD manifest identity mismatch"
}
$z=$r.phase6bd_nv2a_base_restore
if($z.phase6bc_proof.child_address-ne"0x0029AFA8" -or
   $z.phase6bc_proof.first_dword_value-ne"0xFD000000" -or
   $z.phase6bc_proof.first_retail_mmio_read-ne"0xFD001804"){
  throw "Phase 6BD retail-constructor proof gate failed"
}
if($z.ready_bit_shims-ne$false -or
   $z.mmio_fence_changed-ne$false -or
   $z.vram_fence_changed-ne$false -or
   $z.allocator_policy_changed-ne$false){
  throw "Phase 6BD safety gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6BD-NV2A-BASE-RESTORE-20261024-A",
  "phase6bd_env_build_cookie",
  "P6BD NV2A BASE RESTORE",
  "0x0029AFA8u",
  "0xFD000000u",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BD source gate missing: $marker"}
}

if($text.Contains("P6AZ READY3214 SHIM FIRE")){
  throw "Phase 6BD must not inherit Phase 6AZ ready-bit shim"
}

$restoreShardCount=0
Get-ChildItem $shards -Filter "*.inl" | ForEach-Object {
  $s=Get-Content $_.FullName -Raw
  if($s.Contains("P6BD NV2A BASE RESTORE")){$restoreShardCount++}
}
if($restoreShardCount-ne1){
  throw "Phase 6BD expected exactly one patched shard, found $restoreShardCount"
}

Write-Host "[Phase6BD] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BD-NV2A-BASE-RESTORE-20261024-A"
    ExpectedEnvCookie="phase6bd_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bd-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bd-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BD-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BD] BUILD PASS"
  Write-Host ("[Phase6BD] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BD-A.xex"))
}
