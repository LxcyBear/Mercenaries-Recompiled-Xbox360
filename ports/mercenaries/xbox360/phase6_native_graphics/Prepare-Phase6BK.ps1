[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\d3d_pfb_zcomp_bridge_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_pfifo_dma_push_clear_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bk_pfifo_dma_push_clear.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @(
  $python,$emitter,$builder,
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bj-manifest.json"),
  (Join-Path $base "translated_shards")
)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BK input: $f"}
}

$m=Get-Content (Join-Path $base "phase6bj-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BJ"-or$m.build_tag-ne"P6BJ-PFB-ZCOMP-BRIDGE-20261024-A"){
  throw "Phase 6BK baseline identity mismatch"
}

Write-Host "[Phase6BK] PFIFO DMA_PUSH ZERO-CLEAR CONTINUATION"
Write-Host "[Phase6BK] 6BJ crossed ZCOMP tile1 write/readback and PGRAPH mirror"
Write-Host "[Phase6BK] next access WRITE32 FD003220 value 00000000 at VA 00292761"
Write-Host "[Phase6BK] Reuse already-proven Phase 6BE zero-clear semantics only for exact FD003220"
Write-Host "[Phase6BK] PFB tile/ZCOMP + PGRAPH state remain unchanged; all unrelated MMIO/VRAM stays fenced"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BK emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

& $python $emitter "--base-dir" $base "--out-dir" $out 2>&1 | Tee-Object -Variable phase6bkEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BK] EMITTER OUTPUT:"
  $phase6bkEmitOutput | ForEach-Object { Write-Host $_ }
  throw "Phase 6BK emission failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bk-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BK output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BK"-or$r.build_tag-ne"P6BK-PFIFO-DMA-PUSH-CLEAR-20261024-A"){
  throw "Phase 6BK manifest identity mismatch"
}
$g=$r.phase6bk_pfifo_dma_push_clear
if($g.hardware_proof.next_mmio_access-ne"WRITE32 0xFD003220" -or
   $g.hardware_proof.next_mmio_value-ne"0x00000000" -or
   $g.register_semantics.implementation-ne"reuse phase6be_pfifo_idle_write32" -or
   $g.pfb_tile_scope_unchanged-ne$true -or
   $g.pfb_zcomp_scope_unchanged-ne$true -or
   $g.pgraph_scope_unchanged-ne$true -or
   $g.all_other_mmio_fenced-ne$true -or
   $g.vram_fence_changed-ne$false -or
   $g.allocator_policy_changed-ne$false){
  throw "Phase 6BK semantic/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6BK-PFIFO-DMA-PUSH-CLEAR-20261024-A",
  "phase6bk_env_build_cookie",
  "address == 0xFD003220u",
  "value == 0u",
  "phase6be_pfifo_idle_write32(address, value)",
  "phase6bj_pfb_zcomp_write32",
  "phase6bg_pfb_tile_write32",
  "phase6bh_pgraph_scoped_write32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BK source gate missing: $marker"}
}

Write-Host "[Phase6BK] READY"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BK-PFIFO-DMA-PUSH-CLEAR-20261024-A"
    ExpectedEnvCookie="phase6bk_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bk-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bk-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BK-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BK] BUILD PASS"
  Write-Host ("[Phase6BK] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BK-A.xex"))
}
