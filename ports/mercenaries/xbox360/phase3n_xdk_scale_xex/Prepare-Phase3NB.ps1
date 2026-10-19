[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$portRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\.."))
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $portRoot "..\.."))

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$stageARoot = Join-Path $repoRoot "build\phase3n_final_abi_scale"
$generatedRoot = Join-Path $stageARoot "runtime\gen"
$gateReport = Join-Path $stageARoot "phase3n-audit.json"
$functionsPath = Join-Path $stageARoot "analysis\disasm\functions.json"

$buildRoot = Join-Path $repoRoot "build\phase3n_xdk_scale"
$selector = Join-Path $phaseRoot "select_phase3n_scale_pack.py"
$template = Join-Path $phaseRoot "main_template.cpp"
$mainOut = Join-Path $buildRoot "main.cpp"
$selectionJson = Join-Path $buildRoot "selection.json"

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & $python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

function Get-CompositeSha256 {
    param([Parameter(Mandatory = $true)][string[]]$Lines)

    $joined = [string]::Join([Environment]::NewLine, $Lines)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($joined)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString(
            $sha.ComputeHash($bytes))).Replace("-", "")
    }
    finally {
        $sha.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found at $python."
}
foreach ($required in @(
    $gateReport, $functionsPath, $selector, $template
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required Phase 3N-B input is missing: $required"
    }
}
if (-not (Test-Path -LiteralPath $generatedRoot -PathType Container)) {
    throw "3N-A generated tree is missing: $generatedRoot"
}

Push-Location $repoRoot
try {
    Write-Host "[Phase3N-B] FINAL XDK COMPILER/LINKER/RUNTIME SCALE GATE"

    $gate = Get-Content -LiteralPath $gateReport -Raw | ConvertFrom-Json
    if ($gate.phase -ne "3N-A" -or -not [bool]$gate.gate_a_pass) {
        throw "3N-A report is not a PASS. Re-run Stage A before Stage B."
    }
    if ([int]$gate.recompiler.failed -ne 0 -or
        [int]$gate.portability.fatal_count -ne 0 -or
        [int]$gate.portability.residual_unresolved_stubs -ne 0) {
        throw "3N-A report is not clean enough for the XDK scale gate."
    }

    $generatedFiles = @(
        Get-ChildItem -LiteralPath $generatedRoot -Filter "recomp_*.c" -File |
        Sort-Object Name
    )
    if ($generatedFiles.Count -eq 0) {
        throw "No Stage-A generated C files found under $generatedRoot."
    }

    $digestLines = @()
    foreach ($file in $generatedFiles) {
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        $digestLines += ("{0}:{1}:{2}" -f $file.Name, $file.Length, $hash)
    }
    $treeSha = Get-CompositeSha256 -Lines $digestLines
    if ($treeSha -ne [string]$gate.generated_tree_sha256) {
        throw ("3N-A generated tree changed after PASS. Expected {0}, got {1}. " +
               "Re-run Stage A before Stage B." -f
               $gate.generated_tree_sha256, $treeSha)
    }

    Write-Host ("[Phase3N-B] Verified Gate-A tree: {0}" -f $treeSha)

    New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
    Remove-Item -LiteralPath $mainOut -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $selectionJson -Force -ErrorAction SilentlyContinue

    Write-Host "[Phase3N-B] Selecting audited leaf bodies and emitting XDK main.cpp..."
    $selectorArgs = @(
        $selector,
        "--generated-root", $generatedRoot,
        "--functions", $functionsPath,
        "--gate-report", $gateReport,
        "--template", $template,
        "--out-dir", $buildRoot,
        "--main-out", $mainOut
    )
    Invoke-Python @selectorArgs

    if (-not (Test-Path -LiteralPath $selectionJson -PathType Leaf)) {
        throw "Phase 3N-B selector did not produce selection.json."
    }
    if (-not (Test-Path -LiteralPath $mainOut -PathType Leaf)) {
        throw "Phase 3N-B selector did not produce main.cpp."
    }

    $selection = Get-Content -LiteralPath $selectionJson -Raw | ConvertFrom-Json

    Write-Host "[Phase3N-B] Auditing emitted hardware source for legacy guest-memory lvalues..."
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $mainOut

    if ([int]$selection.scale_function_count -lt 64) {
        throw "Phase 3N-B scale pack is below the 64-function minimum."
    }
    if ([int64]$selection.scale_guest_bytes -lt 16384) {
        throw "Phase 3N-B scale pack is below the 16 KiB guest-code minimum."
    }

    $mainHash = (Get-FileHash -LiteralPath $mainOut -Algorithm SHA256).Hash

    Write-Host ""
    Write-Host "[Phase3N-B] ===== SCALE PACK SUMMARY ====="
    Write-Host ("[Phase3N-B] Execution root:    {0}" -f $selection.execution_root)
    Write-Host ("[Phase3N-B] Execution members: {0}" -f $selection.execution_member_count)
    Write-Host ("[Phase3N-B] Execution depth:   {0}" -f $selection.execution_depth)
    Write-Host ("[Phase3N-B] Scale functions:   {0}" -f $selection.scale_function_count)
    Write-Host ("[Phase3N-B] Scale guest bytes: {0}" -f $selection.scale_guest_bytes)
    Write-Host ("[Phase3N-B] Scale source bytes:{0}" -f $selection.scale_source_bytes)
    Write-Host ("[Phase3N-B] main.cpp SHA256:    {0}" -f $mainHash)
    Write-Host ("[Phase3N-B] XDK source:         {0}" -f $mainOut)
    Write-Host "[Phase3N-B] READY FOR XDK COMPILE/LINK + REAL HARDWARE RUN"
}
finally {
    Pop-Location
}
