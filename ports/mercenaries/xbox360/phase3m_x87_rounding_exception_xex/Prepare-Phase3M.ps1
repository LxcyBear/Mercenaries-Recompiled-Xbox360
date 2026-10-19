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

$buildRoot = Join-Path $repoRoot "build\phase3m_x87_rounding_exception"
$analysisRoot = Join-Path $buildRoot "analysis"
$disasmRoot = Join-Path $analysisRoot "disasm"
$xbeJson = Join-Path $analysisRoot "xbe.json"

$selector = Join-Path $phaseRoot "select_phase3m_cluster.py"
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
    Write-Host "[Phase3M] Verified retail XBE: $actualHash"

    $phase3eDisasm = Join-Path $repoRoot "build\phase3e_first_translated\analysis\disasm"
    $phase3eFunctions = Join-Path $phase3eDisasm "functions.json"

    if (Test-Path -LiteralPath $phase3eFunctions -PathType Leaf) {
        Write-Host "[Phase3M] Reusing Phase 3E reviewed-seed disassembly."
        $disasmRoot = $phase3eDisasm
    }
    else {
        Write-Host "[Phase3M] Phase 3E analysis not found; rebuilding reviewed-seed disassembly..."
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

    Write-Host "[Phase3M] Selecting a bounded real closure with real x87 rounding/conversion + x87 control/status state..."

    $selectorArgs = @(
        $selector,
        "--xbe", $xbePath,
        "--disasm-dir", $disasmRoot,
        "--out-dir", $buildRoot,
        "--template", $template,
        "--main-out", $mainOut
    )

    & $python @selectorArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Phase 3M x87 rounding/exception cluster selection failed with exit code $LASTEXITCODE."
    }

    if (-not (Test-Path -LiteralPath $selectionJson -PathType Leaf)) {
        throw "Phase 3M selector did not produce selection.json."
    }

    $selection = Get-Content -LiteralPath $selectionJson -Raw | ConvertFrom-Json

    Write-Host "[Phase3M] Auditing every selected translated body for legacy guest-memory lvalues..."

    foreach ($generatedName in $selection.generated_files) {
        $generatedPath = Join-Path $buildRoot $generatedName

        if (-not (Test-Path -LiteralPath $generatedPath -PathType Leaf)) {
            throw "Expected generated source is missing: $generatedPath"
        }

        Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $generatedPath
    }

    if (-not (Test-Path -LiteralPath $mainOut -PathType Leaf)) {
        throw "Phase 3M selector did not produce the XDK main.cpp."
    }

    Write-Host ""
    Write-Host "[Phase3M] READY"
    Write-Host "[Phase3M] Root:             $($selection.root_name) @ $($selection.root)"
    Write-Host "[Phase3M] Members:          $($selection.member_count)"
    Write-Host "[Phase3M] Dependency depth: $($selection.depth)"
    Write-Host "[Phase3M] Total bytes:      $($selection.total_bytes)"
    Write-Host "[Phase3M] Total insns:      $($selection.total_instructions)"
    Write-Host "[Phase3M] FP/XMM members:   $($selection.fp_members -join ', ')"
    Write-Host "[Phase3M] Flag members:     $($selection.flag_members -join ', ')"
    Write-Host "[Phase3M] Rounding members: $($selection.rounding_members -join ', ')"
    Write-Host "[Phase3M] x87 state members:$($selection.x87_state_members -join ', ')"
    Write-Host "[Phase3M] Backedge members: $($selection.backedge_members -join ', ')"
    Write-Host "[Phase3M] Static edges:"

    foreach ($edge in $selection.edges) {
        Write-Host "[Phase3M]   $($edge.from) -> $($edge.to)"
    }

    Write-Host "[Phase3M] XDK source:       $mainOut"
}
finally {
    Pop-Location
}
