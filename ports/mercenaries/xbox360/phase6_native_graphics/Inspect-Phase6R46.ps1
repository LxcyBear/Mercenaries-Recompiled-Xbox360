[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { throw "Python not found" }
    $python = $cmd.Source
}
$script = Join-Path $PSScriptRoot "inspect_phase6r46_audio_object_producers.py"
$source = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$log = Join-Path $root "build\phase6_native_graphics\phase6r46-producer-audit.txt"
foreach ($path in @($script, $source)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6R46 input: $path"
    }
}
Write-Host "[Phase6R46] ZERO-BUILD AUDIO OBJECT PRODUCER AUDIT"
Write-Host "[Phase6R46] No emitter changes, no build, no Xbox run."
& $python -m py_compile $script
if ($LASTEXITCODE -ne 0) { throw "Phase 6R46 syntax check failed" }
& $python $script "--source" $source 2>&1 | Tee-Object -FilePath $log
if ($LASTEXITCODE -ne 0) { throw "Phase 6R46 audit failed" }
Write-Host "[Phase6R46] REPORT: $log"
if ($CopyToClipboard) {
    Get-Content -LiteralPath $log -Raw | Set-Clipboard
    Write-Host "[Phase6R46] Complete report copied to clipboard."
}
