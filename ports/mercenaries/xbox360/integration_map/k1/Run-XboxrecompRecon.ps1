[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Xbe,
    [string]$Workspace=(Join-Path $env:LOCALAPPDATA "Merc360-Xboxrecomp-Recon"),
    [switch]$NoInstall
)
$ErrorActionPreference="Stop"
$expected="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
$sectionNames="XMV,XACTENG,D3D,XGRPH,DSOUND,WMADEC,XPP"
$py=(Get-Command python -ErrorAction Stop).Source
$git=(Get-Command git -ErrorAction Stop).Source
$sourceXbe=[IO.Path]::GetFullPath($Xbe)
if(-not(Test-Path -LiteralPath $sourceXbe -PathType Leaf)){throw "[XBR] Missing retail XBE: $sourceXbe"}
$sourceSha=(Get-FileHash -LiteralPath $sourceXbe -Algorithm SHA256).Hash.ToUpperInvariant()
if($sourceSha -ne $expected){throw "[XBR] WRONG XBE: required known Mercenaries retail SHA; got $sourceSha"}
$workspacePath=[IO.Path]::GetFullPath($Workspace)
$tool=Join-Path $workspacePath "xboxrecomp"
$private=Join-Path $workspacePath "private"
$split=Join-Path $workspacePath "split"
$upload=Join-Path $workspacePath "upload"
$copiedXbe=Join-Path $private "default.xbe"
$analysis=Join-Path $private "default_analysis.json"
New-Item -ItemType Directory -Path @($workspacePath,$private,$split,$upload) -Force|Out-Null
if(-not(Test-Path -LiteralPath (Join-Path $tool "tools\split\__main__.py") -PathType Leaf)){
    if(Test-Path -LiteralPath $tool){throw "[XBR] Existing tool directory is invalid: $tool"}
    Write-Host "[XBR] Clone xboxrecomp OUTSIDE the Merc360 Git repository"
    & $git clone --depth 1 https://github.com/sp00nznet/xboxrecomp.git $tool
    if($LASTEXITCODE -ne 0){throw "[XBR] Git clone failed"}
}
& $py -c "import capstone" 2>$null
if($LASTEXITCODE -ne 0){
    if($NoInstall){throw "[XBR] Python Capstone unavailable; run: python -m pip install capstone"}
    & $py -m pip install capstone
    if($LASTEXITCODE -ne 0){throw "[XBR] Capstone install failed"}
}
if(-not(Test-Path -LiteralPath $copiedXbe -PathType Leaf) -or (Get-FileHash -LiteralPath $copiedXbe -Algorithm SHA256).Hash -ne $expected){
    Copy-Item -LiteralPath $sourceXbe -Destination $copiedXbe -Force
}
Write-Host "[XBR] Retail SHA PASS, original user-local XBE only; no game bytes for GitHub"
Push-Location $tool
try {
    Write-Host "[XBR] 1/4 XBE sections, entry and imports"
    & $py -m tools.xbe_parser $copiedXbe --json $analysis
    if($LASTEXITCODE -ne 0){throw "[XBR] XBE parser failed"}
    Write-Host "[XBR] 2/4 Whole code-section function discovery (NOT text-only)"
    & $py -m tools.disasm $copiedXbe --extra-sections $sectionNames
    if($LASTEXITCODE -ne 0){throw "[XBR] XBE disassembler failed"}
    Write-Host "[XBR] 3/4 ABI calling conventions, ret cleanup and stack shapes"
    & $py -m tools.abi_analysis $copiedXbe -v
    if($LASTEXITCODE -ne 0){throw "[XBR] ABI analyzer failed"}
    Write-Host "[XBR] 4/4 Per-function byte-exact local assembly + full JSON manifest"
    & $py -m tools.split $copiedXbe --out $split --extra-sections $sectionNames
    if($LASTEXITCODE -ne 0){throw "[XBR] Function splitter failed"}
}
finally{Pop-Location}
$manifest=Join-Path $split "manifest.json"
if(-not(Test-Path -LiteralPath $manifest -PathType Leaf)){throw "[XBR] Missing manifest"}
$data=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8|ConvertFrom-Json
$functions=@($data.function_list)
if($functions.Count -lt 1000){throw "[XBR] Function count too small for retail Mercenaries"}
$byAddress=@{}
foreach($f in $functions){$byAddress[([string]$f.address).ToUpperInvariant()]=$f}
if(-not $byAddress.ContainsKey("0X002D5574")){throw "[XBR] Exact live XPP target 002D5574 missing; inspect section coverage at $manifest"}
$target=$byAddress["0X002D5574"]
if([string]$target.section -ne "XPP"){throw "[XBR] XPP target mapped to unexpected section: $($target.section)"}
$focus=@("0X002D5574","0X002A3A5A","0X0023A3CE","0X00280C39","0X0028E700","0X00290895","0X0029C8BE","0X0027DB5C")
foreach($callee in @($target.calls_to)){
    if($focus.Count -ge 30){break}
    $key=([string]$callee).ToUpperInvariant()
    if($focus -notcontains $key){$focus+= $key}
}
$priority=@()
foreach($key in $focus){if($byAddress.ContainsKey($key)){$priority+= $byAddress[$key]}}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$shardFolder=Join-Path $repo "build\phase6_integration_map\pixel_a3a5a_batch\translated_shards"
$shardFiles=@()
if(Test-Path -LiteralPath $shardFolder -PathType Container){$shardFiles=@(Get-ChildItem -LiteralPath $shardFolder -Filter "translated_*.cpp" -File)}
$compiled=New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
$rx='(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{'
foreach($shard in $shardFiles){
    $source=[IO.File]::ReadAllText($shard.FullName)
    foreach($m in [regex]::Matches($source,$rx)){[void]$compiled.Add("0X"+$m.Groups[1].Value.ToUpperInvariant())}
}
$rows=foreach($f in $functions){
    $key=([string]$f.address).ToUpperInvariant()
    $abiValue=$null
    if($f.PSObject.Properties["calling_convention"]){$abiValue=$f.calling_convention}
    $abiConfidence=$null
    if($f.PSObject.Properties["heuristic_confidence"]){$abiConfidence=$f.heuristic_confidence}
    [PSCustomObject]@{
        Address=$key;Name=$f.name;Section=$f.section;Size=$f.size
        Discovery=$f.detection_method;Confidence=$f.confidence
        CallingConvention=$abiValue;ABIConfidence=$abiConfidence
        PresentInPixelTrueTUs=$compiled.Contains($key)
        DirectCallees=(@($f.calls_to) -join ";")
        DirectCallers=(@($f.called_by) -join ";")
        AssemblyPath=$f.file
    }
}
$csv=Join-Path $upload "merc360_function_census.csv"
$rows|Export-Csv -LiteralPath $csv -Encoding UTF8 -NoTypeInformation
$focusJson=Join-Path $upload "merc360_frontier_focus.json"
@($priority)|ConvertTo-Json -Depth 12|Set-Content -LiteralPath $focusJson -Encoding UTF8
$summary=Join-Path $upload "merc360_frontier_summary.txt"
$lines=New-Object 'System.Collections.Generic.List[string]'
$lines.Add("MERC360 OFFLINE XBOXRECOMP STATIC RECON")
$lines.Add("Retail XBE SHA256: $expected")
$lines.Add("Total functions: $($functions.Count)")
$lines.Add("Functions with ABI guesses: $($data.with_abi)")
$lines.Add("Sections: "+(@($data.sections) -join ", "))
$lines.Add("Known PIXEL TrueTUs: $($shardFiles.Count), compiled function bodies: $($compiled.Count)")
$lines.Add("Known Xbox stop: DIRECT_FRONTIER 0023A3CE -> 002D5574; ticks=27107567; fault=0")
$lines.Add("Guest display_calls=0; never synthesize a display call")
$lines.Add("Static graph is not proven runtime coverage. Validate function/ABI confidence.")
$lines.Add("")
$lines.Add("PRIORITY FUNCTION ABI/GRAPH CAPSULES")
foreach($f in $priority){
    $key=([string]$f.address).ToUpperInvariant()
    $abi="UNKNOWN"
    if($f.PSObject.Properties["calling_convention"]){$abi=[string]$f.calling_convention}
    $line=("{0} section={1} bytes={2} confidence={3} ABI={4} compiledTrueTU={5}") -f $key,$f.section,$f.size,$f.confidence,$abi,$compiled.Contains($key)
    $lines.Add($line)
    $lines.Add("  calls_to: "+(@($f.calls_to) -join ", "))
    $lines.Add("  called_by: "+(@($f.called_by) -join ", "))
}
$lines.Add("")
$lines.Add("Share compact ZIP only. Full XBE and thousands of .s functions stay local.")
$lines|Set-Content -LiteralPath $summary -Encoding UTF8
$manifestCopy=Join-Path $upload "xboxrecomp_manifest.json"
Copy-Item -LiteralPath $manifest -Destination $manifestCopy -Force
$zip=Join-Path $workspacePath "Merc360_xboxrecomp_static_recon.zip"
if(Test-Path -LiteralPath $zip){Remove-Item -LiteralPath $zip -Force}
Compress-Archive -LiteralPath @($summary,$focusJson,$csv,$manifestCopy) -DestinationPath $zip -CompressionLevel Optimal -Force
Write-Host "[XBR] ===================================================="
Write-Host "[XBR] COMPLETE: $($functions.Count) functions, original XPP target $($target.name)"
Write-Host "[XBR] Upload THIS file to ChatGPT: $zip"
Write-Host "[XBR] Original byte-exact assembly remains PRIVATE: $split\asm"
Write-Host "[XBR] No build, no Xbox run, no game binary in ZIP"
