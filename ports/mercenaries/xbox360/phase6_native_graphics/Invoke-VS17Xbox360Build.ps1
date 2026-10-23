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
    [string]$BuildLog = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-VS17Devenv {
    $command = Get-Command "devenv.com" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        $candidate = [string]$command.Source
        try {
            $major = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($candidate).ProductMajorPart
            if ($major -eq 17) {
                return $candidate
            }
        }
        catch {}
    }

    $programFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
    $vswhere = Join-Path $programFilesX86 "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $vswhere) {
        $found = @(
            & $vswhere -products * -version "[17.0,18.0)" -find "Common7\IDE\devenv.com" 2>$null |
                Where-Object { $_ -and (Test-Path -LiteralPath $_) }
        )

        if (@($found).Count -gt 0) {
            return [string]@($found)[0]
        }
    }

    $fallbacks = @(
        "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\devenv.com",
        "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\IDE\devenv.com",
        "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\IDE\devenv.com"
    )
    foreach ($candidate in $fallbacks) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw "Visual Studio 17 devenv.com was not found. Install/repair the VS17 Xbox 360 Debugger/XDK integration first."
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
        'Project\("[^"]+"\)\s*=\s*"[^"]+",\s*"([^"]+\.vcxproj)"',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    $projects = @()
    foreach ($match in $projectMatches) {
        $relative = [string]$match.Groups[1].Value
        $relative = $relative -replace '/', '\'
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $solution.DirectoryName $relative))
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $compiled = @(Get-ProjectCompiledFiles -ProjectPath $candidate)
            $mainMatches = @($compiled | Where-Object { $_.Leaf -ieq "main.cpp" })
            if (@($mainMatches).Count -eq 1) {
                $projects += [pscustomobject]@{
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

foreach ($required in @($GeneratedMain, $GeneratedEnv, $GeneratedShardDir)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Generated build input missing: $required"
    }
}

$resolved = Resolve-SolutionProjectAndSources -RootPath $SolutionRoot
$solutionPath = [string]$resolved.SolutionPath
$projectPath = [string]$resolved.ProjectPath
$mainPath = [string]$resolved.MainPath
$envPath = [string]$resolved.EnvPath
$mainDir = [string]$resolved.MainDir
$solutionText = [string]$resolved.SolutionText
$solutionConfiguration = "$Configuration|$Platform"

Assert-SolutionConfiguration -SolutionText $solutionText -ConfigurationName $solutionConfiguration

Write-Host "[XDK-BUILD] Solution       : $solutionPath"
Write-Host "[XDK-BUILD] Project        : $projectPath"
Write-Host "[XDK-BUILD] main.cpp       : $mainPath"
Write-Host "[XDK-BUILD] env source     : $envPath"
Write-Host "[XDK-BUILD] Configuration  : $solutionConfiguration"

Copy-Item -LiteralPath $GeneratedMain -Destination $mainPath -Force
Copy-Item -LiteralPath $GeneratedEnv -Destination $envPath -Force

$destinationShards = Join-Path $mainDir "translated_shards"
if (Test-Path -LiteralPath $destinationShards) {
    Remove-Item -LiteralPath $destinationShards -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $destinationShards | Out-Null
Copy-Item -Path (Join-Path $GeneratedShardDir "*") -Destination $destinationShards -Recurse -Force

Assert-FileHashMatch -Expected $GeneratedMain -Actual $mainPath -Label "main.cpp"
Assert-FileHashMatch -Expected $GeneratedEnv -Actual $envPath -Label "env CPP"

$sourceShards = @(Get-ChildItem -LiteralPath $GeneratedShardDir -Filter "*.inl" -File | Sort-Object Name)
$destShards = @(Get-ChildItem -LiteralPath $destinationShards -Filter "*.inl" -File | Sort-Object Name)
if (@($sourceShards).Count -ne @($destShards).Count) {
    throw "translated_shards count mismatch: generated=$(@($sourceShards).Count), solution=$(@($destShards).Count)"
}
for ($i = 0; $i -lt @($sourceShards).Count; $i++) {
    if ($sourceShards[$i].Name -ne $destShards[$i].Name) {
        throw "translated_shards filename mismatch at index $i"
    }
    Assert-FileHashMatch -Expected $sourceShards[$i].FullName -Actual $destShards[$i].FullName -Label $sourceShards[$i].Name
}

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
Write-Host "[XDK-BUILD] VS17 builder   : $devenv"

if ([string]::IsNullOrWhiteSpace($CleanLog)) {
    $CleanLog = Join-Path $SolutionRoot "phase6-vs17-clean.log"
}
if ([string]::IsNullOrWhiteSpace($BuildLog)) {
    $BuildLog = Join-Path $SolutionRoot "phase6-vs17-build.log"
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

Write-Host "[XDK-BUILD] CLEAN: $solutionConfiguration"
& $devenv $solutionPath /Clean $solutionConfiguration /Out $CleanLog
$cleanRc = $LASTEXITCODE
if ($cleanRc -ne 0) {
    Write-Host "[XDK-BUILD] CLEAN LOG TAIL:"
    if (Test-Path -LiteralPath $CleanLog) {
        Get-Content -LiteralPath $CleanLog -Tail 120
    }
    throw "VS17 solution clean failed (exit $cleanRc)"
}
Write-Host "[XDK-BUILD] CLEAN: PASS"

$buildStart = Get-Date
Write-Host "[XDK-BUILD] BUILD: $solutionConfiguration"
& $devenv $solutionPath /Build $solutionConfiguration /Out $BuildLog
$buildRc = $LASTEXITCODE
if ($buildRc -ne 0) {
    Write-Host "[XDK-BUILD] BUILD LOG TAIL:"
    if (Test-Path -LiteralPath $BuildLog) {
        Get-Content -LiteralPath $BuildLog -Tail 180
    }
    throw "VS17 Xbox 360 Release build failed (exit $buildRc)"
}

$solutionMainText = Get-Content -LiteralPath $mainPath -Raw
if (-not $solutionMainText.Contains($ExpectedBuildTag)) {
    throw "Post-build source identity gate failed: main.cpp lost expected build tag"
}

$xexCandidates = @(
    Get-ChildItem -LiteralPath $SolutionRoot -Filter "*.xex" -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $buildStart.AddSeconds(-2) } |
        Sort-Object LastWriteTime -Descending
)

Write-Host "[XDK-BUILD] BUILD: PASS"
Write-Host "[XDK-BUILD] Clean log      : $CleanLog"
Write-Host "[XDK-BUILD] Build log      : $BuildLog"

if (@($xexCandidates).Count -gt 0) {
    $builtXex = $xexCandidates[0]
    Write-Host "[XDK-BUILD] Fresh XEX      : $($builtXex.FullName)"
    Write-Host "[XDK-BUILD] XEX timestamp  : $($builtXex.LastWriteTime)"
    Write-Host "[XDK-BUILD] XEX size       : $($builtXex.Length) bytes"
}
else {
    Write-Warning "VS17 reported build success, but no newly-written .xex was found under '$SolutionRoot'."
}

Write-Host "[XDK-BUILD] FULL PIPELINE: PASS"
