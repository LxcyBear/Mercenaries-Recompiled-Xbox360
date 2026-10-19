[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\..\..\.."))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$stage3Root = Join-Path $repoRoot "build\phase3n_final_abi_scale"
$generatedRoot = Join-Path $stage3Root "runtime\gen"
$functionsPath = Join-Path $stage3Root "analysis\disasm\functions.json"
$entryReport = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-startup-closure.json"
$threadReport = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-thread-routine.json"
$baseEmitter = Join-Path $phaseRoot "emit_phase4c_startup_slice.py"
$emitter = Join-Path $phaseRoot "emit_phase4c_vmreserve_aa.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\vmreserve_aa_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-AA input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-AA] RESERVED GUEST VM PAGE-STATE CONTINUATION PACKAGE"
Write-Host "[Phase4C-AA] Phase 4C-Z hardware PASS captured Base=NULL Size=1MiB Type=MEM_RESERVE Protect=PAGE_READWRITE with fault=0."
Write-Host "[Phase4C-AA] Modeling reserved/uncommitted and committed guest pages explicitly."
Write-Host "[Phase4C-AA] Page-backed VA allocation grows downward from the top of 64 MiB RAM, matching the production runtime strategy."
Write-Host "[Phase4C-AA] Later MEM_COMMIT calls preserve the reserved VA, zero newly committed pages, and record protection metadata."
Write-Host "[Phase4C-AA] All previously proven startup invariants, direct roots, helper continuations, and kernel continuations remain active."
Write-Host "[Phase4C-AA] Main/env build cookie is rotated to the AA pair."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-aa-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

# PowerShell 5 treats native stderr as an ErrorRecord when ErrorActionPreference
# is Stop. Let Python complete so we can inspect its exit code + emitted
# manifest, then restore strict wrapper behavior.
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir 2>&1 | Tee-Object -FilePath $emitLog
    $emitExit = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

if ($emitExit -ne 0) {
    $failedManifest = Join-Path $outDir "phase4c-aa-manifest.json"
    if (Test-Path -LiteralPath $failedManifest) {
        try {
            $failedJson = Get-Content -LiteralPath $failedManifest -Raw | ConvertFrom-Json
            if ($failedJson.unknown_direct_helpers) {
                Write-Host ""
                Write-Host "[Phase4C-AA] Remaining unresolved helper dependencies:"
                $failedJson.unknown_direct_helpers.PSObject.Properties | ForEach-Object {
                    Write-Host ("[Phase4C-AA]   {0}: {1}" -f $_.Name, ($_.Value -join ", "))
                }
                Write-Host ""
            }
        } catch {
            Write-Host "[Phase4C-AA] Could not decode failure manifest: $($_.Exception.Message)"
        }
    }
    throw "Phase 4C-AA reserved-VM package emission failed (exit $emitExit). Full emitter output: $emitLog"
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$manifest = Join-Path $outDir "phase4c-aa-manifest.json"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P4C-VMRESERVE-AA-20261019-A",
    "PASS: ordinal 149 KeSetTimer continuation armed",
    "PASS: bounded direct closure rooted at 0022D980 is packed for translated execution",
    "PASS: hardware-observed direct root 00238C00 is packed for translated execution",
    "PASS: maintained recomp_crt_memmove cdecl support armed",
    "PASS: ordinal 184 NtAllocateVirtualMemory reserved/commit page-state continuation armed",
    "NtAllocateVirtualMemory LIVE FRAME",
    "PASS: ordinal 184 NtAllocateVirtualMemory matched reserved/commit guest-VM semantics",
    "CRT memmove LIVE FRAME",
    "PASS: recomp_crt_memmove matched maintained cdecl semantics",
    "PASS: Phase 4C-AA main/env build cookie matches",
    "PHASE 4C-AA VMRESERVE RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-AA main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-AA RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-AA EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-AA EXECUTION ENVIRONMENT RESULT: PASS",
    "phase4c_env_build_cookie",
    "50434141",
    "PHASE 4C-AA RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-AA phase4c_env.cpp is missing marker: $requiredText"
    }
}

if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Generated Phase 4C-AA manifest is missing: $manifest"
}
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestJson.promoted_direct_frontier_target_7 -ne "0x00238C00") {
    throw "Phase 4C-AA manifest 38C00 root mismatch"
}
if ($manifestJson.continued_kernel_call_184.target -ne "0x800000B8" -or
    [int]$manifestJson.continued_kernel_call_184.arg_bytes -ne 20 -or
    [int]$manifestJson.continued_kernel_call_184.frame_bytes -ne 24) {
    throw "Phase 4C-AA manifest ordinal-184 ABI mismatch"
}
if ($manifestJson.continued_kernel_call_184.page_allocator -notlike "*top of 64 MiB guest RAM downward*") {
    throw "Phase 4C-AA manifest page-backed allocator policy mismatch"
}
if ([int]$manifestJson.promoted_closure_depth -ne 0) {
    throw "Phase 4C-AA manifest safe-root depth mismatch"
}
if ($manifestJson.continued_support_helper_memmove.name -ne "recomp_crt_memmove") {
    throw "Phase 4C-AA manifest CRT memmove helper mismatch"
}
if ([int]$manifestJson.continued_support_helper_memmove.arg_bytes -ne 12 -or
    [int]$manifestJson.continued_support_helper_memmove.callee_cleanup_bytes -ne 4) {
    throw "Phase 4C-AA manifest CRT memmove ABI mismatch"
}
if ($manifestJson.promoted_closure_members.Count -ne 1 -or $manifestJson.promoted_closure_members[0] -ne "0x00238C00") {
    throw "Phase 4C-AA safe-root member set must be exactly 0x00238C00"
}

Write-Host ""
Write-Host "[Phase4C-AA] READY"
Write-Host "[Phase4C-AA] Retained 38C00 safe-root members: $($manifestJson.promoted_closure_members.Count)"
Write-Host "[Phase4C-AA]   $($manifestJson.promoted_closure_members -join ', ')"
Write-Host "[Phase4C-AA] Continued kernel target: 0x800000B8 ordinal 184 NtAllocateVirtualMemory"
Write-Host "[Phase4C-AA] VM model: explicit reserved/uncommitted -> committed page transitions"
Write-Host "[Phase4C-AA] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase4C-AA]   $main"
Write-Host "[Phase4C-AA]   $env"
Write-Host "[Phase4C-AA] The AA cookie must be 0x50434141 (PCAA); stale Z/Y environment objects must fail closed."
Write-Host "[Phase4C-AA] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-AA] Expected build tag: P4C-VMRESERVE-AA-20261019-A"
