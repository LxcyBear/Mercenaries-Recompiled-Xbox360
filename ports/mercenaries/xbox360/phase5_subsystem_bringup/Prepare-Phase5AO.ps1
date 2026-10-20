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
$baseEmitter = Join-Path $phaseRoot "..\phase4c_native_startup\emit_phase4c_startup_slice.py"
$emitter = Join-Path $phaseRoot "emit_phase5ao_cache_device_io.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\cache_device_io_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 5AO input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5AO] CACHE VOLUME DEVICE-CONTROL CONTINUATION"
Write-Host "[Phase5AO] Phase 5AN-B hardware PASS opened Partition5 and advanced to ICALL_SAFE token 0x800000C4 (ordinal 196)."
Write-Host "[Phase5AO] Ordinal 196 is NtDeviceIoControlFile; cache-mount compatibility handles IOCTL 0x00070000 and 0x00074004."
Write-Host "[Phase5AO] Preserving proven Partition0/cache-root behavior and adding a synchronous 44-byte device-control frame handler."
Write-Host "[Phase5AO] Unknown/asynchronous device-control forms remain fenced at STORAGE_IO with full frame logging."
Write-Host "[Phase5AO] Depth-2 closure support: cache-prep + tracked audio fallback/free shims are supplied without replacing retail allocator/free behavior."
Write-Host "[Phase5AO] Unknown kernel/device behavior remains fenced at the next real boundary."
Write-Host "[Phase5AO] Main/env link-time cookie symbol is phase5ao_env_build_cookie / P5AO."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5ao-emitter.log"
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
    $failedManifest = Join-Path $outDir "phase5ao-manifest.json"
    $reportedUnknown = $false
    if (Test-Path -LiteralPath $failedManifest) {
        try {
            $failedJson = Get-Content -LiteralPath $failedManifest -Raw | ConvertFrom-Json
            $unknownProps = @($failedJson.unknown_direct_helpers.PSObject.Properties)
            if ($unknownProps.Count -gt 0) {
                Write-Host ""
                Write-Host "[Phase5AO] Remaining unresolved helper dependencies:"
                foreach ($prop in $unknownProps) {
                    $names = @($prop.Value)
                    Write-Host ("[Phase5AO]   {0}: {1}" -f $prop.Name, ($names -join ", "))

                    $ctxProp = $failedJson.unknown_direct_helper_contexts.PSObject.Properties[$prop.Name]
                    if ($ctxProp) {
                        foreach ($ctx in @($ctxProp.Value)) {
                            Write-Host ("[Phase5AO]     helper={0} source-lines={1}-{2}" -f
                                $ctx.helper, $ctx.first_line, $ctx.last_line)
                            if ($ctx.context) {
                                ($ctx.context -split "`n") | ForEach-Object {
                                    Write-Host ("[Phase5AO]       {0}" -f $_)
                                }
                            }
                        }
                    }
                }
                Write-Host ""
                $reportedUnknown = $true
            }
        } catch {
            Write-Host "[Phase5AO] Could not decode failure manifest: $($_.Exception.Message)"
        }
    }

    if (-not $reportedUnknown -and (Test-Path -LiteralPath $emitLog)) {
        Write-Host ""
        Write-Host "[Phase5AO] Emitter log tail:"
        Get-Content -LiteralPath $emitLog -Tail 80 | ForEach-Object {
            Write-Host $_
        }
        Write-Host ""
    }

    throw "Phase 5AO cache-partition batch package emission failed (exit $emitExit). Full emitter output: $emitLog"
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5ao-manifest.json"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P5AO-CACHE-DEVICE-IO-20261020-A",
    "PASS: ordinal 149 KeSetTimer continuation armed",
    "PASS: bounded direct closure rooted at 0022D980 is packed for translated execution",
    "PASS: hardware-observed direct root 00238C00 is packed for translated execution",
    "PASS: maintained recomp_crt_memmove cdecl support armed",
    "PASS: ordinal 184 NtAllocateVirtualMemory reserved/commit page-state continuation armed",
    "PASS: ordinal 291 RtlInitializeCriticalSection continuation armed",
    "PASS: hardware-observed direct root 0022D431 is packed for translated execution",
    "PASS: hardware-observed direct root 0022CA2B is packed for translated execution",
    "PASS: hardware-observed direct root 0022C8EA is packed for translated execution",
    "PASS: hardware-observed direct root 0022CEEE is packed for translated execution",
    "PASS: Phase 5AO ordinal 202 NtOpenFile native continuation armed",
    "NtOpenFile LIVE FRAME",
    "NtOpenFile OBJECT:",
    "NtOpenFile NATIVE:",
    "PASS: Phase 5AO NtOpenFile native continuation",
    "PASS: Phase 5AO Partition0 root NtOpenFile native continuation",
    "game:\\merc360-partition0",
    "s_phase5ahPartition0OpenSuccessCount > 0u",
    "PASS: Phase 5AO ordinal 301 RtlNtStatusToDosError repeatable mapping",
    "case 0xC0000001u: dosError = 31u;",
    "case 164u: return 0x0087E030u; /* LaunchDataPage pointer export */",
    "GUEST_READ32(0x0087E030u) != 0u",
    "startup data imports 40/41/42(optional)/156/164/322/324 relocated; disk_cache_parts=3",
    "phase5ao_mm_allocate_contiguous",
    "phase5ao_mm_allocate_contiguous_ex",
    "phase5ao_mm_allocate_system",
    "phase5ao_mm_free_contiguous",
    "phase5ao_mm_free_system",
    "phase5ao_mm_get_physical_address",
    "phase5ao_mm_lock_unlock_buffer_pages",
    "phase5ao_mm_query_allocation_size",
    "phase5ao_mm_query_statistics",
    "phase5ao_mm_set_address_protect",
    "phase5ao_mm_lock_unlock_physical_page",
    "phase5ao_mm_map_io_space",
    "phase5ao_mm_persist_contiguous",
    "phase5ao_mm_query_address_protect",
    "phase5ao_mm_unmap_io_space",
    "phase5ao_nt_free_virtual_memory",
    "_phase4c_target == 0x800000B2u",
    "_phase4c_target == 0x800000C7u",
    "PASS: Phase 5AO ordinal 178 MmPersistContiguousMemory production no-op",
    "PHASE5AO_PARTITION0_CONFIG_SIZE 0x00080000u",
    "s_phase5aoPartition0RawReadCount > 0u",
    "phase5ao_init_disk_identity_data",
    "case 40u:  return 0x0087E4A0u; /* HalDiskCachePartitionCount */",
    "case 41u:  return 0x0087E420u; /* HalDiskModelNumber STRING */",
    "case 42u:  return 0x0087E460u; /* HalDiskSerialNumber STRING */",
    "s_phase5aoDiskIdentitySeen40 == 1u",
    "s_phase4cFaultAddress != 0x80000028u",
    "PASS: Phase 5AO disk identity data initialized cache_partitions=3",
    "PASS: Phase 5AO Partition0 config raw write offset=",
    "s_phase5aoPartition0RawWriteCount > 0u",
    "s_phase5ahNtWriteFileSuccessCount > 0u",
    "game:\\merc360-partition3",
    "game:\\merc360-partition4",
    "game:\\merc360-partition5",
    "partition3Root[]",
    "partition4Root[]",
    "partition5Root[]",
    "s_phase5aoCacheRootOpenCount > 0u",
    "PASS: Phase 5AO cache partition native open",
    "static void phase5ao_nt_device_io_control_file(uint32_t savedEsp)",
    "_phase4c_target == 0x800000C4u",
    "NtDeviceIoControlFile LIVE FRAME:",
    "0x00070000u",
    "0x00074004u",
    "s_phase5aoNtDeviceIoControlSuccessCount > 0u",
    "s_phase4cBoundaryTarget != 0x800000C4u",
    "PASS: Phase 5AO ordinal 196 NtDeviceIoControlFile cache continuation armed for IOCTL 00070000/00074004",
    "PASS: Phase 5AO NtDeviceIoControlFile cache continuation",
    "PASS: Phase 5AO exact cache-root mappings armed for Partition3/4/5 (slash optional)",
    "case 0x0022C5C6u: return sub_0022C5C6;",
    "s_phase5aoRoot22C5C6Entered = 1;",
    "s_phase4cBoundaryTarget != 0x0022C5C6u",
    "PASS: Phase 5AO cache-setup root 0022C5C6 plus bounded depth-2 closure is packed",
    "int recomp_prepare_empty_cache_volume(void)",
    "int recomp_test_audio_alloc_failure(uint32_t attributes)",
    "uint32_t recomp_audio_pool_fallback(uint32_t size, uint32_t attributes)",
    "int recomp_audio_pool_free(uint32_t ptr)",
    "PASS: Phase 5AO cache prep helper",
    "PASS: Phase 5AO audio pool fallback",
    "policy=continue-retail-body",
    "s_phase5hNtReadFileSuccessCount > 0u",
    "PASS: Phase 5AO Partition0 config raw read offset=",
    "phase5ao_hal_return_to_firmware_trap",
    "_phase4c_target == 0x80000031u",
    "HAL RETURN TRAP: ordinal=49 routine=",
    "HAL RETURN TRAP: non-returning firmware action intentionally not executed by diagnostic harness",
    "_phase4c_target == 0x800000A5u",
    "_phase4c_target == 0x800000B6u",
    "PASS: Phase 5AO ordinal 218 NtQueryVolumeInformationFile native continuation armed",
    "NtQueryVolumeInformationFile LIVE FRAME",
    "PASS: Phase 5AO NtQueryVolumeInformationFile native continuation",
    "PASS: Phase 5AO ordinal 187 NtClose native continuation armed",
    "NtClose LIVE FRAME",
    "PASS: Phase 5AO NtClose native continuation",
    "PASS: Phase 5AO ordinal 67 IoCreateSymbolicLink native continuation armed",
    "IoCreateSymbolicLink LIVE FRAME",
    "IoCreateSymbolicLink OBJECTS:",
    "PASS: Phase 5AO IoCreateSymbolicLink native continuation",
    "PASS: Phase 5AO ordinal 69 IoDeleteSymbolicLink native continuation armed",
    "IoDeleteSymbolicLink LIVE FRAME",
    "PASS: Phase 5AO IoDeleteSymbolicLink native continuation",
    "PASS: hardware-observed post-mount direct root 0022C1C0 is packed for translated execution",
    "PASS: hardware-observed next retail direct root 002370B8 is packed for translated execution",
    "PASS: hardware-observed next retail direct root 0022BE8C is packed for translated execution",
    "PASS: Phase 5AO ordinal 190 NtCreateFile native continuation armed",
    "NtCreateFile LIVE FRAME",
    "NtCreateFile OBJECT:",
    "NtCreateFile NATIVE:",
    "PASS: Phase 5AO NtCreateFile native continuation",
    "PASS: Phase 5AO ordinal 219 NtReadFile synchronous continuation armed",
    "NtReadFile LIVE FRAME",
    "PASS: Phase 5AO NtReadFile native continuation",
    "PASS: Phase 5AO ordinal 289 RtlInitAnsiString continuation armed",
    "RtlInitAnsiString LIVE FRAME",
    "PASS: Phase 5AO RtlInitAnsiString continuation",
    "PASS: Phase 5AO ordinal 279 RtlEqualString continuation armed",
    "RtlEqualString LIVE FRAME",
    "PASS: Phase 5AO RtlEqualString continuation",
    "PASS: hardware-observed post-storage direct root 0022F026 is packed for translated execution",
    "PASS: hardware-observed root 0022B178 uses maintained manual SetLastError execution",
    "PASS: Phase 5AO maintained SetLastError value=",
    "PASS: Phase 5AO ordinal 211 NtQueryInformationFile class-34 native continuation armed",
    "PASS: hardware-observed post-TitleMeta direct root 00239B78 is packed for translated execution",
    "PASS: hardware-observed next post-TitleMeta direct root 0023DDDD is packed for translated execution",
    "PASS: hardware-observed next post-TitleMeta direct root 0023DD7B is packed for translated execution",
    "PASS: hardware-observed next post-TitleMeta direct root 0023DDA0 is packed for translated execution",
    "PASS: hardware-observed next post-TitleMeta direct root 0023DD56 is packed for translated execution",
    "PASS: hardware-observed next post-TitleMeta direct root 0023F8CB is packed for translated execution",
    "PASS: hardware-observed post-write direct root 0022BDA5 is packed for translated execution",
    "PASS: hardware-observed TitleImage-path direct root 0022F08D is packed for translated execution",
    "PASS: hardware-observed post-XeLoadSection direct root 0022F0CC is packed for translated execution",
    "PASS: hardware-observed post-TitleImage-write direct root 0022F0AE is packed for translated execution",
    "PASS: hardware-observed persistent-state direct root 0022A604 is packed for translated execution",
    "PASS: hardware-observed next direct root 0022A3B9 is packed for translated execution",
    "s_phase5ahRoot22BDA5Entered = 1;",
    "s_phase5ahRoot22F08DEntered = 1;",
    "s_phase5ahRoot22F0CCEntered = 1;",
    "s_phase5ahRoot22F0AEEntered = 1;",
    "s_phase5ahRoot22A604Entered = 1;",
    "s_phase5ahRoot22A3B9Entered = 1;",
    "s_phase5ahRoot22A3B9Entered &&",
    "PASS: Phase 5AO ordinal 236 NtWriteFile 36-byte native continuation armed",
    'PASS: Phase 5AO caller 0022F0CC NtWriteFile saved-ESP repair armed for proven $XTIMAGE/$XSIMAGE image-section frames',
    "phase5ah_path_ends_with_ci",
    "s_phase5ahNtWriteFileXsImageSuccessCount",
    "NtWriteFile SAVEDESP REPAIR PROBE:",
    "PASS: Phase 5AO NtWriteFile caller 0022F0CC saved-ESP repair image=",
    "PASS: Phase 5AO ordinal 327 XeLoadSection native bookkeeping continuation armed",
    "PASS: Phase 5AO ordinal 328 XeUnloadSection native bookkeeping continuation armed",
    "XeUnloadSection LIVE FRAME:",
    "PASS: Phase 5AO XeUnloadSection native bookkeeping continuation",
    "s_phase5ahXeUnloadSectionSuccessCount",
    "XeLoadSection LIVE FRAME:",
    "PASS: Phase 5AO XeLoadSection native continuation",
    "sub_00239B78",
    "sub_0023DDDD",
    "sub_0023DD7B",
    "sub_0023DDA0",
    "sub_0023DD56",
    "sub_0023F8CB",
    "NtWriteFile LIVE FRAME:",
    "PASS: Phase 5AO NtWriteFile native continuation",
    "WriteFile(",
        "NtQueryInformationFile LIVE FRAME:",
    "NtQueryInformationFile NATIVE:",
    "PASS: Phase 5AO NtQueryInformationFile class 34 native continuation",
    "GetFileAttributesExA",
    "s_phase5bHandlePaths",
    "FILE_INFORMATION",
    "STORAGE_IO",
    "game:\\merc360-partition1",
    "RtlInitializeCriticalSection LIVE FRAME",
    "PASS: ordinal 291 RtlInitializeCriticalSection matched maintained serialized-guest semantics",
    "NtAllocateVirtualMemory LIVE FRAME",
    "PASS: ordinal 184 NtAllocateVirtualMemory matched reserved/commit guest-VM semantics",
    "CRT memmove LIVE FRAME",
    "PASS: recomp_crt_memmove matched maintained cdecl semantics",
    "PASS: Phase 5AO main/env build cookie matches",
    "PHASE 5AO CACHE DEVICE IO RESULT"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 5AO main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5AO RETAIL ENVIRONMENT PREP START",
    "PHASE 5AO EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5AO EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5ao_env_build_cookie",
    "5035414F",
    "PHASE 5AO RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 5AO phase5_env.cpp is missing marker: $requiredText"
    }
}

if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Generated Phase 5AO manifest is missing: $manifest"
}
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestJson.phase -ne "5AO" -or $manifestJson.build_tag -ne "P5AO-CACHE-DEVICE-IO-20261020-A") {
    throw "Phase 5AO manifest identity mismatch"
}
$cacheStorage = $manifestJson.phase5ao_cache_storage
if ([int]$cacheStorage.partition0_size -ne 524288 -or
    $cacheStorage.partition0_mode -notlike "*read/write*config device*" -or
    $cacheStorage.observed_write_offset -ne "0x00000800" -or
    [int]$cacheStorage.observed_write_length -ne 512 -or
    $cacheStorage.cache_partition_mappings.'3' -ne "game:\merc360-partition3" -or
    $cacheStorage.cache_partition_mappings.'4' -ne "game:\merc360-partition4" -or
    $cacheStorage.cache_partition_mappings.'5' -ne "game:\merc360-partition5" -or
    $cacheStorage.translated_frontier -ne "0x0022C5C6" -or
    [int]$cacheStorage.closure_depth -ne 2 -or
    [int]$cacheStorage.closure_cap -ne 16) {
    throw "Phase 5AO cache-storage manifest contract mismatch"
}
$deviceIo = $manifestJson.phase5ao_cache_device_io
if ([int]$deviceIo.ordinal -ne 196 -or
    $deviceIo.name -ne "NtDeviceIoControlFile" -or
    $deviceIo.token -ne "0x800000C4" -or
    [int]$deviceIo.frame_bytes -ne 44 -or
    -not [bool]$deviceIo.synchronous_only -or
    [int]$deviceIo.cache_size -ne 1044480 -or
    [int]$deviceIo.bytes_per_sector -ne 512 -or
    $deviceIo.supported_controls.'0x00070000'.name -ne "IOCTL_DISK_GET_DRIVE_GEOMETRY" -or
    [int]$deviceIo.supported_controls.'0x00070000'.output_bytes -ne 8 -or
    $deviceIo.supported_controls.'0x00074004'.name -ne "IOCTL_DISK_GET_PARTITION_INFO" -or
    [int]$deviceIo.supported_controls.'0x00074004'.output_bytes -ne 16 -or
    $deviceIo.unknown_policy -notlike "*STORAGE_IO*full live frame*") {
    throw "Phase 5AO NtDeviceIoControlFile manifest contract mismatch"
}
$supportShims = $manifestJson.phase5ao_support_shims
if ($supportShims.recomp_prepare_empty_cache_volume.signature -ne "int(void)" -or
    $supportShims.recomp_prepare_empty_cache_volume.policy -notlike "*return 0*retail translated body executes*" -or
    $supportShims.recomp_test_audio_alloc_failure.signature -ne "int(uint32_t attributes)" -or
    $supportShims.recomp_test_audio_alloc_failure.policy -notlike "*never force failure*" -or
    $supportShims.recomp_audio_pool_fallback.signature -ne "uint32_t(uint32_t size, uint32_t attributes)" -or
    $supportShims.recomp_audio_pool_fallback.policy -notlike "*retail allocator returned NULL*tracked ownership*" -or
    $supportShims.recomp_audio_pool_free.signature -ne "int(uint32_t ptr)" -or
    $supportShims.recomp_audio_pool_free.policy -notlike "*tracked fallback pointers*retail free path*") {
    throw "Phase 5AO support-shim manifest contract mismatch"
}
if ($manifestJson.promoted_direct_frontier_target_29 -ne "0x0022C5C6") {
    throw "Phase 5AO target-29 address mismatch"
}
$closure29 = @($manifestJson.promoted_closure_29_members)
if ($closure29.Count -lt 1 -or $closure29.Count -gt 16 -or
    ($closure29 -notcontains "0x0022C5C6")) {
    throw "Phase 5AO target-29 closure must contain root and stay within cap 16"
}
if ([int]$manifestJson.promoted_closure_29_depth -ne 2 -or
    [int]$manifestJson.promoted_closure_29_cap -ne 16) {
    throw "Phase 5AO target-29 closure depth/cap mismatch"
}
$diskIdentity = $manifestJson.phase5ao_disk_identity
if ([int]$diskIdentity.cache_partition_count -ne 3 -or
    $diskIdentity.cache_partition_export_va -ne "0x0087E4A0" -or
    $diskIdentity.model_string_va -ne "0x0087E420" -or
    $diskIdentity.model_buffer_va -ne "0x0087E430" -or
    $diskIdentity.serial_string_va -ne "0x0087E460" -or
    $diskIdentity.serial_buffer_va -ne "0x0087E470" -or
    $diskIdentity.model -ne "MERC360 VIRTUAL HDD" -or
    $diskIdentity.serial -ne "MERC3600000000001") {
    throw "Phase 5AO disk-identity manifest contract mismatch"
}
$disk40 = @($manifestJson.data_thunk_fixups | Where-Object { [int]$_.ordinal -eq 40 })
if ($disk40.Count -ne 1 -or
    $disk40[0].name -ne "HalDiskCachePartitionCount" -or
    $disk40[0].guest_data_va -ne "0x0087E4A0" -or
    [int]$disk40[0].initial_value -ne 3) {
    throw "Phase 5AO ordinal-40 data-thunk manifest mismatch"
}
$config = $manifestJson.phase5ao_partition0_config
if ([int]$config.size -ne 524288 -or
    $config.backing -notlike "*zero-initialized*fixed-structure*" -or
    $config.read_scope -notlike "*bounded synchronous reads*" -or
    $config.observed_probe_offset -ne "0x00000800" -or
    [int]$config.observed_probe_length -ne 512 -or
    $config.hal_return_policy -notlike "*trap*LaunchDataPage*") {
    throw "Phase 5AO Partition0 config-device manifest contract mismatch"
}
$mmCluster = $manifestJson.phase5ao_memory_cluster
$expectedMm = @(165,166,167,171,172,173,175,176,177,178,179,180,181,182,183,184,199)
$actualMm = @($mmCluster.enabled_ordinals | ForEach-Object { [int]$_ })
if (($actualMm -join ",") -ne ($expectedMm -join ",")) {
    throw "Phase 5AO enabled Mm ordinal set mismatch"
}
$expectedFencedMm = @(168)
$actualFencedMm = @($mmCluster.fenced_ordinals | ForEach-Object { [int]$_ })
if (($actualFencedMm -join ",") -ne ($expectedFencedMm -join ",")) {
    throw "Phase 5AO fenced Mm ordinal set mismatch"
}
$launchDataFixup = @($manifestJson.data_thunk_fixups | Where-Object { [int]$_.ordinal -eq 164 })
if ($launchDataFixup.Count -ne 1 -or
    $launchDataFixup[0].name -ne "LaunchDataPage" -or
    $launchDataFixup[0].guest_data_va -ne "0x0087E030" -or
    $launchDataFixup[0].initial_value -ne "NULL") {
    throw "Phase 5AO LaunchDataPage data-thunk manifest contract mismatch"
}
if ($manifestJson.promoted_direct_frontier_target_7 -ne "0x00238C00") {
    throw "Phase 5AO manifest 38C00 root mismatch"
}
if ($manifestJson.continued_kernel_call_184.target -ne "0x800000B8" -or
    [int]$manifestJson.continued_kernel_call_184.arg_bytes -ne 20 -or
    [int]$manifestJson.continued_kernel_call_184.frame_bytes -ne 24) {
    throw "Phase 5AO manifest ordinal-184 ABI mismatch"
}
if ($manifestJson.continued_kernel_call_291.target -ne "0x80000123" -or
    [int]$manifestJson.continued_kernel_call_291.arg_bytes -ne 4 -or
    [int]$manifestJson.continued_kernel_call_291.frame_bytes -ne 8) {
    throw "Phase 5AO manifest ordinal-291 ABI mismatch"
}
if ($manifestJson.continued_kernel_call_301.target -ne "0x8000012D" -or
    [int]$manifestJson.continued_kernel_call_301.ordinal -ne 301 -or
    [int]$manifestJson.continued_kernel_call_301.arg_bytes -ne 4 -or
    [int]$manifestJson.continued_kernel_call_301.frame_bytes -ne 8 -or
    $manifestJson.continued_kernel_call_301.dispatch -ne "repeatable; no one-shot state guard") {
    throw "Phase 5AO repeatable ordinal-301 contract mismatch"
}
if ($manifestJson.continued_kernel_call_301.hardware_gate -notlike "*STATUS_UNSUCCESSFUL*31*") {
    throw "Phase 5AO ordinal-301 hardware-gate manifest mismatch"
}
if ($manifestJson.phase5_storage_boundary.target -ne "0x800000CA" -or
    [int]$manifestJson.phase5_storage_boundary.ordinal -ne 202 -or
    [int]$manifestJson.phase5_storage_boundary.arg_bytes -ne 24 -or
    [int]$manifestJson.phase5_storage_boundary.frame_bytes -ne 28 -or
    $manifestJson.phase5_storage_boundary.mode -ne "native-continuation") {
    throw "Phase 5AO NtOpenFile native contract mismatch"
}
if ($manifestJson.phase5_storage_boundary.native_mapping -notlike "*Harddisk0*partition1*merc360-partition1*") {
    throw "Phase 5AO Partition1 native mapping mismatch"
}
if ($manifestJson.phase5_storage_boundary.partition0_mapping -notlike "*Harddisk0*partition0*merc360-partition0*") {
    throw "Phase 5AO Partition0 native mapping mismatch"
}
if ($manifestJson.phase5_storage_boundary.partition0_scope -ne "exact root only; child paths remain fenced until observed") {
    throw "Phase 5AO Partition0 scope mismatch"
}
if ($manifestJson.phase5_storage_boundary.partition0_open_policy -notlike "*FILE_FLAG_BACKUP_SEMANTICS*") {
    throw "Phase 5AO Partition0 directory-open policy mismatch"
}
if ($manifestJson.phase5_volume_query.target -ne "0x800000DA" -or
    [int]$manifestJson.phase5_volume_query.ordinal -ne 218 -or
    [int]$manifestJson.phase5_volume_query.arg_bytes -ne 20 -or
    [int]$manifestJson.phase5_volume_query.frame_bytes -ne 24 -or
    [int]$manifestJson.phase5_volume_query.supported_class -ne 3) {
    throw "Phase 5AO volume-query contract mismatch"
}
if ($manifestJson.phase5_handle_close.target -ne "0x800000BB" -or
    [int]$manifestJson.phase5_handle_close.ordinal -ne 187 -or
    [int]$manifestJson.phase5_handle_close.arg_bytes -ne 4 -or
    [int]$manifestJson.phase5_handle_close.frame_bytes -ne 8) {
    throw "Phase 5AO NtClose contract mismatch"
}
if ($manifestJson.phase5_symbolic_link.target -ne "0x80000043" -or
    [int]$manifestJson.phase5_symbolic_link.ordinal -ne 67 -or
    [int]$manifestJson.phase5_symbolic_link.arg_bytes -ne 8 -or
    [int]$manifestJson.phase5_symbolic_link.frame_bytes -ne 12) {
    throw "Phase 5AO IoCreateSymbolicLink contract mismatch"
}
if ($manifestJson.phase5_symbolic_link_delete.target -ne "0x80000045" -or
    [int]$manifestJson.phase5_symbolic_link_delete.ordinal -ne 69 -or
    [int]$manifestJson.phase5_symbolic_link_delete.arg_bytes -ne 4 -or
    [int]$manifestJson.phase5_symbolic_link_delete.frame_bytes -ne 8) {
    throw "Phase 5AO IoDeleteSymbolicLink contract mismatch"
}
if ($manifestJson.promoted_direct_frontier_target_8 -ne "0x0022D431") {
    throw "Phase 5AO retained D431 root mismatch"
}
if ($manifestJson.promoted_closure_8_members.Count -ne 1 -or
    $manifestJson.promoted_closure_8_members[0] -ne "0x0022D431") {
    throw "Phase 5AO retained D431 member set must be exactly 0x0022D431"
}
if ($manifestJson.promoted_direct_frontier_target_9 -ne "0x0022CA2B") {
    throw "Phase 5AO retained CA2B root mismatch"
}
if ($manifestJson.promoted_closure_9_members.Count -ne 1 -or
    $manifestJson.promoted_closure_9_members[0] -ne "0x0022CA2B") {
    throw "Phase 5AO retained CA2B member set must be exactly 0x0022CA2B"
}
if ($manifestJson.promoted_direct_frontier_target_10 -ne "0x0022C8EA") {
    throw "Phase 5AO retained C8EA root mismatch"
}
if ($manifestJson.promoted_closure_10_members.Count -ne 1 -or
    $manifestJson.promoted_closure_10_members[0] -ne "0x0022C8EA") {
    throw "Phase 5AO retained C8EA member set must be exactly 0x0022C8EA"
}
if ($manifestJson.promoted_direct_frontier_target_11 -ne "0x0022CEEE") {
    throw "Phase 5AO retained CEEE root mismatch"
}
if ($manifestJson.promoted_closure_11_members.Count -ne 1 -or
    $manifestJson.promoted_closure_11_members[0] -ne "0x0022CEEE") {
    throw "Phase 5AO retained CEEE member set must be exactly 0x0022CEEE"
}
if ($manifestJson.promoted_direct_frontier_target_12 -ne "0x0022C1C0") {
    throw "Phase 5AO retained C1C0 root mismatch"
}
if ($manifestJson.promoted_closure_12_members.Count -ne 1 -or
    $manifestJson.promoted_closure_12_members[0] -ne "0x0022C1C0") {
    throw "Phase 5AO retained C1C0 member set must be exactly 0x0022C1C0"
}
if ($manifestJson.promoted_direct_frontier_target_13 -ne "0x002370B8") {
    throw "Phase 5AO retained 370B8 root mismatch"
}
if ($manifestJson.promoted_closure_13_members.Count -ne 1 -or
    $manifestJson.promoted_closure_13_members[0] -ne "0x002370B8") {
    throw "Phase 5AO retained 370B8 member set must be exactly 0x002370B8"
}
if ($manifestJson.promoted_direct_frontier_target_14 -ne "0x0022BE8C") {
    throw "Phase 5AO retained BE8C root mismatch"
}
if ($manifestJson.promoted_closure_14_members.Count -ne 1 -or
    $manifestJson.promoted_closure_14_members[0] -ne "0x0022BE8C") {
    throw "Phase 5AO retained BE8C member set must be exactly 0x0022BE8C"
}
if ($manifestJson.promoted_direct_frontier_target_15 -ne "0x0022F026") {
    throw "Phase 5AO retained F026 root mismatch"
}
if ($manifestJson.promoted_closure_15_members.Count -ne 1 -or
    $manifestJson.promoted_closure_15_members[0] -ne "0x0022F026") {
    throw "Phase 5AO retained F026 member set must be exactly 0x0022F026"
}
if ($manifestJson.promoted_direct_frontier_target_16 -ne "0x0022B178") {
    throw "Phase 5AO manifest B178 root mismatch"
}
if ($manifestJson.promoted_direct_frontier_target_16_mode -ne "manual-maintained") {
    throw "Phase 5AO B178 mode must be manual-maintained"
}
if ($manifestJson.manual_maintained_root_16.address -ne "0x0022B178" -or
    $manifestJson.manual_maintained_root_16.name -ne "sub_0022B178" -or
    $manifestJson.manual_maintained_root_16.semantic_name -ne "SetLastError" -or
    $manifestJson.manual_maintained_root_16.production_source -ne "ports/mercenaries/src/recomp_manual.c") {
    throw "Phase 5AO maintained B178 contract mismatch"
}
if ($manifestJson.promoted_closure_members.Count -ne 1 -or
    $manifestJson.promoted_closure_members[0] -ne "0x0022A3B9") {
    throw "Phase 5AO promoted member set must be exactly 0x0022A3B9"
}
if ($manifestJson.promoted_direct_frontier_target_17 -ne "0x00239B78") {
    throw "Phase 5AO retained target-17 address mismatch"
}
if ($manifestJson.promoted_closure_17_members.Count -ne 1 -or
    $manifestJson.promoted_closure_17_members[0] -ne "0x00239B78") {
    throw "Phase 5AO retained target-17 member set must be exactly 0x00239B78"
}
if ($manifestJson.promoted_direct_frontier_target_18 -ne "0x0023DDDD") {
    throw "Phase 5AO retained target-18 address mismatch"
}
if ($manifestJson.promoted_closure_18_members.Count -ne 1 -or
    $manifestJson.promoted_closure_18_members[0] -ne "0x0023DDDD") {
    throw "Phase 5AO retained target-18 member set must be exactly 0x0023DDDD"
}
if ($manifestJson.promoted_direct_frontier_target_19 -ne "0x0023DD7B") {
    throw "Phase 5AO retained target-19 address mismatch"
}
if ($manifestJson.promoted_closure_19_members.Count -ne 1 -or
    $manifestJson.promoted_closure_19_members[0] -ne "0x0023DD7B") {
    throw "Phase 5AO retained target-19 member set must be exactly 0x0023DD7B"
}
if ($manifestJson.promoted_direct_frontier_target_20 -ne "0x0023DDA0") {
    throw "Phase 5AO retained target-20 address mismatch"
}
if ($manifestJson.promoted_closure_20_members.Count -ne 1 -or
    $manifestJson.promoted_closure_20_members[0] -ne "0x0023DDA0") {
    throw "Phase 5AO retained target-20 member set must be exactly 0x0023DDA0"
}
if ($manifestJson.promoted_direct_frontier_target_21 -ne "0x0023DD56") {
    throw "Phase 5AO retained target-21 address mismatch"
}
if ($manifestJson.promoted_closure_21_members.Count -ne 1 -or
    $manifestJson.promoted_closure_21_members[0] -ne "0x0023DD56") {
    throw "Phase 5AO retained target-21 member set must be exactly 0x0023DD56"
}
if ($manifestJson.promoted_direct_frontier_target_22 -ne "0x0023F8CB") {
    throw "Phase 5AO retained target-22 address mismatch"
}
if ($manifestJson.promoted_closure_22_members.Count -ne 1 -or
    $manifestJson.promoted_closure_22_members[0] -ne "0x0023F8CB") {
    throw "Phase 5AO retained target-22 member set must be exactly 0x0023F8CB"
}
if ($manifestJson.promoted_direct_frontier_target_23 -ne "0x0022BDA5") {
    throw "Phase 5AO retained target-23 address mismatch"
}
if ($manifestJson.promoted_closure_23_members.Count -ne 1 -or
    $manifestJson.promoted_closure_23_members[0] -ne "0x0022BDA5") {
    throw "Phase 5AO retained target-23 member set must be exactly 0x0022BDA5"
}
if ($manifestJson.promoted_direct_frontier_target_24 -ne "0x0022F08D") {
    throw "Phase 5AO retained target-24 address mismatch"
}
if ($manifestJson.promoted_closure_24_members.Count -ne 1 -or
    $manifestJson.promoted_closure_24_members[0] -ne "0x0022F08D") {
    throw "Phase 5AO retained target-24 member set must be exactly 0x0022F08D"
}
if ($manifestJson.promoted_direct_frontier_target_25 -ne "0x0022F0CC") {
    throw "Phase 5AO retained target-25 address mismatch"
}
if ($manifestJson.promoted_closure_25_members.Count -ne 1 -or
    $manifestJson.promoted_closure_25_members[0] -ne "0x0022F0CC") {
    throw "Phase 5AO retained target-25 member set must be exactly 0x0022F0CC"
}
if ($manifestJson.promoted_direct_frontier_target_26 -ne "0x0022F0AE") {
    throw "Phase 5AO retained target-26 address mismatch"
}
if ($manifestJson.promoted_closure_26_members.Count -ne 1 -or
    $manifestJson.promoted_closure_26_members[0] -ne "0x0022F0AE") {
    throw "Phase 5AO retained target-26 member set must be exactly 0x0022F0AE"
}
if ($manifestJson.promoted_direct_frontier_target_27 -ne "0x0022A604") {
    throw "Phase 5AO retained target-27 address mismatch"
}
if ($manifestJson.promoted_closure_27_members.Count -ne 1 -or
    $manifestJson.promoted_closure_27_members[0] -ne "0x0022A604") {
    throw "Phase 5AO retained target-27 member set must be exactly 0x0022A604"
}
if ($manifestJson.promoted_direct_frontier_target_28 -ne "0x0022A3B9") {
    throw "Phase 5AO target-28 address mismatch"
}
if ($manifestJson.promoted_closure_28_members.Count -ne 1 -or
    $manifestJson.promoted_closure_28_members[0] -ne "0x0022A3B9") {
    throw "Phase 5AO target-28 member set must be exactly 0x0022A3B9"
}
if ($manifestJson.phase5_nt_query_information_file.target -ne "0x800000D3" -or
    [int]$manifestJson.phase5_nt_query_information_file.ordinal -ne 211 -or
    [int]$manifestJson.phase5_nt_query_information_file.arg_bytes -ne 20 -or
    [int]$manifestJson.phase5_nt_query_information_file.frame_bytes -ne 24 -or
    $manifestJson.phase5_nt_query_information_file.mode -ne "native-class34-continuation" -or
    [int]$manifestJson.phase5_nt_query_information_file.supported_class -ne 34 -or
    [int]$manifestJson.phase5_nt_query_information_file.required_length -ne 56) {
    throw "Phase 5AO NtQueryInformationFile class-34 native contract mismatch"
}
if ($manifestJson.phase5_nt_create_file.target -ne "0x800000BE" -or
    [int]$manifestJson.phase5_nt_create_file.ordinal -ne 190 -or
    [int]$manifestJson.phase5_nt_create_file.arg_bytes -ne 36 -or
    [int]$manifestJson.phase5_nt_create_file.frame_bytes -ne 40 -or
    $manifestJson.phase5_nt_create_file.mode -ne "native-continuation") {
    throw "Phase 5AO NtCreateFile contract mismatch"
}
if ($manifestJson.phase5_nt_read_file.target -ne "0x800000DB" -or
    [int]$manifestJson.phase5_nt_read_file.ordinal -ne 219 -or
    [int]$manifestJson.phase5_nt_read_file.arg_bytes -ne 32 -or
    [int]$manifestJson.phase5_nt_read_file.frame_bytes -ne 36 -or
    $manifestJson.phase5_nt_read_file.mode -ne "synchronous-native-continuation") {
    throw "Phase 5AO NtReadFile contract mismatch"
}
if ($manifestJson.phase5_nt_write_file.target -ne "0x800000EC" -or
    [int]$manifestJson.phase5_nt_write_file.ordinal -ne 236 -or
    [int]$manifestJson.phase5_nt_write_file.arg_bytes -ne 32 -or
    [int]$manifestJson.phase5_nt_write_file.frame_bytes -ne 36 -or
    $manifestJson.phase5_nt_write_file.mode -ne "synchronous-native-continuation-plus-proven-image-section-savedesp-repair") {
    throw "Phase 5AO NtWriteFile contract mismatch"
}
if ($manifestJson.phase5_xe_load_section.target -ne "0x80000147" -or
    [int]$manifestJson.phase5_xe_load_section.ordinal -ne 327 -or
    [int]$manifestJson.phase5_xe_load_section.arg_bytes -ne 4 -or
    [int]$manifestJson.phase5_xe_load_section.frame_bytes -ne 8 -or
    [int]$manifestJson.phase5_xe_load_section.section_header_bytes -ne 56 -or
    $manifestJson.phase5_xe_load_section.mode -ne "native-bookkeeping-continuation") {
    throw "Phase 5AO XeLoadSection contract mismatch"
}
if ($manifestJson.phase5_xe_unload_section.target -ne "0x80000148" -or
    [int]$manifestJson.phase5_xe_unload_section.ordinal -ne 328 -or
    [int]$manifestJson.phase5_xe_unload_section.arg_bytes -ne 4 -or
    [int]$manifestJson.phase5_xe_unload_section.frame_bytes -ne 8 -or
    [int]$manifestJson.phase5_xe_unload_section.section_header_bytes -ne 56 -or
    $manifestJson.phase5_xe_unload_section.mode -ne "native-bookkeeping-continuation") {
    throw "Phase 5AO XeUnloadSection contract mismatch"
}
if ($manifestJson.phase5_rtl_init_ansi_string.target -ne "0x80000121" -or
    [int]$manifestJson.phase5_rtl_init_ansi_string.ordinal -ne 289 -or
    [int]$manifestJson.phase5_rtl_init_ansi_string.arg_bytes -ne 8 -or
    [int]$manifestJson.phase5_rtl_init_ansi_string.frame_bytes -ne 12 -or
    $manifestJson.phase5_rtl_init_ansi_string.mode -ne "maintained-native-continuation") {
    throw "Phase 5AO RtlInitAnsiString contract mismatch"
}
if ($manifestJson.phase5_rtl_equal_string.target -ne "0x80000117" -or
    [int]$manifestJson.phase5_rtl_equal_string.ordinal -ne 279 -or
    [int]$manifestJson.phase5_rtl_equal_string.arg_bytes -ne 12 -or
    [int]$manifestJson.phase5_rtl_equal_string.frame_bytes -ne 16 -or
    $manifestJson.phase5_rtl_equal_string.mode -ne "maintained-native-continuation") {
    throw "Phase 5AO RtlEqualString contract mismatch"
}
if ($manifestJson.continued_kernel_call_184.page_allocator -notlike "*top of 64 MiB guest RAM downward*") {
    throw "Phase 5AO manifest page-backed allocator policy mismatch"
}
if ([int]$manifestJson.promoted_closure_depth -ne 0) {
    throw "Phase 5AO manifest safe-root depth mismatch"
}
if ($manifestJson.continued_support_helper_memmove.name -ne "recomp_crt_memmove") {
    throw "Phase 5AO manifest CRT memmove helper mismatch"
}
if ([int]$manifestJson.continued_support_helper_memmove.arg_bytes -ne 12 -or
    [int]$manifestJson.continued_support_helper_memmove.callee_cleanup_bytes -ne 4) {
    throw "Phase 5AO manifest CRT memmove ABI mismatch"
}
Write-Host ""
Write-Host "[Phase5AO] READY"
Write-Host "[Phase5AO] Hardware target: retain P5AN-B cache-root success and continue through ordinal 196 cache device-control calls."
Write-Host "[Phase5AO] Cache Partition3/4/5 exact roots (with or without trailing slash) and child paths are mapped proactively; stop only at the next genuinely new boundary."
Write-Host "[Phase5AO] Retained regression: ordinal 301 remains repeatable and STATUS_UNSUCCESSFUL still maps to ERROR_GEN_FAILURE (31)."
Write-Host "[Phase5AO] Hardware PASS gate: prior cache proof + at least one successful NtDeviceIoControlFile compatibility continuation + a genuinely newer boundary."
Write-Host "[Phase5AO] Kernel target 0x800000C4 is explicitly rejected as an acceptable next boundary because ordinal 196 is now handled."
Write-Host "[Phase5AO] Exact Partition0 sandbox and all 77 translated bodies remain retained."
Write-Host "[Phase5AO] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase5AO]   $main"
Write-Host "[Phase5AO]   $env"
Write-Host "[Phase5AO] Link-time guard: main requires phase5ao_env_build_cookie from the matching generated environment source."
Write-Host "[Phase5AO] The 5AO cookie must be 0x5035414F (P5AO)."
Write-Host "[Phase5AO] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase5AO] Expected build tag: P5AO-CACHE-DEVICE-IO-20261020-A"
