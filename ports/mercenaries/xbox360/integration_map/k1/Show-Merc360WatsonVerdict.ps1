[CmdletBinding()]
param(
    [string]$LogPath,
    [switch]$NoAppend
)
# Windows PowerShell 5.1. No Xbox/XDK/build needed.
# Reads a FINISHED xbWatson log and writes a source-grounded verdict board at EOF.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
if([string]::IsNullOrWhiteSpace($LogPath)){
    Add-Type -AssemblyName System.Windows.Forms
    $picker=New-Object System.Windows.Forms.OpenFileDialog
    $picker.Title="Select the FINISHED xbWatson Mercenaries log"
    $picker.Filter="Text logs (*.txt;*.log)|*.txt;*.log|All files (*.*)|*.*"
    $picker.Multiselect=$false
    if($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK){
        Write-Host "[MERC360-VERDICT] Cancelled; no files modified"
        exit 0
    }
    $LogPath=$picker.FileName
}
$LogPath=[IO.Path]::GetFullPath($LogPath)
if(-not (Test-Path -LiteralPath $LogPath -PathType Leaf)){
    throw "[MERC360-VERDICT] Cannot locate log file: $LogPath"
}
$python=(Get-Command python -ErrorAction Stop).Source
$scriptPath=Join-Path $PSScriptRoot "Report-Merc360Milestones.py"
if(-not(Test-Path -LiteralPath $scriptPath -PathType Leaf)){
    throw "[MERC360-VERDICT] Missing companion Python analyzer: $scriptPath"
}
& $python -u $scriptPath --self-test
if($LASTEXITCODE -ne 0){
    throw "[MERC360-VERDICT] Milestone classification self-test failed; no log modifications"
}
Write-Host "[MERC360-VERDICT] Reading completed Watson run (no Xbox access)"
$argsList=@("-u",$scriptPath,"--log",$LogPath)
if($NoAppend){$argsList+="--no-append"}
& $python @argsList
if($LASTEXITCODE -ne 0){
    throw "[MERC360-VERDICT] Verdict command failed, exit=$LASTEXITCODE"
}
Write-Host "[MERC360-VERDICT] Full milestone board is above and beside your log."
