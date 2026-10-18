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

$buildRoot = Join-Path $repoRoot "build\phase3f_translated_tailcall"
$analysisRoot = Join-Path $buildRoot "analysis"
$disasmRoot = Join-Path $analysisRoot "disasm"
$xbeJson = Join-Path $analysisRoot "xbe.json"
$calleeFile = Join-Path $buildRoot "sub_00034AE0.c"
$wrapperFile = Join-Path $buildRoot "sub_00034AD0.c"
$templatePath = Join-Path $phaseRoot "main_template.cpp"
$mainOut = Join-Path $buildRoot "main.cpp"

$expectedXbeHash = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
$wrapperAddress = "0x00034AD0"
$calleeAddress = "0x00034AE0"

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

function Lift-One {
    param(
        [string]$Address,
        [string]$OutputPath
    )

    $args = @(
        "-m", "tools.recomp", $xbePath,
        "--function", $Address,
        "--explicit-guest-memory",
        "--disasm-dir", $disasmRoot,
        "--skip-jump-table-splits"
    )

    $lines = & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Single-function lift failed for $Address."
    }

    $source = ($lines -join [Environment]::NewLine) + [Environment]::NewLine
    [System.IO.File]::WriteAllText(
        $OutputPath,
        $source,
        [System.Text.UTF8Encoding]::new($false)
    )
    return $source
}

function Assert-No-UnsafeDependency {
    param(
        [string]$Source,
        [string]$Label
    )

    if ($Source -match '\b(?:RECOMP_ICALL_SAFE|RECOMP_ITAIL|RECOMP_RDTSC|XBOX_MEMCPY|XBOX_REP_MOVS|xbox_[A-Za-z0-9_]+|__debugbreak)\b') {
        throw "$Label unexpectedly depends on ICALL/kernel/runtime-copy services. Stop for re-audit."
    }

    if ($Source -match '\b(?:fp_push|fp_pop|fp_top|fp_st|xmm[0-7]|g_xmm[0-7]|g_mm[0-7]|GUEST_READF32|GUEST_READF64|GUEST_WRITEF32|GUEST_WRITEF64)\b') {
        throw "$Label unexpectedly requires x87/SSE/MMX state. Stop for a narrower Phase 3F candidate."
    }
}

Push-Location $repoRoot
try {
    Write-Host "[Phase3F] Verified retail XBE: $actualHash"

    $phase3eDisasm = Join-Path $repoRoot "build\phase3e_first_translated\analysis\disasm"
    $phase3eFunctions = Join-Path $phase3eDisasm "functions.json"

    if (Test-Path -LiteralPath $phase3eFunctions -PathType Leaf) {
        Write-Host "[Phase3F] Reusing Phase 3E reviewed-seed disassembly."
        $disasmRoot = $phase3eDisasm
    }
    else {
        Write-Host "[Phase3F] Parsing XBE metadata..."
        $parserArgs = @("-m", "tools.xbe_parser", $xbePath, "--json", $xbeJson, "--quiet")
        Invoke-Python @parserArgs

        Write-Host "[Phase3F] Running reviewed-seed disassembly..."
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

    $functionsPath = Join-Path $disasmRoot "functions.json"
    $functions = Get-Content -LiteralPath $functionsPath -Raw | ConvertFrom-Json

    $wrapper = @($functions | Where-Object {
        ([string]$_.start).Trim().ToUpperInvariant() -eq "0X00034AD0"
    })
    $callee = @($functions | Where-Object {
        ([string]$_.start).Trim().ToUpperInvariant() -eq "0X00034AE0"
    })

    if ($wrapper.Count -ne 1) {
        throw "Wrapper 0x00034AD0 was not detected exactly once."
    }
    if ($callee.Count -ne 1) {
        throw "Callee 0x00034AE0 was not detected exactly once."
    }

    Write-Host "[Phase3F] Wrapper metadata: size=$($wrapper[0].size) instructions=$($wrapper[0].num_instructions)"
    Write-Host "[Phase3F] Callee metadata:  size=$($callee[0].size) instructions=$($callee[0].num_instructions)"

    Write-Host "[Phase3F] Lifting callee $calleeAddress..."
    $calleeSource = Lift-One -Address $calleeAddress -OutputPath $calleeFile

    Write-Host "[Phase3F] Lifting wrapper $wrapperAddress..."
    $wrapperSource = Lift-One -Address $wrapperAddress -OutputPath $wrapperFile

    if ($calleeSource -notmatch 'void\s+sub_00034AE0\s*\(\s*void\s*\)') {
        throw "Callee generated with an unexpected function signature."
    }
    if ($wrapperSource -notmatch 'void\s+sub_00034AD0\s*\(\s*void\s*\)') {
        throw "Wrapper generated with an unexpected function signature."
    }

    Assert-No-UnsafeDependency -Source $calleeSource -Label "Callee"
    Assert-No-UnsafeDependency -Source $wrapperSource -Label "Wrapper"

    $wrapperTargetCalls = [regex]::Matches(
        $wrapperSource,
        '\bsub_00034AE0\s*\(\s*\)'
    )
    if ($wrapperTargetCalls.Count -ne 1) {
        throw "Wrapper did not emit exactly one direct call to sub_00034AE0."
    }

    if ($wrapperSource -notmatch 'tail jmp 0x00034AE0') {
        throw "Wrapper no longer lowers 0x00034AE0 as a tail jump."
    }

    if ($wrapperSource -match '\bPUSH32\s*\(') {
        throw "Wrapper tail call unexpectedly pushes a synthetic return address."
    }

    $wrapperSubs = @(
        [regex]::Matches($wrapperSource, '\bsub_([0-9A-Fa-f]{8})\s*\(') |
            ForEach-Object { $_.Groups[1].Value.ToUpperInvariant() } |
            Sort-Object -Unique
    )
    $unexpectedWrapperSubs = @($wrapperSubs | Where-Object {
        $_ -ne "00034AD0" -and $_ -ne "00034AE0"
    })
    if ($unexpectedWrapperSubs.Count -ne 0) {
        throw "Wrapper calls unexpected translated function(s): $($unexpectedWrapperSubs -join ', ')."
    }

    $calleeSubs = @(
        [regex]::Matches($calleeSource, '\bsub_([0-9A-Fa-f]{8})\s*\(') |
            ForEach-Object { $_.Groups[1].Value.ToUpperInvariant() } |
            Sort-Object -Unique
    )
    $unexpectedCalleeSubs = @($calleeSubs | Where-Object { $_ -ne "00034AE0" })
    if ($unexpectedCalleeSubs.Count -ne 0) {
        throw "Callee unexpectedly calls translated function(s): $($unexpectedCalleeSubs -join ', ')."
    }

    $calleeLineCount = $calleeSource.Split([Environment]::NewLine).Count
    $wrapperLineCount = $wrapperSource.Split([Environment]::NewLine).Count
    if ($calleeLineCount -gt 220 -or $wrapperLineCount -gt 120) {
        throw "Candidate pair is larger than the bounded Phase 3F limit. Callee=$calleeLineCount wrapper=$wrapperLineCount."
    }

    Write-Host "[Phase3F] Auditing generated functions for legacy guest-memory lvalues..."
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $calleeFile
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $wrapperFile

    $template = Get-Content -LiteralPath $templatePath -Raw
    $calleeMarker = "/*__PHASE3F_CALLEE__*/"
    $wrapperMarker = "/*__PHASE3F_WRAPPER__*/"

    if (-not $template.Contains($calleeMarker) -or -not $template.Contains($wrapperMarker)) {
        throw "Phase 3F template injection marker is missing."
    }

    $combined = $template.Replace($calleeMarker, $calleeSource)
    $combined = $combined.Replace($wrapperMarker, $wrapperSource)

    [System.IO.File]::WriteAllText(
        $mainOut,
        $combined,
        [System.Text.UTF8Encoding]::new($false)
    )

    Write-Host ""
    Write-Host "[Phase3F] READY"
    Write-Host "[Phase3F] Callee source:  $calleeFile"
    Write-Host "[Phase3F] Wrapper source: $wrapperFile"
    Write-Host "[Phase3F] XDK source:     $mainOut"
}
finally {
    Pop-Location
}
