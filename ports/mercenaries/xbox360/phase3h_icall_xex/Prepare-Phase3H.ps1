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

$buildRoot = Join-Path $repoRoot "build\phase3h_translated_icall"
$analysisRoot = Join-Path $buildRoot "analysis"
$disasmRoot = Join-Path $analysisRoot "disasm"
$xbeJson = Join-Path $analysisRoot "xbe.json"
$selector = Join-Path $phaseRoot "select_phase3h_candidate.py"
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
    Write-Host "[Phase3H] Verified retail XBE: $actualHash"

    $phase3eDisasm = Join-Path $repoRoot "build\phase3e_first_translated\analysis\disasm"
    $phase3eFunctions = Join-Path $phase3eDisasm "functions.json"

    if (Test-Path -LiteralPath $phase3eFunctions -PathType Leaf) {
        Write-Host "[Phase3H] Reusing Phase 3E reviewed-seed disassembly."
        $disasmRoot = $phase3eDisasm
    }
    else {
        Write-Host "[Phase3H] Phase 3E analysis not found; rebuilding reviewed-seed disassembly..."
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

    Write-Host "[Phase3H] Selecting the smallest isolated real RECOMP_ICALL_SAFE site..."
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
        throw "Phase 3H candidate selection failed with exit code $LASTEXITCODE."
    }

    if (-not (Test-Path -LiteralPath $selectionJson -PathType Leaf)) {
        throw "Phase 3H selector did not produce selection.json."
    }

    $selection = Get-Content -LiteralPath $selectionJson -Raw | ConvertFrom-Json
    $callerFile = Join-Path $buildRoot "$($selection.caller_name).c"
    $referenceCaller = Join-Path $buildRoot "reference_caller.c"
    $targetFile = Join-Path $buildRoot "$($selection.dispatch_target_name).c"
    $targetImpl = Join-Path $buildRoot "target_impl.c"
    $helperFile = $null
    if ($null -ne $selection.direct_helper_name -and
        -not [string]::IsNullOrWhiteSpace([string]$selection.direct_helper_name)) {
        $helperFile = Join-Path $buildRoot "$($selection.direct_helper_name).c"
    }

    Write-Host "[Phase3H] Auditing generated sources for legacy guest-memory lvalues..."
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $callerFile
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $referenceCaller
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $targetFile
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $targetImpl
    if ($null -ne $helperFile) {
        Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $helperFile
    }

    if (-not (Test-Path -LiteralPath $mainOut -PathType Leaf)) {
        throw "Phase 3H selector did not produce the XDK main.cpp."
    }

    Write-Host ""
    Write-Host "[Phase3H] READY"
    Write-Host "[Phase3H] Caller:          $($selection.caller_name) @ $($selection.caller)"
    Write-Host "[Phase3H] Caller size:     $($selection.caller_size) bytes / $($selection.caller_instructions) instructions"
    Write-Host "[Phase3H] ICALL expression:$($selection.icall_expression)"
    if ($null -ne $selection.direct_helper_name -and
        -not [string]::IsNullOrWhiteSpace([string]$selection.direct_helper_name)) {
        Write-Host "[Phase3H] Direct helper:   $($selection.direct_helper_name) @ $($selection.direct_helper)"
    }
    else {
        Write-Host "[Phase3H] Direct helper:   none"
    }
    Write-Host "[Phase3H] Dispatch target: $($selection.dispatch_target_name) @ $($selection.dispatch_target)"
    Write-Host "[Phase3H] Target size:     $($selection.dispatch_target_size) bytes / $($selection.dispatch_target_instructions) instructions"
    Write-Host "[Phase3H] Modes:           discover caller target -> resolved / unresolved; direct range guard"
    Write-Host "[Phase3H] XDK source:      $mainOut"
}
finally {
    Pop-Location
}
