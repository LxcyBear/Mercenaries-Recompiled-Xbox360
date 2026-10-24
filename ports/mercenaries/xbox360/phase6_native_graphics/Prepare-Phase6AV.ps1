[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\d3d_frontier_00292586_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_frontier_budget8m_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6av_budget8m.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$builder,(Join-Path $base "main.cpp"),(Join-Path $base "main_monolithic.cpp"),(Join-Path $base "phase5_env.cpp"),(Join-Path $base "phase6au-manifest.json"),(Join-Path $base "translated_shards"))){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6AV input: $f"}
}

$m=Get-Content (Join-Path $base "phase6au-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6AU"-or$m.build_tag-ne"P6AU-D3D-FRONTIER-00292586-20261024-A"){throw "Phase 6AV baseline identity mismatch"}

Write-Host "[Phase6AV] 8,000,000-TICK D3D DEEP EXECUTION PASS"
Write-Host "[Phase6AV] 6AU hardware: crossed 00292586; next stop=BUDGET at 00291D4E, fault=0"
Write-Host "[Phase6AV] Only change: PHASE4C_EXEC_BUDGET 2000000 -> 8000000"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6AV emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out
if($LASTEXITCODE-ne0){throw "Phase 6AV emission failed"}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6av-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){if(-not(Test-Path $f)){throw "Missing Phase 6AV output: $f"}}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6AV"-or$r.build_tag-ne"P6AV-BUDGET8M-20261024-A"){throw "Phase 6AV manifest identity mismatch"}
if([int]$r.phase6av_budget8m.old_budget_ticks-ne2000000 -or [int]$r.phase6av_budget8m.new_budget_ticks-ne8000000){throw "Phase 6AV budget gate failed"}

$text=Get-Content $mono -Raw
foreach($marker in @("#define PHASE4C_EXEC_BUDGET 8000000u","P6AV-BUDGET8M-20261024-A","phase6av_env_build_cookie","PASS: Phase 6AV entered translated D3D frontier 00292586")){
  if(-not$text.Contains($marker)){throw "Phase 6AV source gate missing: $marker"}
}

Write-Host "[Phase6AV] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6AV-BUDGET8M-20261024-A"
    ExpectedEnvCookie="phase6av_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6av-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6av-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6AV-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6AV] BUILD PASS"
  Write-Host ("[Phase6AV] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AV-A.xex"))
}
