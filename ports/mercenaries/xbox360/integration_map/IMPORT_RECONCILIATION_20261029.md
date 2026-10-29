# Phase 6 original Xbox retail kernel import-gap reconciliation — 2026-10-29

This document records the first **exact-XBE-backed** gap list after the
111-slot retail import table passed local SHA-256 validation.
The original 43-count means "**no explicit ICALL route detected by the
initial source scanner**," not "43 functions broken on an Xbox 360."
Unimplemented host bridges, startup data-thunk relocation, direct guest
calls and alternative tail paths require separate inspection.

Export ordinal/name facts are cross-referenced against
[XboxDev/OpenXDK's xboxkrnl.exe.def](https://github.com/XboxDev/OpenXDK/blob/master/src/xboxkrnl/xboxkrnl.exe.def)
and stored locally as `xboxkrnl_ordinals_reference.json`.
The source is an export reference, NOT proof of ABI or port correctness.

## Named inventory of the **43 original gaps**

| Class | Ordinal — original Xbox export name | Interpretation |
|---|---|---|
| DATA | 16 ExEventObjectType, 71 IoFileObjectType, 323 XboxHDKey | Data/global imports; **not callable kernel API gaps**. Audit real pointer/value usage. Never invent XboxHDKey bytes. |
| EXISTING ALTERNATE ROUTE | 24 ExQueryNonVolatileSetting | Cached runtime handles this through **RECOMP_ITAIL**, which the original 64-route ICALL-only scanner missed. Verify operational semantics separately. |
| TIME / THREAD / SYNC | 97 KeCancelTimer; 100 KeDisconnectInterrupt; 119 KeInsertQueueDpc; **128 KeQuerySystemTime**; 137 KeRemoveQueueDpc; 145 KeSetEvent; 153 KeSynchronizeExecution; 159 KeWaitForSingleObject; 225 NtSetEvent; 232 NtUserIoApcDispatcher; 233 NtWaitForSingleObject; 234 NtWaitForSingleObjectEx; 258 PsTerminateSystemThread | Prioritize real clock + waiting/signal + callback/interrupt interactions as one subsystem; ordinal 128 is the current **hardware-observed** stop, not just a static guess. |
| IO MANAGER / DEVICES | 65 IoCreateDevice; 74 IoInvalidDeviceRequest; 81 IoStartNextPacket; 83 IoStartPacket; 87 IofCompleteRequest; 359 IoMarkIrpMustComplete | IRP/device queues and completions need consistent object lifetime and state, not individual success stubs. |
| STORAGE / FILES | 198 NtFlushBuffersFile; 200 NtFsControlFile; 207 NtQueryDirectoryFile; 210 NtQueryFullAttributesFile | Group tagged-handle I/O, directory enumeration and completion/status semantics. |
| MEMORY / GRAPHICS | 168 MmClaimGpuInstanceMemory; 217 NtQueryVirtualMemory | Validate guest virtual/physical mapping and Xenos-backed graphics memory; no fake GPU pointers. |
| PLATFORM / SHUTDOWN | 46 HalReadWritePCISpace; 358 HalIsResetOrShutdownPending; 360 HalInitiateShutdown | Investigate how the guest queries PCI state and shutdown lifecycle; do not trigger real Xbox shutdown from an unvalidated guest call. |
| DEBUG / EXCEPTIONS | 8 DbgPrint; 95 KeBugCheck; 302 RtlRaiseException; 312 RtlUnwind | Respect error/exception contracts. Fail-stop deliberately on actual fatal paths. |
| RUNTIME / TIME FIELDS | 269 RtlCompareMemoryUlong; 304 RtlTimeFieldsToTime; 305 RtlTimeToTimeFields | Implement semantics and guest data-structure layout with offline differential tests. |
| CRYPTO | 335 XcSHAInit; 336 XcSHAUpdate; 337 XcSHAFinal; 340 XcHMAC | Implement as a complete SHA/HMAC family, test with independent public vectors; never log or substitute secret key material. |

**Count check:** 3 data + 1 known ITAIL route + 13 timing/sync +
6 I/O-manager + 4 storage + 2 memory/graphics + 3 platform +
4 debug/exception + 3 runtime + 4 crypto = **43**.

After excluding 3 DATA entries and recognizing the ordinal-24 ITAIL
route, **up to 39** original entries remain as callable entries without
an identified explicit path. The new scanner may discover other existing
routes. Do not label all 39 as missing implementation or hardware blockers
until checking all relevant dispatchers and indirect host bridges.

## Batch implementation policy

1. **Wave KERNEL-CORE:** one typed compatibility service table covering
   system time, timers, waits, event signaling, DPC and interrupt contracts.
   Resolve observed ordinal 128 with the existing 100ns FILETIME helper,
   correct 8-byte output write, stack cleanup and guest-memory validation.
   Test before Xbox deployment. No blanket-success stub.
2. **Wave I/O:** review and implement related kernel IRP/device/storage
   functions coherently, with tagged-handle and callback regression tests.
3. **Wave MEMORY+XENOS:** map guest virtual memory and GPU ownership,
   distinguish source literals from hardware MMIO and actual D3D calls.
4. **Wave RUNTIME+CRYPTO:** implement guest ABI-sensitive time fields,
   memory comparison and SHA/HMAC as tested families.
5. **Wave ERRORS+PLATFORM:** preserve fatal exception/shutdown semantics
   and avoid host-side irreversible actions during diagnostic execution.

Per service, a "complete" row must record: exact ordinal and import
slot, callable/data classification, actual dispatch entry, guest calling
convention, register preservation, stack delta, pointer dereferences,
side effects, return status, offline tests and Xbox hardware results.

**Phase6DQ remains frozen as a diagnostic baseline.** This is a
reconciliation/audit; no runtime repair is claimed until a batch has been
implemented, built and hardware-tested.
