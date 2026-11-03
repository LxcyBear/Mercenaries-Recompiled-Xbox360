[CmdletBinding()]
param(
    [switch]$R5Only,
    [switch]$RefreshMap,
    [switch]$AnalyzeOnly,
    [switch]$SourceOnly,
    [string]$PcLog = "",
    [string]$XboxLog = "",
    [string]$RetailXbe = "$env:USERPROFILE\OneDrive\Desktop\My Xbox\default.xbe",
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
# ONE controlled local run. Stage exact r5, use previously verified 404
# function PC-retail map, conditionally stage 1..24 source-clean r6 members,
# do ONE incremental Xbox 360 XDK build. If r6 safety gates reject the
# packet, fall back to the original r5 single-function source build.
#
# Xbox live hardware execution/capture cannot be performed by this script
# without an external Xbox debugger. Optional xbWatson log analysis is
# real evidence only, not a synthetic hardware run.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$tag = "[K1-ONE-RUN]"
$r5stage = Join-Path $PSScriptRoot "Advance-K1PostTwoRootDirect.ps1"
$maprunner = Join-Path $PSScriptRoot "Run-K1PCCrossPortAudit.ps1"
$packetplanner = Join-Path $PSScriptRoot "Plan-K1BulkGraphicsPackets.ps1"
$r6stage = Join-Path $PSScriptRoot "Stage-K1BulkOriginalPackets.ps1"
$trace = Join-Path $PSScriptRoot "Audit-K1GraphicsMilestoneTrace.py"
$builder = Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envSource = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$shards = Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3\translated_shards"
$r5dir = Join-Path $root "build\phase6_integration_map\k1_direct_2228c0_r5"
$r5main = Join-Path $r5dir "main.cpp"
$r5manifest = Join-Path $r5dir "k1-direct-2228c0-original-manifest.json"
$r6dir = Join-Path $root "build\phase6_integration_map\k1_bulk_support_clean_r6"
$r6main = Join-Path $r6dir "main.cpp"
$r6manifest = Join-Path $r6dir "k1-bulk-source-only-r6-manifest.json"
$mapdir = Join-Path $root "build\phase6_integration_map\k1_pc_crossport_audit"
$mapreport = Join-Path $mapdir "pc-to-xbox360-retail-coverage.json"
$packetreport = Join-Path $mapdir "k1-original-404-bounded-source-clean-packets.json"
$runRoot = Join-Path $root "build\phase6_integration_map\k1_one_run_r5_map_graphics"
$traceJson = Join-Path $runRoot "hardware-vs-pc-milestones.json"
$oneRunReport = Join-Path $runRoot "one-run-build-report.json"

function Invoke-SourceScript([string]$Path, [object[]]$ExtraArgs) {
    if(-not(Test-Path -LiteralPath $Path -PathType Leaf)){
        throw "$tag Missing maintained source stage $Path"
    }
    Write-Host "$tag Starting $(Split-Path -Leaf $Path)"
    # Child process needed: older stage scripts end with 'exit 0', which
    # must never terminate this combined runner before its map/build.
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Path @ExtraArgs
    if($LASTEXITCODE -ne 0){
        throw "$tag Original source stage failed $Path (code=$LASTEXITCODE)"
    }
}

function Invoke-Trace([string]$Python) {
    if(-not $PcLog -and -not $XboxLog){
        Write-Host "$tag No PC/Xbox log supplied; real hardware milestones await xbWatson test."
        return
    }
    $argsList = @("-u", $trace, "--output", $traceJson)
    if($PcLog){
        if(-not(Test-Path -LiteralPath $PcLog -PathType Leaf)){
            throw "$tag Requested PC trace file missing: $PcLog"
        }
        $argsList += @("--pc-log", $PcLog)
    }
    if($XboxLog){
        if(-not(Test-Path -LiteralPath $XboxLog -PathType Leaf)){
            throw "$tag Requested Xbox xbWatson hardware log missing: $XboxLog"
        }
        $argsList += @("--xbox-log", $XboxLog)
    }
    & $Python @argsList
    if($LASTEXITCODE -ne 0){
        throw "$tag Actual PC/Xbox log parsing failed"
    }
}

$py = (Get-Command python -ErrorAction Stop).Source
foreach($file in @($r5stage,$packetplanner,$r6stage,$trace)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "$tag Missing original source/build/trace dependency: $file"
    }
}
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
& $py -m py_compile $trace
if($LASTEXITCODE -ne 0){throw "$tag Trace analyzer syntax failure"}
& $py -u $trace --self-test
if($LASTEXITCODE -ne 0){throw "$tag Trace analyzer honest hardware-proof selftest failure"}
if($AnalyzeOnly){
    Invoke-Trace $py
    Write-Host "$tag ANALYZE ONLY PASS: no XDK, no source change, no Xbox auto-run."
    return
}

Write-Host "$tag ============================================================"
Write-Host "$tag ONE RUN: r5 exact retail -> 404 map -> optional r6 packet -> ONE XDK"
Write-Host "$tag PC data is reference, not a substitute for original retail Xbox behavior"
Write-Host "$tag No automatic Xbox deployment; 64 TrueTUs and hard fences retained"

# 1. Source-stage the exact original 002228C0 with verified retail branch.
Invoke-SourceScript $r5stage @("-RetailXbe", $RetailXbe)
foreach($file in @($r5main,$r5manifest)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "$tag r5 retail-restored source/manifest missing after successful source stage: $file"
    }
}
$r5doc = Get-Content -LiteralPath $r5manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$r5sha = (Get-FileHash -LiteralPath $r5main -Algorithm SHA256).Hash.ToLowerInvariant()
if($r5doc.new_main_sha256 -ne $r5sha -or
   $r5doc.original_function_address -ne "0x002228C0" -or
   $r5doc.original_true_tus_unchanged -ne $true -or
   [int]$r5doc.true_tu_count -ne 64 -or
   $r5doc.pc_developer_patch_reverted_to_original_retail.status -ne "PINNED_PC_DEVELOPER_ONLY_PATCH_RESTORED_TO_RETAIL" -or
   $r5doc.pc_developer_patch_reverted_to_original_retail.arbitrary_helper_stub_used -ne $false){
    throw "$tag r5 exact-original retail source / previous hardware preservation contract failed"
}
Write-Host "$tag R5 SOURCE PASS sha=$r5sha original=002228C0, 64 TrueTUs unchanged"

# 2. Reuse/prove r4 full map, then plan up to 24 graph-reachable members.
$selection = "r5"
$selectedMain = $r5main
$selectedManifest = $r5manifest
$packetCount = 0
$fallbackReason = ""
if(-not $R5Only){
    $tryPacket = $true
    if($RefreshMap -or -not(Test-Path -LiteralPath $mapreport -PathType Leaf)){
        Invoke-SourceScript $maprunner @()
    }
    try {
        Invoke-SourceScript $packetplanner @()
        $plan = Get-Content -LiteralPath $packetreport -Raw -Encoding UTF8 | ConvertFrom-Json
        if($plan.status -ne "K1_GLOBAL_MISSING_ORIGINAL_SOURCE_BATCH_PACKETS_NO_XDK" -or
           $plan.safe_to_deploy_unverified_xex -ne $false -or
           $plan.original_64_true_tus_modified -ne $false -or
           [int]$plan.source_clean_eligible_count -lt 1 -or
           [int]$plan.source_clean_eligible_count -gt 24){
            $tryPacket = $false
            $fallbackReason = "Map contains no eligible bounded source packet or violates cap/provenance"
        }
        if($tryPacket){
            Invoke-SourceScript $r6stage @()
            $r6doc = Get-Content -LiteralPath $r6manifest -Raw -Encoding UTF8 | ConvertFrom-Json
            $r6sha = (Get-FileHash -LiteralPath $r6main -Algorithm SHA256).Hash.ToLowerInvariant()
            if($r6doc.status -ne "K1_ORIGINAL_BULK_GRAPHICS_R6_SOURCE_ONLY_XDK_BLOCKED" -or
               $r6doc.r5_main_sha256 -ne $r5sha -or
               $r6doc.r6_derived_main_sha256 -ne $r6sha -or
               $r6doc.r4_hardware_proven_source_fences_preserved -ne $true -or
               $r6doc.original_r5_retail_branch_preserved -ne $true -or
               [int]$r6doc.unmodified_original_TrueTU_count -ne 64 -or
               [int]$r6doc.new_member_count -lt 1 -or
               [int]$r6doc.new_member_count -gt 24 -or
               $r6doc.zero_dummy_host_helpers -ne $true -or
               $r6doc.safe_to_deploy -ne $false -or
               $r6doc.r6_xdk_verified -ne $false){
                throw "$tag r6 derived retail source/64TU/hard-fence verification failed"
            }
            $selection = "combined-r5-plus-r6"
            $selectedMain = $r6main
            $selectedManifest = $r6manifest
            $packetCount = [int]$r6doc.new_member_count
        }
    }
    catch {
        # A source candidate may fail support/ABI checks even after the
        # offline heuristic. Preserve failure reason, never force-pack.
        $fallbackReason = $_.Exception.Message
        $selection = "r5"
        $selectedMain = $r5main
        $selectedManifest = $r5manifest
        $packetCount = 0
        Write-Warning "$tag SAFE FALLBACK to exact r5: $fallbackReason"
    }
}
else {
    $fallbackReason = "R5Only requested"
}
Write-Host "$tag FINAL SOURCE=$selection additional_original_C=$packetCount"
Write-Host "$tag R4 hardware-good six-case source retained; r5/r6 hardware remains UNVERIFIED"

# 3. Compile ONCE, never silently build both r5 and r6. This is a
# hardware-test candidate, NOT a claim that the guest presented pixels.
$xdk = Join-Path $runRoot "xdk"
$xex = Join-Path $xdk ("Merc-K1-OneRun-"+$selection+".xex")
$built = $false
if(-not $SourceOnly){
    foreach($file in @($builder,$envSource)){
        if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
            throw "$tag Missing XDK original builder/phase5 env: $file"
        }
    }
    if(-not(Test-Path -LiteralPath $shards -PathType Container)){
        throw "$tag Missing original 64 TrueTU directory"
    }
    New-Item -ItemType Directory -Path $xdk -Force | Out-Null
    $buildArgs = @{
        GeneratedMain = $selectedMain
        GeneratedEnv = $envSource
        GeneratedShardDir = $shards
        ExpectedBuildTag = "P6DQ-R51-MM173-FRAME-20261029-A"
        ExpectedEnvCookie = "phase6dq_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = "Release"
        Platform = "Xbox 360"
        CleanLog = (Join-Path $xdk "xdk-clean.log")
        BuildLog = (Join-Path $xdk "xdk-build.log")
        PublishedXex = $xex
        ShadowBuildRoot = $FastBuildRoot
        SkipClean = $true
    }
    Write-Host "$tag ONE INCREMENTAL XDK BUILD -> $selection"
    & $builder @buildArgs
    if($LASTEXITCODE -ne 0 -or -not(Test-Path -LiteralPath $xex -PathType Leaf)){
        throw "$tag XDK build/published-XEX validation failed; check $($buildArgs.BuildLog)"
    }
    if((Get-Item -LiteralPath $xex).Length -lt 1000000){
        throw "$tag Published XEX unexpectedly small; refusing to report build pass"
    }
    $built = $true
    Write-Host "$tag XDK BUILD PASS: $xex"
}
else {
    Write-Host "$tag SOURCE ONLY: compiled XEX unchanged"
}
# 4. Optional genuine Xbox test/PC reference trace analysis.
Invoke-Trace $py

$sourceChecksum=(Get-FileHash -LiteralPath $selectedMain -Algorithm SHA256).Hash.ToLowerInvariant()
$report=[ordered]@{
    status="K1_ONE_RUN_R5_RETAIL_AND_404_MAP_ORIGINAL_SOURCE"
    selection=$selection
    r5_source_verified=$true
    r4_hardware_good_graphics_fences_preserved=$true
    original_64_true_tus_unchanged=$true
    original_2228c0_restored_retail=$true
    additional_original_generated_c_staged=$packetCount
    combined_packet_fallback_reason=$fallbackReason
    source_sha256=$sourceChecksum
    selected_source_path=$selectedMain
    selected_source_manifest_path=$selectedManifest
    xdk_build_success=$built
    xex_path= $(if($built){$xex}else{$null})
    xex_sha256=$(if($built){(Get-FileHash -LiteralPath $xex -Algorithm SHA256).Hash.ToLowerInvariant()}else{$null})
    xbox_hardware_run_performed_by_script=$false
    xbox_hardware_new_pixels_verified=$false
    new_hardware_tick_gain_verified=$false
    xbox_hardware_log_supplied=[bool]$XboxLog
    pc_reference_log_supplied=[bool]$PcLog
    trace_report_path=$(if($PcLog -or $XboxLog){$traceJson}else{$null})
    requires_real_xbox_test=$true
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $oneRunReport -Encoding UTF8
Write-Host "$tag ============================================================"
Write-Host "$tag ONE RUN COMPLETE: source=$selection XDK_PASS=$built added_original=$packetCount"
Write-Host "$tag report=$oneRunReport"
if($built){
    Write-Host "$tag TEST-ONLY XEX=$xex"
}
Write-Host "$tag Next: run the above XEX on actual Xbox, capture xbWatson, then"
Write-Host "$tag   .\ports\mercenaries\xbox360\integration_map\k1\Run-K1OneShotBuildAndTrace.ps1 -AnalyzeOnly -XboxLog '<xbWatson.txt>'"
Write-Host "$tag NO GUEST PIXELS/TICK GAIN CLAIMED UNTIL REAL HARDWARE TRACE"
