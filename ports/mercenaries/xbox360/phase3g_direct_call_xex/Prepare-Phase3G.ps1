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

$buildRoot = Join-Path $repoRoot "build\phase3g_translated_direct_call"
$analysisRoot = Join-Path $buildRoot "analysis"
$disasmRoot = Join-Path $analysisRoot "disasm"
$xbeJson = Join-Path $analysisRoot "xbe.json"
$selector = Join-Path $phaseRoot "select_phase3g_candidate.py"
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
    Write-Host "[Phase3G] Verified retail XBE: $actualHash"

    $phase3eDisasm = Join-Path $repoRoot "build\phase3e_first_translated\analysis\disasm"
    $phase3eFunctions = Join-Path $phase3eDisasm "functions.json"

    if (Test-Path -LiteralPath $phase3eFunctions -PathType Leaf) {
        Write-Host "[Phase3G] Reusing Phase 3E reviewed-seed disassembly."
        $disasmRoot = $phase3eDisasm
    }
    else {
        Write-Host "[Phase3G] Phase 3E analysis not found; rebuilding reviewed-seed disassembly..."
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

    Write-Host "[Phase3G] Selecting the smallest isolated real x86 CALL pair..."
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
        throw "Phase 3G candidate selection failed with exit code $LASTEXITCODE."
    }

    if (-not (Test-Path -LiteralPath $selectionJson -PathType Leaf)) {
        throw "Phase 3G selector did not produce selection.json."
    }

    $selection = Get-Content -LiteralPath $selectionJson -Raw | ConvertFrom-Json
    $callerFile = Join-Path $buildRoot "$($selection.caller_name).c"
    $calleeFile = Join-Path $buildRoot "$($selection.callee_name).c"
    $calleeImpl = Join-Path $buildRoot "callee_impl.c"
    $referenceCaller = Join-Path $buildRoot "reference_caller.c"

    Write-Host "[Phase3G] Auditing generated sources for legacy guest-memory lvalues..."
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $callerFile
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $calleeFile
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $calleeImpl
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $referenceCaller

    if (-not (Test-Path -LiteralPath $mainOut -PathType Leaf)) {
        throw "Phase 3G selector did not produce the XDK main.cpp."
    }

    Write-Host ""
    Write-Host "[Phase3G] READY"
    Write-Host "[Phase3G] Caller:         $($selection.caller_name) @ $($selection.caller)"
    Write-Host "[Phase3G] Callee:         $($selection.callee_name) @ $($selection.callee)"
    Write-Host "[Phase3G] Caller size:    $($selection.caller_size) bytes / $($selection.caller_instructions) instructions"
    Write-Host "[Phase3G] Callee size:    $($selection.callee_size) bytes / $($selection.callee_instructions) instructions"
    Write-Host "[Phase3G] Real call:      PUSH32(esp, 0); translated callee();"
    Write-Host "[Phase3G] Reference call: explicit GUEST_WRITE32(esp-4, 0), set ESP, translated callee();"
    Write-Host "[Phase3G] XDK source:     $mainOut"
}
finally {
    Pop-Location
}
