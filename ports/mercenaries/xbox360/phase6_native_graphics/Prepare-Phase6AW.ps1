[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\d3d_frontier_budget8m_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_spin_probe_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6aw_d3d_spin_probe.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$builder,(Join-Path $base "main.cpp"),(Join-Path $base "main_monolithic.cpp"),(Join-Path $base "phase5_env.cpp"),(Join-Path $base "phase6av-manifest.json"),(Join-Path $base "translated_shards"))){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6AW input: $f"}
}

$m=Get-Content (Join-Path $base "phase6av-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6AV"-or$m.build_tag-ne"P6AV-BUDGET8M-20261024-A"){throw "Phase 6AW baseline identity mismatch"}

Write-Host "[Phase6AW] D3D SPIN PROBE"
Write-Host "[Phase6AW] 6AV hardware: 8M ticks -> same 00291D4E state, fault=0"
Write-Host "[Phase6AW] No budget increase. No translated-pack, allocator, or fence changes."
Write-Host "[Phase6AW] Samples at 2M/4M/6M/8M + final 32-VA ring"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6AW emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out
if($LASTEXITCODE-ne0){throw "Phase 6AW emission failed"}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6aw-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){if(-not(Test-Path $f)){throw "Missing Phase 6AW output: $f"}}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6AW"-or$r.build_tag-ne"P6AW-D3D-SPIN-PROBE-20261024-A"){throw "Phase 6AW manifest identity mismatch"}

$text=Get-Content $mono -Raw
foreach($marker in @("#define PHASE4C_EXEC_BUDGET 8000000u","P6AW-D3D-SPIN-PROBE-20261024-A","phase6aw_env_build_cookie","P6AW SPIN SAMPLE","P6AW FINAL VA RING BEGIN")){
  if(-not$text.Contains($marker)){throw "Phase 6AW source gate missing: $marker"}
}

Write-Host "[Phase6AW] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6AW-D3D-SPIN-PROBE-20261024-A"
    ExpectedEnvCookie="phase6aw_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6aw-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6aw-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6AW-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6AW] BUILD PASS"
  Write-Host ("[Phase6AW] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AW-A.xex"))
}
