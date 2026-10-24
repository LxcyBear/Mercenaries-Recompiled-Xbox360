[CmdletBinding()]
param()
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$p4=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$stage3=Join-Path $root "build\phase3n_final_abi_scale"
$outDir=Join-Path $root "build\phase6_native_graphics\d3d_ready_flag_audit"
$analyzer=Join-Path $PSScriptRoot "analyze_phase6ay_d3d_ready_flag.py"
$functions=Join-Path $stage3 "analysis\disasm\functions.json"
$generated=Join-Path $stage3 "runtime\gen"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$report=Join-Path $outDir "phase6ay-ready-flag-audit.txt"
foreach($f in @($python,$analyzer,$functions,$generated,$baseEmitter)){if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6AY input: $f"}}
Write-Host "[Phase6AY] D3D READY-FLAG PRODUCER AUDIT"
Write-Host "[Phase6AY] Proven P6AW gate: device+0x3214 bit 0x10 never becomes set"
Write-Host "[Phase6AY] Scanning generated code before any forced-state experiment"
& $python -m py_compile $analyzer
if($LASTEXITCODE-ne0){throw "Phase 6AY analyzer syntax check failed"}
if(Test-Path $outDir){Remove-Item $outDir -Recurse -Force}
New-Item -ItemType Directory -Force -Path $outDir|Out-Null
& $python $analyzer "--phase4-emitter" $baseEmitter "--functions" $functions "--generated-root" $generated "--out" $report
if($LASTEXITCODE-ne0){throw "Phase 6AY producer audit failed"}
if(-not(Test-Path $report)){throw "Phase 6AY report missing"}
Write-Host "[Phase6AY] PASS"
Write-Host ("[Phase6AY] SEND THIS REPORT: {0}" -f $report)
