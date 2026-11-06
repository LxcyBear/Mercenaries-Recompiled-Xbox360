[CmdletBinding()]
param(
    [string]$ReconZip = "",
    [ValidateRange(1,5)][int]$Depth = 3,
    [ValidateRange(10,2000)][int]$Cap = 400
)
# K1 V7J - offline retail xboxrecomp + generated C + current V7I + 64 TrueTU
# No VS2017, XDK or Xbox interaction. Does not stage patched game source.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
Push-Location $repo
try {
    $tag = "[K1-V7J]"
    $analysis = Join-Path $repo "build\phase3n_final_abi_scale"
    $ranges = Join-Path $analysis "analysis\disasm\functions.json"
    $generated = Join-Path $analysis "runtime\gen"
    $emitter = Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
    $shards = Join-Path $repo "build\phase6_integration_map\k1_pixel_ntread_apc_stream_v6b\translated_shards"
    $current = Join-Path $repo "build\phase6_integration_map\k1_pixel_apc_iosb_v7i"
    $main = Join-Path $current "main.cpp"
    $manifest = Join-Path $current "v7i-manifest.json"
    $py = Join-Path $PSScriptRoot "Audit-K1V7JRecompSourceBatch.py"
    foreach ($file in @($ranges,$emitter,$main,$manifest,$py)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "$tag Required source input missing: $file"
        }
    }
    foreach ($dir in @($generated,$shards)) {
        if (-not (Test-Path -LiteralPath $dir -PathType Container)) {
            throw "$tag Required source directory missing: $dir"
        }
    }
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    & $python -m py_compile $py
    if ($LASTEXITCODE -ne 0) { throw "$tag Python syntax gate failed" }
    if ([string]::IsNullOrWhiteSpace($ReconZip)) {
        # Reuse cached xboxrecomp zip; do not regenerate/copy original XBE.
        # Probe likely repo-local locations first, then ZIP files under build/.
        $zipCandidates = New-Object 'System.Collections.Generic.List[string]'
        $searchRoots = @((Join-Path $repo "build"),(Join-Path $repo ".deps"))
        foreach ($folder in $searchRoots) {
            if (Test-Path -LiteralPath $folder -PathType Container) {
                Get-ChildItem -LiteralPath $folder -Filter "*.zip" -File -Recurse -ErrorAction SilentlyContinue |
                    ForEach-Object { $zipCandidates.Add($_.FullName) }
            }
        }
        Add-Type -AssemblyName System.IO.Compression
        $found = @()
        foreach ($candidate in $zipCandidates) {
            try {
                $z=[IO.Compression.ZipFile]::OpenRead($candidate)
                try {
                    $names = @($z.Entries | ForEach-Object { $_.FullName })
                    if ($names -contains "xboxrecomp_manifest.json" -and
                        $names -contains "merc360_frontier_summary.txt") {
                        $found += $candidate
                    }
                } finally { $z.Dispose() }
            } catch {
                # unrelated/invalid ZIP; do not interpret it as a source inventory
            }
        }
        if ($found.Count -eq 1) {
            $ReconZip = $found[0]
            Write-Host "$tag Found original xboxrecomp inventory ZIP: $ReconZip"
        } elseif ($found.Count -eq 0) {
            Write-Host "$tag No archived xboxrecomp manifest found. Using existing disasm/functions.json with accurate lower-confidence provenance."
            $ReconZip = ""
        } else {
            Write-Host "$tag Multiple cached xboxrecomp archives; using local disassembly ranges without selecting an arbitrary ZIP."
            $ReconZip = ""
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($ReconZip) -and
        -not (Test-Path -LiteralPath $ReconZip -PathType Leaf)) {
        throw "$tag Explicit xboxrecomp archive missing: $ReconZip"
    }
    $out = Join-Path $repo "build\phase6_integration_map\k1_v7j_source_batch"
    $args = @(
        "-u", $py,
        "--ranges", $ranges,
        "--generated", $generated,
        "--emitter", $emitter,
        "--shards", $shards,
        "--current-main", $main,
        "--current-manifest", $manifest,
        "--out", $out,
        "--depth", [string]$Depth,
        "--cap", [string]$Cap
    )
    Write-Host "$tag STARTING OFFLINE SOURCE-DEPENDENCY BATCH; depth=$Depth cap=$Cap"
    if (-not [string]::IsNullOrWhiteSpace($ReconZip)) {
        $args += @("--recon", $ReconZip)
        Write-Host "$tag Inventory: original xboxrecomp ZIP $ReconZip"
    } else {
        Write-Host "$tag Inventory: local original XBE disassembly functions.json (ZIP absent)"
    }
    & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw "$tag Source inventory failed closed. No XDK or Xbox touched."
    }
    $report = Join-Path $out "v7j_batch_frontiers.json"
    if (-not (Test-Path -LiteralPath $report -PathType Leaf)) {
        throw "$tag Missing final report"
    }
    Write-Host "$tag BATCH AUDIT COMPLETE. No game sources or retail XBE exported."
    Write-Host "$tag REVIEW CANDIDATES BEFORE ANY XDK BUILD."
} finally {
    Pop-Location
}
