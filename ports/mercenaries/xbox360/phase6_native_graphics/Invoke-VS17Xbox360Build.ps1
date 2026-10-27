[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GeneratedMain,

    [Parameter(Mandatory = $true)]
    [string]$GeneratedEnv,

    [Parameter(Mandatory = $true)]
    [string]$GeneratedShardDir,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedBuildTag,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedEnvCookie,

    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$Configuration = "Release",
    [string]$Platform = "Xbox 360",
    [string]$CleanLog = "",
    [string]$BuildLog = "",
    [string]$PublishedXex = "",
    [string]$ShadowBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port",
    [switch]$DisableShadowBuild,
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-VS17Devenv {
    $command = Get-Command "devenv.com" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        $candidate = [string]$command.Source
        try {
            $major = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($candidate).ProductMajorPart
            if ($major -eq 15) {
                return $candidate
            }
        }
        catch {}
    }

    $programFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
    $vswhere = Join-Path $programFilesX86 "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $vswhere) {
        $found = @(
            & $vswhere -products * -version "[15.0,16.0)" -find "Common7\IDE\devenv.com" 2>$null |
                Where-Object { $_ -and (Test-Path -LiteralPath $_) }
        )

        if (@($found).Count -gt 0) {
            return [string]@($found)[0]
        }
    }

    $fallbacks = @(
        "C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\Common7\IDE\devenv.com",
        "C:\Program Files (x86)\Microsoft Visual Studio\2017\Professional\Common7\IDE\devenv.com",
        "C:\Program Files (x86)\Microsoft Visual Studio\2017\Enterprise\Common7\IDE\devenv.com",
        "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\Common7\IDE\devenv.com"
    )
    foreach ($candidate in $fallbacks) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw "Visual Studio 2017 devenv.com was not found. The helper searched VS 2017 / version 15.x plus the standard 2017 install paths."
}

function Sync-SolutionShadow {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$DestinationRoot
    )

    if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
        throw "Source Xbox 360 solution root does not exist: $SourceRoot"
    }

    $robocopy = Join-Path $env:SystemRoot "System32\robocopy.exe"
    if (-not (Test-Path -LiteralPath $robocopy -PathType Leaf)) {
        throw "robocopy.exe was not found; cannot create fast local shadow build"
    }

    if (-not (Test-Path -LiteralPath $DestinationRoot -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
    }

    $started = Get-Date
    $args = @(
        $SourceRoot,
        $DestinationRoot,
        "/MIR",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/R:1",
        "/W:1",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP",
        "/XD",
        ".vs",
        "Debug",
        "Release",
        "x64",
        "Win32",
        "ipch",
        "translated_shards",
        "/XF",
        "main.cpp",
        "phase4c_env.cpp",
        "phase5_env.cpp",
        "*.obj",
        "*.pdb",
        "*.ilk",
        "*.idb",
        "*.tlog",
        "*.lastbuildstate",
        "*.xex",
        "*.log",
        "*.suo",
        "*.user",
        "*.vcxproj"
    )

    & $robocopy @args | Out-Null
    $rc = $LASTEXITCODE
    if ($rc -ge 8) {
        throw "Fast local shadow sync failed (robocopy exit $rc)"
    }

    # Keep generated True-TU project injection persistent in the local shadow.
    # Robocopy intentionally excludes *.vcxproj; sync the underlying source
    # project only when its base content changed. This prevents every build
    # from erasing/re-inserting the same 64 ClCompile items and touching the
    # project timestamp.
    $markerPattern = '(?s)\r?\n\s*<!-- BEGIN PHASE6 TRUE TU SHARDS -->.*?<!-- END PHASE6 TRUE TU SHARDS -->\s*'
    $sourceProjects = @(Get-ChildItem -LiteralPath $SourceRoot -Filter "*.vcxproj" -File -Recurse)
    foreach ($sourceProject in $sourceProjects) {
        $relativeProject = $sourceProject.FullName.Substring($SourceRoot.Length).TrimStart('\')
        $destProject = Join-Path $DestinationRoot $relativeProject
        $destParent = Split-Path -Parent $destProject
        if (-not (Test-Path -LiteralPath $destParent -PathType Container)) {
            New-Item -ItemType Directory -Force -Path $destParent | Out-Null
        }

        $sourceProjectText = Get-Content -LiteralPath $sourceProject.FullName -Raw
        $sourceBase = [regex]::Replace($sourceProjectText, $markerPattern, [Environment]::NewLine)

        if (-not (Test-Path -LiteralPath $destProject -PathType Leaf)) {
            [System.IO.File]::WriteAllText(
                $destProject,
                $sourceBase,
                (New-Object System.Text.UTF8Encoding($false))
            )
            continue
        }

        $destProjectText = Get-Content -LiteralPath $destProject -Raw
        $destBase = [regex]::Replace($destProjectText, $markerPattern, [Environment]::NewLine)
        if ($destBase -cne $sourceBase) {
            [System.IO.File]::WriteAllText(
                $destProject,
                $sourceBase,
                (New-Object System.Text.UTF8Encoding($false))
            )
        }
    }

    $elapsed = (Get-Date) - $started
    Write-Host ("[XDK-BUILD] Shadow sync     : PASS source='{0}' dest='{1}' elapsed={2:N2}s robocopy_rc={3}" -f $SourceRoot, $DestinationRoot, $elapsed.TotalSeconds, $rc)
    Write-Host "[XDK-BUILD] Shadow policy   : generated main/env/shards excluded from mirror; content sync owns their timestamps"
    return $DestinationRoot
}

function Get-ProjectCompiledFiles {
    param([string]$ProjectPath)

    $projectDir = Split-Path -Parent $ProjectPath
    $projectText = Get-Content -LiteralPath $ProjectPath -Raw
    $matches = [regex]::Matches(
        $projectText,
        '<ClCompile\b[^>]*\bInclude="([^"]+)"',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    $rows = @()
    foreach ($match in $matches) {
        $include = [string]$match.Groups[1].Value
        if ([string]::IsNullOrWhiteSpace($include)) { continue }
        if ($include.Contains('$(')) { continue }

        $relative = $include -replace '/', '\'
        $full = [System.IO.Path]::GetFullPath((Join-Path $projectDir $relative))
        $rows += [pscustomobject]@{
            Include = $include
            FullPath = $full
            Leaf = [System.IO.Path]::GetFileName($full)
        }
    }

    return $rows
}

function Resolve-SolutionProjectAndSources {
    param([string]$RootPath)

    if (-not (Test-Path -LiteralPath $RootPath -PathType Container)) {
        throw "Xbox 360 solution root does not exist: $RootPath"
    }

    $solutions = @(Get-ChildItem -LiteralPath $RootPath -Filter "*.sln" -File)
    if (@($solutions).Count -eq 0) {
        $solutions = @(Get-ChildItem -LiteralPath $RootPath -Filter "*.sln" -File -Recurse)
    }
    if (@($solutions).Count -ne 1) {
        throw "Expected exactly one .sln under '$RootPath', found $(@($solutions).Count)."
    }

    $solution = $solutions[0]
    $solutionText = Get-Content -LiteralPath $solution.FullName -Raw
    $projectMatches = [regex]::Matches(
        $solutionText,
        'Project\("[^"]+"\)\s*=\s*"([^"]+)",\s*"([^"]+\.vcxproj)"',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    $projects = @()
    foreach ($match in $projectMatches) {
        $projectName = [string]$match.Groups[1].Value
        $relative = [string]$match.Groups[2].Value
        $relative = $relative -replace '/', '\'
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $solution.DirectoryName $relative))
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $compiled = @(Get-ProjectCompiledFiles -ProjectPath $candidate)
            $mainMatches = @($compiled | Where-Object { $_.Leaf -ieq "main.cpp" })
            if (@($mainMatches).Count -eq 1) {
                $projects += [pscustomobject]@{
                    Name = $projectName
                    Path = $candidate
                    Compiled = $compiled
                    Main = $mainMatches[0]
                }
            }
        }
    }

    if (@($projects).Count -ne 1) {
        throw "Expected exactly one solution project compiling main.cpp, found $(@($projects).Count)."
    }

    $project = $projects[0]

    $monolithic = @($project.Compiled | Where-Object { $_.Leaf -ieq "main_monolithic.cpp" })
    if (@($monolithic).Count -gt 0) {
        throw "main_monolithic.cpp is listed as a compiled source in '$($project.Path)'. Remove/exclude it before building."
    }

    $envMatches = @($project.Compiled | Where-Object { $_.Leaf -ieq "phase4c_env.cpp" })
    if (@($envMatches).Count -eq 0) {
        $envMatches = @($project.Compiled | Where-Object { $_.Leaf -ieq "phase5_env.cpp" })
    }
    if (@($envMatches).Count -eq 0) {
        $envMatches = @($project.Compiled | Where-Object { $_.Leaf -match "(?i)env\.cpp$" })
    }
    if (@($envMatches).Count -ne 1) {
        throw "Expected exactly one compiled env CPP in '$($project.Path)', found $(@($envMatches).Count)."
    }

    return @{
        SolutionPath = $solution.FullName
        SolutionText = $solutionText
        ProjectName = $project.Name
        ProjectPath = $project.Path
        MainPath = $project.Main.FullPath
        EnvPath = $envMatches[0].FullPath
        MainDir = Split-Path -Parent $project.Main.FullPath
    }
}

function Assert-SolutionConfiguration {
    param(
        [string]$SolutionText,
        [string]$ConfigurationName
    )

    $section = [regex]::Match(
        $SolutionText,
        'GlobalSection\(SolutionConfigurationPlatforms\) = preSolution(?<body>.*?)EndGlobalSection',
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )
    if (-not $section.Success) {
        throw "Could not find SolutionConfigurationPlatforms in the .sln."
    }

    $available = @(
        [regex]::Matches($section.Groups["body"].Value, '(?m)^\s*([^=\r\n]+?)\s*=') |
            ForEach-Object { $_.Groups[1].Value.Trim() } |
            Select-Object -Unique
    )

    if ($available -notcontains $ConfigurationName) {
        throw "Solution configuration '$ConfigurationName' was not found. Available: $($available -join ', ')"
    }
}

function Assert-FileHashMatch {
    param(
        [string]$Expected,
        [string]$Actual,
        [string]$Label
    )

    $expectedHash = (Get-FileHash -LiteralPath $Expected -Algorithm SHA256).Hash
    $actualHash = (Get-FileHash -LiteralPath $Actual -Algorithm SHA256).Hash
    if ($expectedHash -ne $actualHash) {
        throw "$Label copy verification failed"
    }
}

function Update-ProjectTrueTUItems {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectPath,
        [Parameter(Mandatory = $true)][string]$ProjectDirectory,
        [Parameter(Mandatory = $true)][System.IO.FileInfo[]]$ShardFiles
    )

    $begin = "  <!-- BEGIN PHASE6 TRUE TU SHARDS -->"
    $end = "  <!-- END PHASE6 TRUE TU SHARDS -->"
    $text = Get-Content -LiteralPath $ProjectPath -Raw
    $pattern = '(?s)\r?\n\s*<!-- BEGIN PHASE6 TRUE TU SHARDS -->.*?<!-- END PHASE6 TRUE TU SHARDS -->\s*'
    $text = [regex]::Replace($text, $pattern, "`r`n")

    if (@($ShardFiles).Count -gt 0) {
        $items = @()
        foreach ($shard in ($ShardFiles | Sort-Object Name)) {
            $relative = $shard.FullName.Substring($ProjectDirectory.Length).TrimStart('\')
            $escaped = [System.Security.SecurityElement]::Escape($relative)
            $items += "    <ClCompile Include=`"$escaped`" />"
        }

        $block = @(
            $begin
            "  <ItemGroup>"
            ($items -join "`r`n")
            "  </ItemGroup>"
            $end
        ) -join "`r`n"

        $projectClose = $text.LastIndexOf("</Project>")
        if ($projectClose -lt 0) {
            throw "Could not locate </Project> while injecting true-TU shard compile items."
        }
        $text = $text.Insert($projectClose, $block + "`r`n")
    }

    $current = Get-Content -LiteralPath $ProjectPath -Raw
    if ($current -ceq $text) { return $false }
    [System.IO.File]::WriteAllText($ProjectPath, $text, [System.Text.UTF8Encoding]::new($false))
    return $true
}
function Sync-FileIfChanged {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $sourceHash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash
    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        $destinationHash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash
        if ($sourceHash -eq $destinationHash) {
            return $false
        }
    }

    $destinationParent = Split-Path -Parent $Destination
    if (-not (Test-Path -LiteralPath $destinationParent -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
    }

    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    $copiedHash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash
    if ($copiedHash -ne $sourceHash) {
        throw "$Label content-addressed sync verification failed"
    }

    return $true
}

foreach ($required in @($GeneratedMain, $GeneratedEnv, $GeneratedShardDir)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Generated build input missing: $required"
    }
}

$effectiveSolutionRoot = $SolutionRoot
if (-not $DisableShadowBuild) {
    $sourceFull = [System.IO.Path]::GetFullPath($SolutionRoot).TrimEnd('\')
    $shadowFull = [System.IO.Path]::GetFullPath($ShadowBuildRoot).TrimEnd('\')
    if ($sourceFull -ieq $shadowFull) {
        throw "ShadowBuildRoot must differ from SolutionRoot"
    }
    $effectiveSolutionRoot = Sync-SolutionShadow -SourceRoot $sourceFull -DestinationRoot $shadowFull
    Write-Host "[XDK-BUILD] Build location  : LOCAL SHADOW (OneDrive avoided for compile/intermediates)"
}
else {
    Write-Host "[XDK-BUILD] Build location  : SOURCE TREE (shadow disabled)"
}

$resolved = Resolve-SolutionProjectAndSources -RootPath $effectiveSolutionRoot
$solutionPath = [string]$resolved.SolutionPath
$projectName = [string]$resolved.ProjectName
$projectPath = [string]$resolved.ProjectPath
$mainPath = [string]$resolved.MainPath
$envPath = [string]$resolved.EnvPath
$mainDir = [string]$resolved.MainDir
$solutionText = [string]$resolved.SolutionText
$solutionConfiguration = "$Configuration|$Platform"

Assert-SolutionConfiguration -SolutionText $solutionText -ConfigurationName $solutionConfiguration

Write-Host "[XDK-BUILD] Effective root : $effectiveSolutionRoot"
Write-Host "[XDK-BUILD] Solution       : $solutionPath"
Write-Host "[XDK-BUILD] Project        : $projectName ($projectPath)"
Write-Host "[XDK-BUILD] main.cpp       : $mainPath"
Write-Host "[XDK-BUILD] env source     : $envPath"
Write-Host "[XDK-BUILD] Configuration  : $solutionConfiguration"

$syncStart = Get-Date
$mainChanged = Sync-FileIfChanged -Source $GeneratedMain -Destination $mainPath -Label "main.cpp"
$envChanged = Sync-FileIfChanged -Source $GeneratedEnv -Destination $envPath -Label "env CPP"

$destinationShards = Join-Path $mainDir "translated_shards"
if (-not (Test-Path -LiteralPath $destinationShards -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $destinationShards | Out-Null
}

$sourceCppShards = @(Get-ChildItem -LiteralPath $GeneratedShardDir -Filter "translated_*.cpp" -File -ErrorAction SilentlyContinue | Sort-Object Name)
$trueTuMode = @($sourceCppShards).Count -gt 0
if ($trueTuMode) {
    $sourceShards = $sourceCppShards
    $sourceAuxiliary = @(Get-ChildItem -LiteralPath $GeneratedShardDir -Filter "*.h" -File -ErrorAction SilentlyContinue | Sort-Object Name)
    Write-Host ("[XDK-BUILD] Shard mode      : TRUE TU ({0} compiled .cpp shards)" -f @($sourceShards).Count)
}
else {
    $sourceShards = @(Get-ChildItem -LiteralPath $GeneratedShardDir -Filter "*.inl" -File | Sort-Object Name)
    $sourceAuxiliary = @()
    Write-Host ("[XDK-BUILD] Shard mode      : LEGACY INCLUDE ({0} .inl shards)" -f @($sourceShards).Count)
}

if (@($sourceShards).Count -lt 1) {
    throw "Generated shard directory contains neither translated_*.cpp nor *.inl shards."
}

$sourceNames = @{}
foreach ($sourceShard in @($sourceShards + $sourceAuxiliary)) {
    $sourceNames[$sourceShard.Name.ToLowerInvariant()] = $true
}

$staleShards = @(
    Get-ChildItem -LiteralPath $destinationShards -File -ErrorAction SilentlyContinue |
        Where-Object {
            ($_.Extension -in @(".inl", ".cpp", ".h")) -and
            -not $sourceNames.ContainsKey($_.Name.ToLowerInvariant())
        }
)
foreach ($staleShard in $staleShards) {
    Remove-Item -LiteralPath $staleShard.FullName -Force
}

$changedShardCount = 0
$unchangedShardCount = 0
foreach ($sourceShard in @($sourceShards + $sourceAuxiliary)) {
    $destinationShard = Join-Path $destinationShards $sourceShard.Name
    $changed = Sync-FileIfChanged -Source $sourceShard.FullName -Destination $destinationShard -Label $sourceShard.Name
    if ($changed) { ++$changedShardCount } else { ++$unchangedShardCount }
}

Assert-FileHashMatch -Expected $GeneratedMain -Actual $mainPath -Label "main.cpp"
Assert-FileHashMatch -Expected $GeneratedEnv -Actual $envPath -Label "env CPP"

$destShards = @(
    if ($trueTuMode) {
        Get-ChildItem -LiteralPath $destinationShards -Filter "translated_*.cpp" -File | Sort-Object Name
    }
    else {
        Get-ChildItem -LiteralPath $destinationShards -Filter "*.inl" -File | Sort-Object Name
    }
)
if (@($sourceShards).Count -ne @($destShards).Count) {
    throw "translated_shards count mismatch: generated=$(@($sourceShards).Count), solution=$(@($destShards).Count)"
}
for ($i = 0; $i -lt @($sourceShards).Count; $i++) {
    if ($sourceShards[$i].Name -ne $destShards[$i].Name) {
        throw "translated_shards filename mismatch at index $i"
    }
    Assert-FileHashMatch -Expected $sourceShards[$i].FullName -Actual $destShards[$i].FullName -Label $sourceShards[$i].Name
}
foreach ($sourceAux in $sourceAuxiliary) {
    Assert-FileHashMatch -Expected $sourceAux.FullName -Actual (Join-Path $destinationShards $sourceAux.Name) -Label $sourceAux.Name
}

$projectChanged = $false
if ($trueTuMode) {
    if ($DisableShadowBuild) {
        throw "True TU mode requires the fast local shadow build so generated project items do not mutate the source solution. Remove -DisableFastLocalBuild."
    }
    $compiledShardFiles = @(Get-ChildItem -LiteralPath $destinationShards -Filter "translated_*.cpp" -File | Sort-Object Name)
    $projectChanged = Update-ProjectTrueTUItems -ProjectPath $projectPath -ProjectDirectory (Split-Path -Parent $projectPath) -ShardFiles $compiledShardFiles
}
else {
    $projectChanged = Update-ProjectTrueTUItems -ProjectPath $projectPath -ProjectDirectory (Split-Path -Parent $projectPath) -ShardFiles @()
}
$syncElapsed = (Get-Date) - $syncStart
$mainSyncState = if ($mainChanged) { "CHANGED" } else { "UNCHANGED" }
$envSyncState = if ($envChanged) { "CHANGED" } else { "UNCHANGED" }
Write-Host ("[XDK-BUILD] Content sync    : main={0} env={1} shards_changed={2} shards_unchanged={3} stale_removed={4} project_changed={5} elapsed={6:N2}s" -f $mainSyncState, $envSyncState, $changedShardCount, $unchangedShardCount, @($staleShards).Count, $projectChanged, $syncElapsed.TotalSeconds)

$solutionMainText = Get-Content -LiteralPath $mainPath -Raw
$solutionEnvText = Get-Content -LiteralPath $envPath -Raw
if (-not $solutionMainText.Contains($ExpectedBuildTag)) {
    throw "Solution main.cpp does not contain expected build tag: $ExpectedBuildTag"
}
if ($solutionMainText -notmatch [regex]::Escape($ExpectedEnvCookie) -or
    $solutionEnvText -notmatch [regex]::Escape($ExpectedEnvCookie)) {
    throw "Solution main/env cookie verification failed: $ExpectedEnvCookie"
}

Write-Host "[XDK-BUILD] SOURCE SYNC: PASS"
Write-Host "[XDK-BUILD] Shards synced  : $(@($sourceShards).Count)"

$devenv = Resolve-VS17Devenv
Write-Host "[XDK-BUILD] VS2017 builder   : $devenv"

if ([string]::IsNullOrWhiteSpace($CleanLog)) {
    $CleanLog = Join-Path $effectiveSolutionRoot "phase6-vs17-clean.log"
}
if ([string]::IsNullOrWhiteSpace($BuildLog)) {
    $BuildLog = Join-Path $effectiveSolutionRoot "phase6-vs17-build.log"
}
foreach ($log in @($CleanLog, $BuildLog)) {
    $parent = Split-Path -Parent $log
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    if (Test-Path -LiteralPath $log) {
        Remove-Item -LiteralPath $log -Force
    }
}

if ($SkipClean) {
    Write-Host "[XDK-BUILD] CLEAN: SKIPPED (incremental build requested)"
}
else {
    Write-Host "[XDK-BUILD] CLEAN: $solutionConfiguration"
    & $devenv $solutionPath /Clean $solutionConfiguration /Project $projectName /Out $CleanLog
    $cleanRc = $LASTEXITCODE
    if ($cleanRc -ne 0) {
        Write-Host "[XDK-BUILD] CLEAN LOG TAIL:"
        if (Test-Path -LiteralPath $CleanLog) {
            Get-Content -LiteralPath $CleanLog -Tail 120
        }
        throw "VS17 solution clean failed (exit $cleanRc)"
    }
    Write-Host "[XDK-BUILD] CLEAN: PASS"
}

$buildStart = Get-Date
Write-Host "[XDK-BUILD] BUILD: $solutionConfiguration"
& $devenv $solutionPath /Build $solutionConfiguration /Project $projectName /Out $BuildLog
$buildRc = $LASTEXITCODE
$buildElapsed = (Get-Date) - $buildStart
if ($buildRc -ne 0) {
    if (Test-Path -LiteralPath $BuildLog) {
        Write-Host "[XDK-BUILD] COMPILER/LINKER ERRORS:"
        $errorLines = @(
            Select-String -LiteralPath $BuildLog -Pattern @(
                "error C[0-9]+",
                "fatal error C[0-9]+",
                "error LNK[0-9]+",
                "fatal error LNK[0-9]+",
                "error MSB[0-9]+",
                ": error "
            ) -CaseSensitive:$false -ErrorAction SilentlyContinue
        )
        if ($errorLines.Count -gt 0) {
            Write-Host "[XDK-BUILD] ERROR FAMILY SUMMARY:"
            $errorLines |
                ForEach-Object {
                    $line = $_.Line
                    $line = $line -replace '^.*?\):\s*', ''
                    $line = $line -replace '^.*?:\s*(?=(?:fatal )?error\s)', ''
                    $line
                } |
                Group-Object |
                Sort-Object Count -Descending |
                Select-Object -First 30 |
                ForEach-Object {
                    Write-Host ("[XDK-BUILD] x{0} {1}" -f $_.Count, $_.Name)
                }

            Write-Host "[XDK-BUILD] LAST COMPILER/LINKER ERRORS:"
            $errorLines | Select-Object -Last 80 | ForEach-Object {
                Write-Host $_.Line
            }
        }
        else {
            Write-Host "[XDK-BUILD] No canonical compiler/linker error line matched; showing tail."
        }

        Write-Host "[XDK-BUILD] BUILD LOG TAIL:"
        Get-Content -LiteralPath $BuildLog -Tail 180
    }
    throw "VS17 Xbox 360 Release build failed (exit $buildRc)"
}

$solutionMainText = Get-Content -LiteralPath $mainPath -Raw
if (-not $solutionMainText.Contains($ExpectedBuildTag)) {
    throw "Post-build source identity gate failed: main.cpp lost expected build tag"
}

$xexSearchRoots = @(
    $effectiveSolutionRoot,
    $SolutionRoot
) | Where-Object {
    -not [string]::IsNullOrWhiteSpace($_) -and
    (Test-Path -LiteralPath $_ -PathType Container)
} | ForEach-Object {
    [IO.Path]::GetFullPath($_).TrimEnd('\')
} | Select-Object -Unique

$xexCandidates = @(
    foreach ($xexRoot in $xexSearchRoots) {
        Get-ChildItem -LiteralPath $xexRoot -Filter "*.xex" -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -ge $buildStart.AddSeconds(-2) }
    }
) | Sort-Object LastWriteTime -Descending

Write-Host ("[XDK-BUILD] XEX search roots : {0}" -f ($xexSearchRoots -join " ; "))

$buildReportedUpToDate = $false
if (Test-Path -LiteralPath $BuildLog) {
    $buildReportedUpToDate = $null -ne (
        Select-String -LiteralPath $BuildLog -Pattern "up-to-date" -CaseSensitive:$false -ErrorAction SilentlyContinue |
            Select-Object -First 1
    )
}

$generatedInputsUnchanged = (
    (-not $mainChanged) -and
    (-not $envChanged) -and
    ($changedShardCount -eq 0) -and
    (@($staleShards).Count -eq 0) -and
    (-not $projectChanged)
)

$builtXex = $null
$xexDisposition = ""

if (@($xexCandidates).Count -gt 0) {
    $builtXex = $xexCandidates[0]
    $xexDisposition = "Fresh"
}
elseif ($SkipClean -and $generatedInputsUnchanged -and $buildReportedUpToDate) {
    $existingXexCandidates = @(
        foreach ($xexRoot in $xexSearchRoots) {
            Get-ChildItem -LiteralPath $xexRoot -Filter "*.xex" -File -Recurse -ErrorAction SilentlyContinue
        }
    ) | Sort-Object LastWriteTime -Descending

    if (@($existingXexCandidates).Count -gt 0) {
        $builtXex = $existingXexCandidates[0]
        $xexDisposition = "Reused up-to-date"
    }
}

Write-Host "[XDK-BUILD] BUILD: PASS"
Write-Host ("[XDK-BUILD] Build elapsed  : {0:N2}s" -f $buildElapsed.TotalSeconds)
Write-Host "[XDK-BUILD] Clean log      : $CleanLog"
Write-Host "[XDK-BUILD] Build log      : $BuildLog"
Write-Host ("[XDK-BUILD] VS up-to-date  : {0}" -f $buildReportedUpToDate)
Write-Host ("[XDK-BUILD] Inputs unchanged: {0}" -f $generatedInputsUnchanged)

if ($null -ne $builtXex) {
    Write-Host ("[XDK-BUILD] XEX disposition: {0}" -f $xexDisposition)
    Write-Host "[XDK-BUILD] XEX path       : $($builtXex.FullName)"
    Write-Host "[XDK-BUILD] XEX timestamp  : $($builtXex.LastWriteTime)"
    Write-Host "[XDK-BUILD] XEX size       : $($builtXex.Length) bytes"

    if (-not [string]::IsNullOrWhiteSpace($PublishedXex)) {
        $publishParent = Split-Path -Parent $PublishedXex
        if (-not (Test-Path -LiteralPath $publishParent -PathType Container)) {
            New-Item -ItemType Directory -Force -Path $publishParent | Out-Null
        }
        Copy-Item -LiteralPath $builtXex.FullName -Destination $PublishedXex -Force
        Assert-FileHashMatch -Expected $builtXex.FullName -Actual $PublishedXex -Label "Published XEX"
        $published = Get-Item -LiteralPath $PublishedXex
        Write-Host "[XDK-BUILD] Published XEX  : $($published.FullName)"
        Write-Host "[XDK-BUILD] Published size : $($published.Length) bytes"
    }
}
elseif ($buildReportedUpToDate -and -not $generatedInputsUnchanged) {
    throw "VS17 reported the project up-to-date even though generated inputs changed; refusing to reuse a potentially stale .xex."
}
else {
    throw ("VS17 reported build success, but no usable .xex was found under any build output root: " + ($xexSearchRoots -join " ; "))
}

Write-Host "[XDK-BUILD] FULL PIPELINE: PASS"
