[CmdletBinding()]
param(
    [string]$GameDirectory,
    [ValidateRange(2, 64)]
    [int]$MaxPasses = 32,
    [switch]$ResumeLowering
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$portRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\.."))
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $portRoot "..\.."))

if (-not $GameDirectory) {
    $GameDirectory = Join-Path $repoRoot "game_files\mercenaries-retail"
}

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$recompile = Join-Path $portRoot "scripts\Recompile.ps1"
$buildRoot = Join-Path $repoRoot "build\phase3n_final_abi_scale"
$analysisRoot = Join-Path $buildRoot "analysis"
$recompRoot = Join-Path $buildRoot "recomp"
$isolatedRecompRoot = Join-Path $buildRoot "runtime"
$generatedRoot = Join-Path $isolatedRecompRoot "gen"
$loweringReport = Join-Path $buildRoot "explicit-memory-lowering.json"
$portabilityReport = Join-Path $buildRoot "portability-audit.json"
$gateReport = Join-Path $buildRoot "phase3n-audit.json"
$manifestPath = Join-Path $buildRoot "generated-manifest.json"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found at $python. Run ports\mercenaries\scripts\Setup-Python.ps1 first."
}
if (-not (Test-Path -LiteralPath $recompile -PathType Leaf)) {
    throw "Recompile.ps1 not found at $recompile."
}

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null

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
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "")
    }
    finally {
        $sha.Dispose()
    }
}

Push-Location $repoRoot
try {
    Write-Host "[Phase3N] FINAL PHASE-3 ABI + SCALE GATE"
    Write-Host "[Phase3N] Stage A: full retail generated-tree audit"
    Write-Host ""

    Write-Host "[Phase3N] Running lowering unit tests..."
    Invoke-Python "-m" "unittest" "tools.recomp.test_lower_explicit_guest_memory"

    if (-not $ResumeLowering) {
        Write-Host ""
        Write-Host "[Phase3N] Recompiling the supported retail XBE in an isolated workspace..."

        # A fresh generated tree is a new evidence baseline. Do not aggregate
        # lowering/audit reports left by an older tree or by a failed previous
        # regeneration.
        $resumeLoweringReport = Join-Path $buildRoot "explicit-memory-lowering-resume.json"
        foreach ($staleReport in @(
            $loweringReport,
            $resumeLoweringReport,
            $portabilityReport,
            $gateReport,
            $manifestPath
        )) {
            Remove-Item -LiteralPath $staleReport -Force -ErrorAction SilentlyContinue
        }
        $recompileArgs = @{
            GameDirectory = $GameDirectory
            MaxPasses = $MaxPasses
            AnalysisRootOverride = $analysisRoot
            GeneratedRootOverride = $generatedRoot
            RecompRootOverride = $recompRoot
            SkipGeneratedProvenanceArchive = $true
            LowerExplicitGuestMemory = $true
            LoweringReport = $loweringReport
        }
        & $recompile @recompileArgs
    }
    else {
        Write-Host ""
        Write-Host "[Phase3N] Resume mode: preserving existing translated/patched tree."
        $summaryPath = Join-Path $recompRoot "summary.json"
        if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
            throw "Resume requested but recompiler summary is missing: $summaryPath"
        }
        if (-not (Test-Path -LiteralPath $generatedRoot -PathType Container)) {
            throw "Resume requested but generated tree is missing: $generatedRoot"
        }

        Write-Host "[Phase3N] Repairing known native-helper guest-pointer boundaries..."
        $bridgeRepair = Join-Path $phaseRoot "repair_guest_pointer_bridges.py"
        Invoke-Python $bridgeRepair $generatedRoot

        Write-Host "[Phase3N] Lowering existing patched tree to explicit guest-memory ABI..."
        $lowerer = Join-Path $repoRoot "tools\recomp\lower_explicit_guest_memory.py"
        $resumeLoweringReport = Join-Path $buildRoot "explicit-memory-lowering-resume.json"
        $priorLowering = $null
        if (Test-Path -LiteralPath $loweringReport -PathType Leaf) {
            $priorLowering = Get-Content -LiteralPath $loweringReport -Raw | ConvertFrom-Json
        }

        # A previous resume can finish lowering and then fail while the report
        # is being consolidated. Preserve that already-completed evidence
        # before this invocation overwrites the incremental report.
        $pendingLoweringData = $null
        if (Test-Path -LiteralPath $resumeLoweringReport -PathType Leaf) {
            $pendingLoweringData = Get-Content -LiteralPath $resumeLoweringReport -Raw | ConvertFrom-Json
        }

        Invoke-Python $lowerer $generatedRoot "--report" $resumeLoweringReport

        # Do not call this $resumeLowering: PowerShell variable names are
        # case-insensitive, so that collides with the typed [switch]
        # $ResumeLowering script parameter.
        $resumeLoweringData = Get-Content -LiteralPath $resumeLoweringReport -Raw | ConvertFrom-Json

        $priorReads = 0
        $priorWrites = 0
        $priorCompound = 0
        $priorIncDec = 0
        $priorBulk = 0
        if ($null -ne $priorLowering) {
            $priorReads = [int]$priorLowering.reads
            $priorWrites = [int]$priorLowering.writes
            $priorCompound = [int]$priorLowering.compound_writes
            $priorIncDec = [int]$priorLowering.incdec_writes
            if ($null -ne $priorLowering.PSObject.Properties["bulk_writes"]) {
                $priorBulk = [int]$priorLowering.bulk_writes
            }
        }

        $pendingReads = 0
        $pendingWrites = 0
        $pendingCompound = 0
        $pendingIncDec = 0
        $pendingBulk = 0
        if ($null -ne $pendingLoweringData) {
            $pendingReads = [int]$pendingLoweringData.reads
            $pendingWrites = [int]$pendingLoweringData.writes
            $pendingCompound = [int]$pendingLoweringData.compound_writes
            $pendingIncDec = [int]$pendingLoweringData.incdec_writes
            if ($null -ne $pendingLoweringData.PSObject.Properties["bulk_writes"]) {
                $pendingBulk = [int]$pendingLoweringData.bulk_writes
            }
        }

        $resumeBulk = 0
        if ($null -ne $resumeLoweringData.PSObject.Properties["bulk_writes"]) {
            $resumeBulk = [int]$resumeLoweringData.bulk_writes
        }

        [ordered]@{
            files = [int]$resumeLoweringData.files
            reads = $priorReads + $pendingReads + [int]$resumeLoweringData.reads
            writes = $priorWrites + $pendingWrites + [int]$resumeLoweringData.writes
            compound_writes = $priorCompound + $pendingCompound + [int]$resumeLoweringData.compound_writes
            incdec_writes = $priorIncDec + $pendingIncDec + [int]$resumeLoweringData.incdec_writes
            bulk_writes = $priorBulk + $pendingBulk + $resumeBulk
            source_bytes = [int64]$resumeLoweringData.source_bytes
            resumed = $true
        } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $loweringReport -Encoding UTF8

        # The incremental report is now folded into the durable aggregate.
        Remove-Item -LiteralPath $resumeLoweringReport -Force -ErrorAction SilentlyContinue

        Write-Host "[Phase3N] Auditing resumed post-lowering tree..."
        Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $generatedRoot
    }

    Write-Host ""
    Write-Host "[Phase3N] Running full post-patch portability audit..."
    $functionsPath = Join-Path $analysisRoot "disasm\\functions.json"
    if (-not (Test-Path -LiteralPath $functionsPath -PathType Leaf)) {
        throw "Phase 3N disassembly function database missing: $functionsPath"
    }
    Invoke-Python "-m" "tools.recomp.audit_phase3n_portability" $generatedRoot "--functions" $functionsPath "--output" $portabilityReport

    # Re-run the narrow scanner explicitly at the phase boundary. Recompile.ps1
    # already ran it; this makes the final report unambiguously post-lowering.
    Invoke-Python "-m" "tools.recomp.audit_explicit_guest_memory" $generatedRoot

    $summaryPath = Join-Path $recompRoot "summary.json"
    if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
        throw "Recompiler did not produce $summaryPath."
    }
    if (-not (Test-Path -LiteralPath $loweringReport -PathType Leaf)) {
        throw "Explicit-memory lowerer did not produce $loweringReport."
    }
    if (-not (Test-Path -LiteralPath $portabilityReport -PathType Leaf)) {
        throw "Portability audit did not produce $portabilityReport."
    }

    $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
    $lowering = Get-Content -LiteralPath $loweringReport -Raw | ConvertFrom-Json
    $portability = Get-Content -LiteralPath $portabilityReport -Raw | ConvertFrom-Json

    $generatedFiles = @(
        Get-ChildItem -LiteralPath $generatedRoot -Filter "recomp_*.c" -File |
        Sort-Object Name
    )
    if ($generatedFiles.Count -eq 0) {
        throw "No generated C files were produced under $generatedRoot."
    }

    $manifestRows = @()
    $digestLines = @()
    foreach ($file in $generatedFiles) {
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        $manifestRows += [ordered]@{
            file = $file.Name
            bytes = [int64]$file.Length
            sha256 = $hash
        }
        $digestLines += ("{0}:{1}:{2}" -f $file.Name, $file.Length, $hash)
    }
    $treeSha256 = Get-CompositeSha256 -Lines $digestLines

    [ordered]@{
        phase = "3N-A"
        purpose = "final Phase-3 full generated-tree ABI/portability audit"
        generated_root = $generatedRoot
        generated_tree_sha256 = $treeSha256
        files = $manifestRows
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

    $translated = [int]$summary.translated
    $total = [int]$summary.total
    $failed = [int]$summary.failed
    $unresolved = [int]$summary.unresolved_stubs
    $residualUnresolved = [int]$portability.residual_unresolved_stubs
    $fatal = [int]$portability.fatal_count

    $gatePass = (
        $failed -eq 0 -and
        $residualUnresolved -eq 0 -and
        $fatal -eq 0
    )

    $bulkWrites = 0
    if ($null -ne $lowering.PSObject.Properties["bulk_writes"]) {
        $bulkWrites = [int]$lowering.bulk_writes
    }

    $nextMessage = "Resolve every failed translation, residual post-patch unresolved stub, or Gate-3-fatal portability leak before scale testing."
    if ($gatePass) {
        $nextMessage = "Select and emit the Phase 3N-B XDK scale-pack harness."
    }

    $gate = [ordered]@{
        phase = "3N-A"
        purpose = "full post-patch generated-tree audit before XDK scale proof"
        generated_tree_sha256 = $treeSha256
        recompiler = [ordered]@{
            translated = $translated
            total = $total
            failed = $failed
            unresolved_stubs_before_patching = $unresolved
            residual_unresolved_stubs_after_patching = $residualUnresolved
        }
        lowering = [ordered]@{
            files = [int]$lowering.files
            reads = [int]$lowering.reads
            writes = [int]$lowering.writes
            compound_writes = [int]$lowering.compound_writes
            incdec_writes = [int]$lowering.incdec_writes
            bulk_writes = $bulkWrites
            source_bytes = [int64]$lowering.source_bytes
        }
        portability = [ordered]@{
            function_bodies = [int]$portability.function_bodies
            fatal_count = $fatal
            failed_translation_stubs = [int]$portability.failed_translation_stubs
            residual_unresolved_stubs = $residualUnresolved
            platform_surfaces = $portability.platform_surfaces
            translated_surfaces = $portability.translated_surfaces
        }
        gate_a_pass = $gatePass
        next = $nextMessage
    }

    $gate | ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath $gateReport -Encoding UTF8

    Write-Host ""
    Write-Host "[Phase3N] ===== STAGE A SUMMARY ====="
    Write-Host ("[Phase3N] Generated functions: {0}" -f $portability.function_bodies)
    Write-Host ("[Phase3N] Recompiler: {0}/{1} translated, failures={2}, raw unresolved={3}, residual unresolved={4}" -f $translated, $total, $failed, $unresolved, $residualUnresolved)
    Write-Host ("[Phase3N] Explicit lowering: reads={0}, writes={1}, compound={2}, inc/dec={3}, bulk={4}" -f $lowering.reads, $lowering.writes, $lowering.compound_writes, $lowering.incdec_writes, $bulkWrites)
    Write-Host ("[Phase3N] Gate-3-fatal portability hits: {0}" -f $fatal)
    Write-Host ("[Phase3N] Generated tree SHA256: {0}" -f $treeSha256)
    Write-Host ("[Phase3N] Report: {0}" -f $gateReport)

    if (-not $gatePass) {
        Write-Host "[Phase3N] PHASE 3N-A RESULT: FAIL"
        throw "Phase 3N-A did not satisfy the strict final-tree audit."
    }

    Write-Host "[Phase3N] PHASE 3N-A RESULT: PASS"
    Write-Host "[Phase3N] READY FOR 3N-B XDK SCALE-PACK SELECTION"
}
finally {
    Pop-Location
}
