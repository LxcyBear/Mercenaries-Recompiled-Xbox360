[CmdletBinding()]
param(
    [string]$GameDirectory
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$portRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\.."))
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $portRoot "..\.."))

if (-not $GameDirectory) {
    $GameDirectory = Join-Path $repoRoot "game_files\mercenaries-retail"
}

$gameRoot = [System.IO.Path]::GetFullPath($GameDirectory)
$xbePath = Join-Path $gameRoot "default.xbe"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$manualSeeds = Join-Path $portRoot "manual-seeds.json"

$buildRoot = Join-Path $repoRoot "build\phase3i_composite_slice"
$analysisRoot = Join-Path $buildRoot "analysis"
$disasmRoot = Join-Path $analysisRoot "disasm"
$xbeJson = Join-Path $analysisRoot "xbe.json"

$preparer = Join-Path $phaseRoot "prepare_phase3i_slice.py"
$template = Join-Path $phaseRoot "main_template.cpp"
$mainOut = Join-Path $buildRoot "main.cpp"
$selectionJson = Join-Path $buildRoot "selection.json"

$expectedXbeHash = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found at $python. Run ports\mercenaries\scripts\Setup-Python.ps1 first."
}

if (-not (Test-Path -LiteralPath $xbePath -PathType Leaf)) {
    throw "Supported retail default.xbe not found at: $xbePath"
}

$actualHash = (Get-FileHash -LiteralPath $xbePath -Algorithm SHA256).Hash
if ($actualHash -ne $expectedXbeHash) {
    throw "Unsupported default.xbe. Expected $expectedXbeHash, got $actualHash."
}

New-Item -ItemType Directory -Force -Path $analysisRoot | Out-Null
New-Item -ItemType Directory -Force -Path $disasmRoot | Out-Null
New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & $python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

Push-Location $repoRoot
try {
    Write-Host "[Phase3I] Verified retail XBE: $actualHash"

    $phase3eDisasm = Join-Path $repoRoot "build\phase3e_first_translated\analysis\disasm"
    $phase3eFunctions = Join-Path $phase3eDisasm "functions.json"

    if (Test-Path -LiteralPath $phase3eFunctions -PathType Leaf) {
        Write-Host "[Phase3I] Reusing Phase 3E reviewed-seed disassembly."
        $disasmRoot = $phase3eDisasm
    }
    else {
        Write-Host "[Phase3I] Phase 3E analysis not found; rebuilding reviewed-seed disassembly..."
        Invoke-Python "-m" "tools.xbe_parser" $xbePath "--json" $xbeJson "--quiet"

        $disasmArgs = @(
            "-m", "tools.disasm", $xbePath,
            "-o", $disasmRoot,
            "--analysis-json", $xbeJson,
            "--extra-sections", "XMV,XACTENG,D3D,XGRPH,DSOUND,WMADEC,XPP,DOLBY",
            "--seed-functions", $manualSeeds,
            "--protected-seed-functions", $manualSeeds,
            "--force"
        )
        Invoke-Python @disasmArgs
    }

    Write-Host "[Phase3I] Lifting the hardware-proven composite translated slice..."

    $prepareArgs = @(
        $preparer,
        "--xbe", $xbePath,
        "--disasm-dir", $disasmRoot,
        "--out-dir", $buildRoot,
        "--template", $template,
        "--main-out", $mainOut
    )
    & $python @prepareArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Phase 3I slice preparation failed with exit code $LASTEXITCODE."
    }

    if (-not (Test-Path -LiteralPath $selectionJson -PathType Leaf)) {
        throw "Phase 3I preparer did not produce selection.json."
    }

    $selection = Get-Content -LiteralPath $selectionJson -Raw | ConvertFrom-Json

    $generatedFiles = @(
        (Join-Path $buildRoot "$($selection.direct_caller_name).c"),
        (Join-Path $buildRoot "$($selection.shared_target_name).c"),
        (Join-Path $buildRoot "$($selection.tail_wrapper_name).c"),
        (Join-Path $buildRoot "$($selection.tail_callee_name).c"),
        (Join-Path $buildRoot "$($selection.icall_caller_name).c"),
        (Join-Path $buildRoot "discovery_caller.c"),
        (Join-Path $buildRoot "shared_target_impl.c")
    )

    if ($null -ne $selection.icall_direct_helper_name -and
        -not [string]::IsNullOrWhiteSpace([string]$selection.icall_direct_helper_name)) {
        $generatedFiles += Join-Path $buildRoot "$($selection.icall_direct_helper_name).c"
    }

    Write-Host "[Phase3I] Auditing every generated translated body for legacy guest-memory lvalues..."
    foreach ($file in $generatedFiles) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "Expected generated source is missing: $file"
        }

        Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $file
    }

    if (-not (Test-Path -LiteralPath $mainOut -PathType Leaf)) {
        throw "Phase 3I preparer did not produce the XDK main.cpp."
    }

    Write-Host ""
    Write-Host "[Phase3I] READY"
    Write-Host "[Phase3I] Direct chain:     $($selection.direct_caller) -> $($selection.shared_target)"
    Write-Host "[Phase3I] Tail chain:       $($selection.tail_wrapper) -> $($selection.tail_callee)"
    Write-Host "[Phase3I] ICALL caller:     $($selection.icall_caller)"
    Write-Host "[Phase3I] ICALL operand:    $($selection.icall_expression)"
    Write-Host "[Phase3I] Pointer slot expr:$($selection.pointer_slot_expression)"

    if ($null -ne $selection.icall_direct_helper_name -and
        -not [string]::IsNullOrWhiteSpace([string]$selection.icall_direct_helper_name)) {
        Write-Host "[Phase3I] ICALL helper:     $($selection.icall_direct_helper_name) @ $($selection.icall_direct_helper)"
    }
    else {
        Write-Host "[Phase3I] ICALL helper:     none"
    }

    Write-Host "[Phase3I] Real functions:   $($selection.function_count)"
    Write-Host "[Phase3I] XDK source:       $mainOut"
}
finally {
    Pop-Location
}
