[CmdletBinding()]
param()
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$p4=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$stage3=Join-Path $root "build\phase3n_final_abi_scale"
$outDir=Join-Path $root "build\phase6_native_graphics\d3d_spin_source_analysis"
$analyzer=Join-Path $PSScriptRoot "analyze_phase6ax_d3d_spin_source.py"
$functions=Join-Path $stage3 "analysis\disasm\functions.json"
$generated=Join-Path $stage3 "runtime\gen"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$report=Join-Path $outDir "phase6ax-spin-source.txt"

foreach($f in @($python,$analyzer,$functions,$generated,$baseEmitter)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6AX input: $f"}
}

Write-Host "[Phase6AX] D3D SPIN SOURCE CORRELATION"
Write-Host "[Phase6AX] P6AW hardware loop:"
Write-Host "[Phase6AX] 291BE0 -> 291BFF -> 291C10 -> 291C60 -> 291CCB -> 291D3A"
Write-Host "[Phase6AX] -> 291D42 -> 291D4E -> 292299 -> 2922A9 -> 292277 -> 292292 -> repeat"
Write-Host "[Phase6AX] No XEX build in this phase; resolve the loop condition first."

& $python -m py_compile $analyzer
if($LASTEXITCODE-ne0){throw "Phase 6AX analyzer syntax check failed"}

if(Test-Path $outDir){Remove-Item $outDir -Recurse -Force}
New-Item -ItemType Directory -Force -Path $outDir|Out-Null

& $python $analyzer "--phase4-emitter" $baseEmitter "--functions" $functions "--generated-root" $generated "--out" $report

if($LASTEXITCODE-ne0){throw "Phase 6AX source correlation failed"}
if(-not(Test-Path $report)){throw "Phase 6AX report missing"}

Write-Host "[Phase6AX] PASS"
Write-Host ("[Phase6AX] SEND THIS REPORT: {0}" -f $report)
