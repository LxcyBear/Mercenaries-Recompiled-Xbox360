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

$buildRoot = Join-Path $repoRoot "build\phase3e_first_translated"
$analysisRoot = Join-Path $buildRoot "analysis"
$disasmRoot = Join-Path $analysisRoot "disasm"
$xbeJson = Join-Path $analysisRoot "xbe.json"
$generatedFunction = Join-Path $buildRoot "sub_00208F30.c"
$templatePath = Join-Path $phaseRoot "main_template.cpp"
$mainOut = Join-Path $buildRoot "main.cpp"

$expectedXbeHash = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
$targetFunction = "0x00208F30"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found at $python. Run ports\mercenaries\scripts\Setup-Python.ps1 first."
}

if (-not (Test-Path -LiteralPath $xbePath -PathType Leaf)) {
    throw "Supported retail default.xbe not found at: $xbePath"
}

if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
    throw "Phase 3E template missing: $templatePath"
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
    Write-Host "[Phase3E] Verified retail XBE: $actualHash"
    Write-Host "[Phase3E] Parsing XBE metadata..."

    $parserArgs = @("-m", "tools.xbe_parser", $xbePath, "--json", $xbeJson, "--quiet")
    Invoke-Python @parserArgs

    Write-Host "[Phase3E] Running one reviewed-seed disassembly pass..."
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

    $functionsPath = Join-Path $disasmRoot "functions.json"
    if (-not (Test-Path -LiteralPath $functionsPath -PathType Leaf)) {
        throw "Disassembler did not produce functions.json."
    }

    $functions = Get-Content -LiteralPath $functionsPath -Raw | ConvertFrom-Json
    $candidate = @(
        $functions |
            Where-Object {
                ([string]$_.start).Trim().ToUpperInvariant() -eq "0X00208F30"
            }
    )

    if ($candidate.Count -ne 1) {
        throw "Reviewed candidate 0x00208F30 was not detected exactly once."
    }

    Write-Host "[Phase3E] Lifting only $targetFunction with explicit guest memory..."

    $recompArgs = @(
        "-m", "tools.recomp", $xbePath,
        "--function", $targetFunction,
        "--explicit-guest-memory",
        "--disasm-dir", $disasmRoot,
        "--skip-jump-table-splits"
    )

    $generatedLines = & $python @recompArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Single-function lift failed with exit code $LASTEXITCODE."
    }

    $generated = ($generatedLines -join [Environment]::NewLine) + [Environment]::NewLine
    [System.IO.File]::WriteAllText(
        $generatedFunction,
        $generated,
        [System.Text.UTF8Encoding]::new($false)
    )

    if ($generated -notmatch 'void\s+sub_00208F30\s*\(\s*void\s*\)') {
        throw "Generated function did not use expected name sub_00208F30."
    }

    if ($generated -notmatch 'GUEST_READ8\s*\(') {
        throw "Candidate no longer has the reviewed one-byte explicit read shape. Stop for re-audit."
    }

    if ($generated -match 'GUEST_READ(?:16|32|64|F32|F64|128)\s*\(') {
        throw "Candidate unexpectedly uses a guest read wider than 8 bits. Stop for re-audit."
    }

    if ($generated -match 'GUEST_WRITE(?:8|16|32|64|F32|F64|128)\s*\(') {
        throw "Candidate unexpectedly writes guest memory. Stop for re-audit."
    }

    if ($generated -match '\b(?:RECOMP_ICALL|ICALL|XBOX_KERNEL|XBOX_MEMCPY|XBOX_REP_MOVS)\b') {
        throw "Candidate unexpectedly depends on indirect/runtime services. Stop for re-audit."
    }

    $translatedCalls = [regex]::Matches(
        $generated,
        '\bsub_[0-9A-Fa-f]{8}\s*\('
    )
    if ($translatedCalls.Count -ne 1) {
        throw "Candidate unexpectedly contains another translated-function call."
    }

    Write-Host "[Phase3E] Auditing generated function for legacy guest-memory lvalues..."
    $auditArgs = @("-m", "tools.recomp.audit_explicit_guest_memory", $generatedFunction)
    Invoke-Python @auditArgs

    $template = Get-Content -LiteralPath $templatePath -Raw
    $marker = "/*__PHASE3E_GENERATED_FUNCTION__*/"
    if (-not $template.Contains($marker)) {
        throw "Phase 3E template injection marker is missing."
    }

    $combined = $template.Replace($marker, $generated)

    [System.IO.File]::WriteAllText(
        $mainOut,
        $combined,
        [System.Text.UTF8Encoding]::new($false)
    )

    Write-Host ""
    Write-Host "[Phase3E] READY"
    Write-Host "[Phase3E] Generated function: $generatedFunction"
    Write-Host "[Phase3E] XDK source:        $mainOut"
    Write-Host "[Phase3E] Compile build\phase3e_first_translated\main.cpp in the same VS17/XDK diagnostic project."
}
finally {
    Pop-Location
}
