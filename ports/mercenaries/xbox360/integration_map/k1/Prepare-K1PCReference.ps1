[CmdletBinding()]
param(
    [string]$Destination,
    [switch]$RefreshPinned
)
# Read-only provenance source. Clone the PUBLIC PC recomp project once;
# pin a reviewed commit. Never copy PC host renderer or binaries into Xbox.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
if(-not $Destination){
    $Destination = Join-Path $root ".deps\mercenaries-pc-reference"
}
$dest = [IO.Path]::GetFullPath($Destination)
$expectedUrl = "https://github.com/KraftMacAndChee/Mercenaries-Recompiled.git"
$expectedCommit = "f513ae4e041401b7b032410016940971488d523b"
[void](Get-Command git -ErrorAction Stop)
if(-not(Test-Path -LiteralPath $dest -PathType Container)){
    New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
    Write-Host "[K1-PCREF] Cloning reviewed public PC reference source"
    & git clone --quiet --single-branch --branch master $expectedUrl $dest
    if($LASTEXITCODE -ne 0){throw "[K1-PCREF] Git clone failed"}
}
if(-not(Test-Path -LiteralPath (Join-Path $dest ".git"))){
    throw "[K1-PCREF] Existing destination is not a Git checkout: $dest"
}
$origin = (& git -C $dest remote get-url origin)
if($LASTEXITCODE -ne 0){throw "[K1-PCREF] Git origin unavailable"}
$origin = "$origin".Trim().TrimEnd("/")
if($origin -ne $expectedUrl -and
    $origin -ne "https://github.com/KraftMacAndChee/Mercenaries-Recompiled" -and
    $origin -ne "git@github.com:KraftMacAndChee/Mercenaries-Recompiled.git"){
    throw "[K1-PCREF] Unexpected PC reference origin: $origin"
}
$head = "$(& git -C $dest rev-parse HEAD)".Trim().ToLowerInvariant()
if($LASTEXITCODE -ne 0){throw "[K1-PCREF] Git HEAD unavailable"}
if($head -ne $expectedCommit){
    if(-not $RefreshPinned){
        throw "[K1-PCREF] Different source commit $head; use -RefreshPinned to select reviewed snapshot"
    }
    $dirty = @(& git -C $dest status --porcelain)
    if($LASTEXITCODE -ne 0 -or @($dirty | Where-Object {$_}).Count -ne 0){
        throw "[K1-PCREF] Refusing checkout because existing PC reference is dirty"
    }
    & git -C $dest fetch --quiet origin master
    if($LASTEXITCODE -ne 0){throw "[K1-PCREF] Could not fetch source reference"}
    & git -C $dest checkout --quiet --detach $expectedCommit
    if($LASTEXITCODE -ne 0){throw "[K1-PCREF] Could not select pinned PC source commit"}
    $head = "$(& git -C $dest rev-parse HEAD)".Trim().ToLowerInvariant()
    if($head -ne $expectedCommit){throw "[K1-PCREF] Exact PC source commit still absent"}
}
$patch = Join-Path $dest "ports\mercenaries\scripts\Patch-Generated.py"
$inventory = Join-Path $dest "ports\mercenaries\data\generated-patch-inventory.json"
foreach($file in @($patch,$inventory)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1-PCREF] Pinned source file missing: $file"
    }
}
$dirtyVerified = @(& git -C $dest status --porcelain -- "ports/mercenaries/scripts/Patch-Generated.py" "ports/mercenaries/data/generated-patch-inventory.json")
if($LASTEXITCODE -ne 0 -or @($dirtyVerified | Where-Object {$_}).Count -ne 0){
    throw "[K1-PCREF] Reviewed PC patch templates/inventory have local changes"
}
Write-Host "[K1-PCREF] Pinned public PC source PASS commit=$head"
Write-Host "[K1-PCREF] Reference: $dest"
Write-Host "[K1-PCREF] No PC renderer copied to Xbox; no XDK or XEX changed"
