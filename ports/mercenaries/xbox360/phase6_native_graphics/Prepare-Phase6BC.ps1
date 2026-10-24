[CmdletBinding()]
param()
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$p4=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$stage3=Join-Path $root "build\phase3n_final_abi_scale"
$outDir=Join-Path $root "build\phase6_native_graphics\d3d_child_nv2a_base_audit"
$analyzer=Join-Path $PSScriptRoot "analyze_phase6bc_d3d_child_nv2a_base.py"
$functions=Join-Path $stage3 "analysis\disasm\functions.json"
$generated=Join-Path $stage3 "runtime\gen"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$report=Join-Path $outDir "phase6bc-d3d-child-nv2a-base.txt"

foreach($f in @($python,$analyzer,$functions,$generated,$baseEmitter)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BC input: $f"}
}

Write-Host "[Phase6BC] D3D CHILD FIRST-DWORD / NV2A-BASE AUDIT"
Write-Host "[Phase6BC] No XEX build; prove the child base semantics before hardware"

& $python -m py_compile $analyzer
if($LASTEXITCODE-ne0){throw "Phase 6BC analyzer syntax check failed"}

if(Test-Path $outDir){Remove-Item $outDir -Recurse -Force}
New-Item -ItemType Directory -Force -Path $outDir|Out-Null

& $python $analyzer "--phase4-emitter" $baseEmitter "--functions" $functions "--generated-root" $generated "--out" $report
if($LASTEXITCODE-ne0){throw "Phase 6BC NV2A-base audit failed"}
if(-not(Test-Path $report)){throw "Phase 6BC report missing"}

Write-Host "[Phase6BC] PASS"
Write-Host ("[Phase6BC] SEND THIS REPORT: {0}" -f $report)
