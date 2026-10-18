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
$calleeFile = Join-Path $buildRoot "sub_0021AB90.c"
$wrapperFile = Join-Path $buildRoot "sub_001EF850.c"
$templatePath = Join-Path $phaseRoot "main_template.cpp"
$mainOut = Join-Path $buildRoot "main.cpp"

$expectedXbeHash = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
$wrapperAddress = "0x001EF850"
$calleeAddress = "0x0021AB90"

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

function Show-And-Reject-Dependency {
    param(
        [string]$Source,
        [string]$Label
    )

    $dependencyPattern = '\b(?:RECOMP_ICALL_SAFE|RECOMP_ITAIL|RECOMP_RDTSC|XBOX_MEMCPY|XBOX_REP_MOVS|xbox_[A-Za-z0-9_]+|__debugbreak)\b'
    $dependencyLines = @(
        $Source -split [Environment]::NewLine |
            Where-Object { $_ -match $dependencyPattern }
    )

    if ($dependencyLines.Count -ne 0) {
        Write-Host "[Phase3F] $Label dependency audit hit(s):" -ForegroundColor Yellow
        foreach ($line in $dependencyLines) {
            Write-Host "  $($line.Trim())" -ForegroundColor Yellow
        }
        throw "$Label unexpectedly depends on ICALL/kernel/runtime-copy services. Stop for re-audit."
    }

    # Candidate B is intentionally allowed to use only the scalar XMM0 path
    # already hardware-proven in Phase 3C. Reject every other SIMD/x87 shape.
    $forbiddenSimdPattern = '\b(?:fp_push|fp_pop|fp_top|fp_st|xmm[1-7]|g_xmm[1-7]|mm[0-7]|g_mm[0-7]|GUEST_READF64|GUEST_WRITEF64|recomp_xmm_(?!loadss\b)[A-Za-z0-9_]+)\b'
    $forbiddenSimdLines = @(
        $Source -split [Environment]::NewLine |
            Where-Object { $_ -match $forbiddenSimdPattern }
    )

    if ($forbiddenSimdLines.Count -ne 0) {
        Write-Host "[Phase3F] $Label unsupported SIMD/x87 audit hit(s):" -ForegroundColor Yellow
        foreach ($line in $forbiddenSimdLines) {
            Write-Host "  $($line.Trim())" -ForegroundColor Yellow
        }
        throw "$Label requires SIMD/x87 behavior beyond the Phase 3C-proven scalar XMM0 path."
    }
}

Push-Location $repoRoot
try {
    Write-Host "[Phase3F] Candidate B: 0x001EF850 -> tail-call -> 0x0021AB90"
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
        ([string]$_.start).Trim().ToUpperInvariant() -eq "0X001EF850"
    })
    $callee = @($functions | Where-Object {
        ([string]$_.start).Trim().ToUpperInvariant() -eq "0X0021AB90"
    })

    if ($wrapper.Count -ne 1) {
        throw "Wrapper 0x001EF850 was not detected exactly once."
    }
    if ($callee.Count -ne 1) {
        throw "Callee 0x0021AB90 was not detected exactly once."
    }

    Write-Host "[Phase3F] Wrapper metadata: size=$($wrapper[0].size) instructions=$($wrapper[0].num_instructions)"
    Write-Host "[Phase3F] Callee metadata:  size=$($callee[0].size) instructions=$($callee[0].num_instructions)"

    Write-Host "[Phase3F] Lifting callee $calleeAddress..."
    $calleeSource = Lift-One -Address $calleeAddress -OutputPath $calleeFile

    Write-Host "[Phase3F] Lifting wrapper $wrapperAddress..."
    $wrapperSource = Lift-One -Address $wrapperAddress -OutputPath $wrapperFile

    if ($calleeSource -notmatch 'void\s+sub_0021AB90\s*\(\s*void\s*\)') {
        throw "Callee generated with an unexpected function signature."
    }
    if ($wrapperSource -notmatch 'void\s+sub_001EF850\s*\(\s*void\s*\)') {
        throw "Wrapper generated with an unexpected function signature."
    }

    Show-And-Reject-Dependency -Source $calleeSource -Label "Callee"
    Show-And-Reject-Dependency -Source $wrapperSource -Label "Wrapper"

    $wrapperAdjustPattern = 'ecx\s*=\s*ecx\s*\+\s*0x28\s*;'
    if ($wrapperSource -notmatch $wrapperAdjustPattern) {
        Write-Host "[Phase3F] Wrapper source:" -ForegroundColor Yellow
        Write-Host $wrapperSource
        throw "Candidate B wrapper no longer has the expected ECX += 0x28 adjustment."
    }

    if ($wrapperSource -match '\b(?:GUEST_[A-Z0-9_]*|RECOMP_(?:READ|WRITE)[A-Z0-9_]*|xmm0|g_xmm0)\b') {
        Write-Host "[Phase3F] Wrapper source:" -ForegroundColor Yellow
        Write-Host $wrapperSource
        throw "Candidate B wrapper unexpectedly touches guest memory or XMM state before the tail call."
    }

    $calleeStorePattern = 'GUEST_WRITEF32\s*\(\s*ecx\s*\+\s*0xDC\s*,\s*xmm0\s*\)'
    if ($calleeSource -notmatch $calleeStorePattern) {
        Write-Host "[Phase3F] Callee source:" -ForegroundColor Yellow
        Write-Host $calleeSource
        throw "Candidate B callee no longer has the expected scalar XMM0 store to this+0xDC."
    }

    if ($wrapperSource -match 'GUEST_WRITEF32\s*\(') {
        throw "Candidate B wrapper unexpectedly writes scalar float guest memory before the tail boundary."
    }
    if ($calleeSource -match 'recomp_xmm_loadss\s*\(') {
        throw "Candidate B callee unexpectedly performs its own scalar XMM load."
    }

    if ($calleeSource -notmatch 'esp\s*\+=\s*8\s*;\s*return\s*;\s*/\*\s*ret 4\s*\*/') {
        Write-Host "[Phase3F] Callee source:" -ForegroundColor Yellow
        Write-Host $calleeSource
        throw "Candidate B callee no longer has the expected ret 4 guest-stack cleanup."
    }

    $wrapperTargetCalls = [regex]::Matches(
        $wrapperSource,
        '\bsub_0021AB90\s*\(\s*\)'
    )
    if ($wrapperTargetCalls.Count -ne 1) {
        throw "Wrapper did not emit exactly one direct call to sub_0021AB90."
    }

    if ($wrapperSource -notmatch 'tail jmp 0x0021AB90') {
        throw "Wrapper no longer lowers 0x0021AB90 as a tail jump."
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
        $_ -ne "001EF850" -and $_ -ne "0021AB90"
    })
    if ($unexpectedWrapperSubs.Count -ne 0) {
        throw "Wrapper calls unexpected translated function(s): $($unexpectedWrapperSubs -join ', ')."
    }

    $calleeSubs = @(
        [regex]::Matches($calleeSource, '\bsub_([0-9A-Fa-f]{8})\s*\(') |
            ForEach-Object { $_.Groups[1].Value.ToUpperInvariant() } |
            Sort-Object -Unique
    )
    $unexpectedCalleeSubs = @($calleeSubs | Where-Object { $_ -ne "0021AB90" })
    if ($unexpectedCalleeSubs.Count -ne 0) {
        throw "Callee unexpectedly calls translated function(s): $($unexpectedCalleeSubs -join ', ')."
    }

    $calleeLineCount = $calleeSource.Split([Environment]::NewLine).Count
    $wrapperLineCount = $wrapperSource.Split([Environment]::NewLine).Count
    if ($calleeLineCount -gt 140 -or $wrapperLineCount -gt 120) {
        throw "Candidate B is larger than the bounded Phase 3F limit. Callee=$calleeLineCount wrapper=$wrapperLineCount."
    }

    Write-Host "[Phase3F] Auditing generated functions for legacy guest-memory lvalues..."
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $calleeFile
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $wrapperFile

    $template = Get-Content -LiteralPath $templatePath -Raw
    $calleeMarker = "/*__PHASE3F_CALLEE__*/"
    $wrapperMarker = "/*__PHASE3F_WRAPPER__*/"

    if (-not $template.Contains($calleeMarker) -or
        -not $template.Contains($wrapperMarker)) {
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
    Write-Host "[Phase3F] Candidate:      0x001EF850 -> 0x0021AB90"
    Write-Host "[Phase3F] Wrapper shape:  ECX += 0x28, direct tail JMP, no PUSH32"
    Write-Host "[Phase3F] Callee shape:   store XMM0 scalar to ECX+0xDC, RET 4"
    Write-Host "[Phase3F] Callee source:  $calleeFile"
    Write-Host "[Phase3F] Wrapper source: $wrapperFile"
    Write-Host "[Phase3F] XDK source:     $mainOut"
}
finally {
    Pop-Location
}
