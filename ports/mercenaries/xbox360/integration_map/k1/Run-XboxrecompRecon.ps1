[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Xbe,
    [string]$Workspace=(Join-Path $env:LOCALAPPDATA "Merc360-Xboxrecomp-Recon"),
    [switch]$NoInstall,
    [switch]$ResumeOnly
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
& $py -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('capstone') else 1)"
if($LASTEXITCODE -ne 0){
    if($NoInstall){throw "[XBR] Python Capstone unavailable; run: python -m pip install capstone"}
    & $py -m pip install capstone
    if($LASTEXITCODE -ne 0){throw "[XBR] Capstone install failed"}
}
if(-not(Test-Path -LiteralPath $copiedXbe -PathType Leaf) -or (Get-FileHash -LiteralPath $copiedXbe -Algorithm SHA256).Hash -ne $expected){
    Copy-Item -LiteralPath $sourceXbe -Destination $copiedXbe -Force
}
Write-Host "[XBR] Retail SHA PASS, original user-local XBE only; no game bytes for GitHub"
$disasm=Join-Path $tool "tools\disasm\output"
$cache=Join-Path $disasm ".disasm_cache.json"
$functions=Join-Path $disasm "functions.json"
$summary=Join-Path $disasm "summary.json"
$strings=Join-Path $disasm "strings.json"
$xrefs=Join-Path $disasm "xrefs.json"
$labels=Join-Path $disasm "labels.json"
$identified=Join-Path $tool "tools\func_id\output\identified_functions.json"
$abi=Join-Path $tool "tools\abi_analysis\output\abi_functions.json"
$pack=Join-Path $PSScriptRoot "Pack-XboxrecompRecon.py"
if(-not(Test-Path -LiteralPath $pack -PathType Leaf)){
    throw "[XBR] Updated report packager missing. Run git pull --ff-only."
}
Push-Location $tool
try {
    Write-Host "[XBR] 1/5 XBE parser (retail source verification already passed)"
    & $py -m tools.xbe_parser $copiedXbe --json $analysis
    if($LASTEXITCODE -ne 0){throw "[XBR] XBE parser failed"}

    $disasmComplete=$false
    if((Test-Path -LiteralPath $cache -PathType Leaf) -and
       (Test-Path -LiteralPath $functions -PathType Leaf) -and
       (Test-Path -LiteralPath $summary -PathType Leaf) -and
       (Test-Path -LiteralPath $strings -PathType Leaf) -and
       (Test-Path -LiteralPath $xrefs -PathType Leaf) -and
       (Test-Path -LiteralPath $labels -PathType Leaf)){
        $meta=Get-Content -LiteralPath $cache -Raw -Encoding UTF8 | ConvertFrom-Json
        $details=Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
        if(([string]$meta.xbe_hash).ToUpperInvariant() -eq $expected -and
           $meta.text_only -eq $false -and
           $details.entry_point -eq "0x0022964A" -and
           [int]$details.total_functions -gt 1000){
            $disasmComplete=$true
        }
    }
    if($disasmComplete){
        Write-Host "[XBR] 2/5 REUSE PASS: previous whole-XBE disassembly + function graph cached"
        Write-Host "[XBR] Saved functions: $($details.total_functions), previous disassembly retained"
        Write-Host "[XBR] No repeat of your 663-second disassembly."
    }else{
        if($ResumeOnly){
            throw "[XBR] ResumeOnly requested but Stage 2 cache is missing or not verified. No expensive rescan performed."
        }
        Write-Host "[XBR] 2/5 Original code-section function discovery (can take a while)"
        & $py -m tools.disasm $copiedXbe --analysis-json $analysis --extra-sections $sectionNames -v
        if($LASTEXITCODE -ne 0){throw "[XBR] XBE disassembly failed"}
    }
    foreach($name in @($functions,$strings,$xrefs,$summary)){
        if(-not(Test-Path -LiteralPath $name -PathType Leaf)){
            throw "[XBR] Stage 2 prerequisite was not written: $name"
        }
    }
    Write-Host "[XBR] 3/5 Function classification — missing prerequisite of original runner"
    if(-not(Test-Path -LiteralPath $identified -PathType Leaf)){
        & $py -m tools.func_id $copiedXbe --functions $functions --strings $strings --xrefs $xrefs -v
        if($LASTEXITCODE -ne 0){throw "[XBR] Function identification failed"}
    }else{
        Write-Host "[XBR] REUSE: identified_functions.json already exists"
    }
    if(-not(Test-Path -LiteralPath $identified -PathType Leaf)){
        throw "[XBR] Function identifier did not create identified_functions.json"
    }
    Write-Host "[XBR] 4/5 ABI calling-convention, parameters and stack frame recovery"
    if(-not(Test-Path -LiteralPath $abi -PathType Leaf)){
        & $py -m tools.abi_analysis $copiedXbe --functions $functions --identified $identified --output $abi -v
        if($LASTEXITCODE -ne 0){throw "[XBR] ABI analyzer failed"}
    }else{
        Write-Host "[XBR] REUSE: abi_functions.json already exists"
    }
    if(-not(Test-Path -LiteralPath $abi -PathType Leaf)){
        throw "[XBR] ABI analyzer produced no JSON"
    }
}
finally{Pop-Location}
Write-Host "[XBR] 5/5 Build compact graph/ABI report FROM SAVED JSON (NO split/rescan)"
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$pixelShards=Join-Path $repo "build\phase6_integration_map\pixel_a3a5a_batch\translated_shards"
$zip=Join-Path $workspacePath "Merc360_xboxrecomp_static_recon.zip"
& $py -u $pack --xbe $copiedXbe --functions $functions --summary $summary --abi $abi --pixel-shards $pixelShards --out $upload --zip $zip
if($LASTEXITCODE -ne 0){throw "[XBR] Report packing/retail provenance check failed"}
if(-not(Test-Path -LiteralPath $zip -PathType Leaf)){
    throw "[XBR] Report ZIP absent despite claimed pass: $zip"
}
Write-Host "[XBR] ====================================================="
Write-Host "[XBR]  COMPLETE — SAVED DISASSEMBLY, ABI & STATIC CALL GRAPH"
Write-Host "[XBR] ====================================================="
Write-Host "[XBR] SEND TO CHATGPT: $zip"
Write-Host "[XBR] Original retail XBE stays private. NO XDK build or Xbox run."
