[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p6 = $PSScriptRoot
$p4 = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseDir = Join-Path $root "build\phase6_native_graphics\cos_harvest_00251cd0_xdk"
$out = Join-Path $root "build\phase6_native_graphics\budget600k_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6p-emitter.log"

$emitter = Join-Path $p6 "emit_phase6p_budget_extension.py"
$baseEmitter = Join-Path $p4 "emit_phase4c_startup_slice.py"
foreach ($v in @($emitter,$baseEmitter,$python)) {
    if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6P input: $v" }
}

$baseManifestPath = Join-Path $baseDir "phase6o-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    $baseManifestPath
)
foreach ($f in $baseFiles) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6P fast baseline missing: $f. Keep the successful Phase 6O generated output."
    }
}

$baseManifest = Get-Content $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6O" -or $baseManifest.build_tag -ne "P6O-COS-HARVEST-00251CD0-20261022-A") {
    throw "Phase 6P cached Phase 6O baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6P] CACHED BUDGET EXTENSION"
Write-Host "[Phase6P] Phase 6O hardware boundary: BUDGET 0023A3CE -> 002527B5, fault=0"
Write-Host "[Phase6P] FAST BASE: exact Phase 6O monolithic cache"
Write-Host "[Phase6P] Pack/support policy: UNCHANGED"
Write-Host "[Phase6P] Execution watchdog: 200000 -> 600000 blocks"
Write-Host "[Phase6P] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $emitter "--base-dir" $baseDir "--base-emitter" $baseEmitter "--out-dir" $out 2>&1 | Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}
if ($rc -ne 0) {
    Get-Content $log -Tail 200
    throw "Phase 6P emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6p-manifest.json"
foreach ($f in @($main,$monolithic,$env,$manifest)) {
    if (-not (Test-Path $f)) { throw "Phase 6P missing output: $f" }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6P" -or $m.build_tag -ne "P6P-BUDGET600K-20261022-A") {
    throw "Phase 6P manifest identity mismatch"
}
$g = $m.phase6p_budget_extension
if (-not [bool]$g.phase6o_hardware_pass -or [int]$g.old_execution_budget -ne 200000 -or [int]$g.new_execution_budget -ne 600000 -or -not [bool]$g.pack_members_unchanged) {
    throw "Phase 6P manifest gate mismatch"
}
if ($null -eq $g.source_layout -or [int]$g.source_layout.shard_count -lt 1) {
    throw "Phase 6P source-shard manifest gate mismatch"
}
$shardDir = Join-Path $out ([string]$g.source_layout.shard_directory)
if (-not (Test-Path -LiteralPath $shardDir)) {
    throw "Phase 6P translated shard directory missing: $shardDir"
}

Write-Host ""
Write-Host "[Phase6P] READY"
Write-Host ("[Phase6P] Pack members             : {0} (unchanged)" -f [int]$g.pack_members)
Write-Host ("[Phase6P] Execution budget old     : {0}" -f [int]$g.old_execution_budget)
Write-Host ("[Phase6P] Execution budget new     : {0}" -f [int]$g.new_execution_budget)
Write-Host ("[Phase6P] VS wrapper lines         : {0}" -f [int]$g.source_layout.wrapper_lines)
Write-Host ("[Phase6P] Translated body lines    : {0}" -f [int]$g.source_layout.body_lines)
Write-Host ("[Phase6P] Generated .inl shards    : {0}" -f [int]$g.source_layout.shard_count)
Write-Host "[Phase6P] Build BOTH fresh sources:"
Write-Host "[Phase6P]   $main   (small VS-friendly wrapper)"
Write-Host "[Phase6P]   $env"
Write-Host "[Phase6P] DO NOT compile main_monolithic.cpp; emitter cache only:"
Write-Host "[Phase6P]   $monolithic"
Write-Host "[Phase6P] Keep translated_shards beside main.cpp and d3d9.lib linked."
Write-Host "[Phase6P] Expected tag: P6P-BUDGET600K-20261022-A"
Write-Host "[Phase6P] Hardware goal: clear the old 200k watchdog and expose the next real boundary."
Write-Host "[Phase6P] Purple = genuine NV2A MMIO/VRAM boundary."
