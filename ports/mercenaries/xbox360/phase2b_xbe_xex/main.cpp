/*
 * Mercenaries Xbox 360 - Phase 2B retail XBE parse/load diagnostic.
 *
 * SELF-CONTAINED XDK TEST. This program DOES NOT execute guest code.
 *
 * Input:
 *     game:\default.xbe
 *
 * The file must come from the user's own supported original-Xbox retail copy.
 * Nothing from the retail game is included in this source repository.
 *
 * Phase 2B proves:
 *   - XBE file I/O on Xbox 360 storage
 *   - explicit little-endian XBE parsing on big-endian Xenon
 *   - supported Mercenaries structural identity
 *   - bounded header + section loading into the 64 MiB guest byte arena
 *   - decoded entry point is mapped, but NEVER called
 */

#include <xtl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MERC_GUEST_RAM_SIZE       (64u * 1024u * 1024u)
#define MERC_XBE_BASE             0x00010000u
#define MERC_TITLE_ID             0x4C410015u
#define MERC_ENTRY_POINT          0x0022964Au
#define MERC_SECTION_COUNT        14u

#define XBE_MIN_HEADER_SIZE       0x178u
#define XBE_SECTION_HEADER_SIZE   56u

#define XBE_ENTRY_RETAIL_XOR      0xA8FC57ABu
#define XBE_THUNK_RETAIL_XOR      0x5B6D40B6u

#define XBE_OFF_BASE              0x0104u
#define XBE_OFF_HEADERS_SIZE      0x0108u
#define XBE_OFF_IMAGE_SIZE        0x010Cu
#define XBE_OFF_CERTIFICATE       0x0118u
#define XBE_OFF_SECTION_COUNT     0x011Cu
#define XBE_OFF_SECTION_HEADERS   0x0120u
#define XBE_OFF_ENTRY             0x0128u
#define XBE_OFF_TLS               0x012Cu
#define XBE_OFF_THUNKS            0x0158u

#define XBE_SEC_FLAGS             0u
#define XBE_SEC_VA                4u
#define XBE_SEC_VSIZE             8u
#define XBE_SEC_RAW_OFFSET        12u
#define XBE_SEC_RAW_SIZE          16u
#define XBE_SEC_NAME_VA           20u

typedef struct MercGuestMemory
{
    BYTE* base;
    DWORD size;
} MercGuestMemory;

typedef struct XbeBuffer
{
    BYTE* data;
    DWORD size;
} XbeBuffer;

static HANDLE s_logFile = INVALID_HANDLE_VALUE;

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P2B] ");
    OutputDebugStringA(line);
    OutputDebugStringA("\r\n");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        WriteFile(s_logFile, line, length, &written, NULL);
        WriteFile(s_logFile, "\r\n", 2, &written, NULL);
        FlushFileBuffers(s_logFile);
    }
}

static void trace_u32(const char* label, DWORD value)
{
    char buffer[160];
    sprintf(buffer, "%s0x%08X (%u)", label, (unsigned int)value,
            (unsigned int)value);
    trace(buffer);
}

static void trace_section(DWORD index,
                          const char* name,
                          DWORD flags,
                          DWORD va,
                          DWORD vsize,
                          DWORD rawOffset,
                          DWORD rawSize)
{
    char buffer[256];
    sprintf(buffer,
            "SECTION %u %-12s flags=%08X VA=%08X VSIZE=%08X RAW=%08X RSIZE=%08X",
            (unsigned int)index,
            name ? name : "?",
            (unsigned int)flags,
            (unsigned int)va,
            (unsigned int)vsize,
            (unsigned int)rawOffset,
            (unsigned int)rawSize);
    trace(buffer);
}

static int check(int condition,
                 const char* passText,
                 const char* failText)
{
    if (condition)
    {
        trace(passText);
        return 1;
    }

    trace(failText);
    return 0;
}

static DWORD read_le32(const void* address)
{
    const BYTE* p = (const BYTE*)address;
    return ((DWORD)p[0]) |
           ((DWORD)p[1] << 8) |
           ((DWORD)p[2] << 16) |
           ((DWORD)p[3] << 24);
}

static int range_ok(DWORD offset, DWORD length, DWORD total)
{
    if (offset > total)
        return 0;
    if (length > total - offset)
        return 0;
    return 1;
}

static int guest_range_ok(const MercGuestMemory* memory,
                          DWORD address,
                          DWORD length)
{
    if (!memory || !memory->base)
        return 0;
    if (address >= memory->size)
        return 0;
    if (length > memory->size - address)
        return 0;
    return 1;
}

static int guest_memory_init(MercGuestMemory* memory)
{
    if (!memory)
        return 0;

    memory->base = (BYTE*)malloc((size_t)MERC_GUEST_RAM_SIZE);
    if (!memory->base)
    {
        memory->size = 0;
        return 0;
    }

    memory->size = MERC_GUEST_RAM_SIZE;
    memset(memory->base, 0, MERC_GUEST_RAM_SIZE);
    return 1;
}

static void guest_memory_shutdown(MercGuestMemory* memory)
{
    if (!memory)
        return;

    if (memory->base)
        free(memory->base);

    memory->base = NULL;
    memory->size = 0;
}

static int load_file(const char* path, XbeBuffer* output)
{
    HANDLE file = INVALID_HANDLE_VALUE;
    DWORD high = 0;
    DWORD low = 0;
    DWORD read = 0;
    BYTE* data = NULL;

    if (!output)
        return 0;

    output->data = NULL;
    output->size = 0;

    file = CreateFileA(path,
                       GENERIC_READ,
                       FILE_SHARE_READ,
                       NULL,
                       OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL,
                       NULL);
    if (file == INVALID_HANDLE_VALUE)
        return 0;

    low = GetFileSize(file, &high);
    if (high != 0 || low == 0 || low == INVALID_FILE_SIZE)
    {
        CloseHandle(file);
        return 0;
    }

    data = (BYTE*)malloc((size_t)low);
    if (!data)
    {
        CloseHandle(file);
        return 0;
    }

    if (!ReadFile(file, data, low, &read, NULL) || read != low)
    {
        free(data);
        CloseHandle(file);
        return 0;
    }

    CloseHandle(file);
    output->data = data;
    output->size = low;
    return 1;
}

static void unload_file(XbeBuffer* file)
{
    if (!file)
        return;

    if (file->data)
        free(file->data);

    file->data = NULL;
    file->size = 0;
}

static void get_section_name(const XbeBuffer* xbe,
                             DWORD base,
                             DWORD nameVa,
                             char output[33])
{
    DWORD offset;
    DWORD i;

    output[0] = '?';
    output[1] = '\0';

    if (!xbe || !xbe->data || nameVa < base)
        return;

    offset = nameVa - base;
    if (offset >= xbe->size)
        return;

    for (i = 0; i < 32u && offset + i < xbe->size; ++i)
    {
        BYTE c = xbe->data[offset + i];
        if (c == 0)
        {
            output[i] = '\0';
            return;
        }

        if (c < 0x20u || c > 0x7Eu)
            c = '?';

        output[i] = (char)c;
    }

    output[i] = '\0';
}

static int load_supported_xbe(const XbeBuffer* xbe,
                              MercGuestMemory* memory)
{
    DWORD base;
    DWORD headersSize;
    DWORD imageSize;
    DWORD certificateVa;
    DWORD certificateOffset;
    DWORD titleId;
    DWORD sectionCount;
    DWORD sectionHeadersVa;
    DWORD sectionHeadersOffset;
    DWORD entryRaw;
    DWORD entryPoint;
    DWORD tlsVa;
    DWORD thunkRaw;
    DWORD thunkVa;
    DWORD i;
    DWORD sectionsLoaded = 0;
    DWORD totalCopied = 0;
    int entryMapped = 0;
    int ok = 1;

    if (!xbe || !xbe->data || !memory || !memory->base)
        return 0;

    if (!check(xbe->size >= XBE_MIN_HEADER_SIZE,
               "PASS: XBE large enough for base header",
               "FAIL: XBE is too small for base header"))
        return 0;

    if (!check(xbe->data[0] == 'X' &&
               xbe->data[1] == 'B' &&
               xbe->data[2] == 'E' &&
               xbe->data[3] == 'H',
               "PASS: XBE magic is XBEH",
               "FAIL: XBE magic is not XBEH"))
        return 0;

    base = read_le32(xbe->data + XBE_OFF_BASE);
    headersSize = read_le32(xbe->data + XBE_OFF_HEADERS_SIZE);
    imageSize = read_le32(xbe->data + XBE_OFF_IMAGE_SIZE);
    certificateVa = read_le32(xbe->data + XBE_OFF_CERTIFICATE);
    sectionCount = read_le32(xbe->data + XBE_OFF_SECTION_COUNT);
    sectionHeadersVa = read_le32(xbe->data + XBE_OFF_SECTION_HEADERS);
    entryRaw = read_le32(xbe->data + XBE_OFF_ENTRY);
    tlsVa = read_le32(xbe->data + XBE_OFF_TLS);
    thunkRaw = read_le32(xbe->data + XBE_OFF_THUNKS);

    entryPoint = entryRaw ^ XBE_ENTRY_RETAIL_XOR;
    thunkVa = thunkRaw ^ XBE_THUNK_RETAIL_XOR;

    trace_u32("XBE base: ", base);
    trace_u32("XBE header bytes: ", headersSize);
    trace_u32("XBE image size: ", imageSize);
    trace_u32("XBE decoded entry: ", entryPoint);
    trace_u32("XBE TLS VA: ", tlsVa);
    trace_u32("XBE decoded kernel thunk VA: ", thunkVa);
    trace_u32("XBE section count: ", sectionCount);

    ok &= check(base == MERC_XBE_BASE,
                "PASS: XBE base matches supported Mercenaries",
                "FAIL: XBE base does not match supported Mercenaries");

    ok &= check(entryPoint == MERC_ENTRY_POINT,
                "PASS: retail entry point matches supported Mercenaries",
                "FAIL: retail entry point does not match supported Mercenaries");

    ok &= check(sectionCount == MERC_SECTION_COUNT,
                "PASS: section count matches supported Mercenaries",
                "FAIL: section count does not match supported Mercenaries");

    ok &= check(headersSize >= XBE_MIN_HEADER_SIZE &&
                headersSize <= xbe->size &&
                guest_range_ok(memory, base, headersSize),
                "PASS: XBE header range is bounded",
                "FAIL: XBE header range is invalid");

    ok &= check(imageSize != 0 &&
                imageSize <= MERC_GUEST_RAM_SIZE - base,
                "PASS: XBE image size fits guest RAM",
                "FAIL: XBE image size exceeds guest RAM");

    if (!ok)
        return 0;

    if (certificateVa < base)
    {
        trace("FAIL: certificate VA is below XBE base");
        return 0;
    }

    certificateOffset = certificateVa - base;
    if (!range_ok(certificateOffset, 12u, xbe->size))
    {
        trace("FAIL: certificate header is outside XBE file");
        return 0;
    }

    titleId = read_le32(xbe->data + certificateOffset + 8u);
    trace_u32("Certificate Title ID: ", titleId);
    if (!check(titleId == MERC_TITLE_ID,
               "PASS: Title ID matches Mercenaries",
               "FAIL: Title ID does not match Mercenaries"))
        return 0;

    if (sectionHeadersVa < base)
    {
        trace("FAIL: section header VA is below XBE base");
        return 0;
    }

    sectionHeadersOffset = sectionHeadersVa - base;

    if (sectionCount == 0u || sectionCount > 64u)
    {
        trace("FAIL: section count is outside sanity bounds");
        return 0;
    }

    if (!range_ok(sectionHeadersOffset,
                  sectionCount * XBE_SECTION_HEADER_SIZE,
                  xbe->size))
    {
        trace("FAIL: section table lies outside XBE file");
        return 0;
    }

    memcpy(memory->base + base, xbe->data, headersSize);

    if (!check(memory->base[base + 0] == 'X' &&
               memory->base[base + 1] == 'B' &&
               memory->base[base + 2] == 'E' &&
               memory->base[base + 3] == 'H',
               "PASS: XBE header copied into guest address 0x00010000",
               "FAIL: guest XBE header copy verification"))
        return 0;

    trace("Beginning bounded XBE section load (NO EXECUTION)");

    for (i = 0; i < sectionCount; ++i)
    {
        const BYTE* sh =
            xbe->data + sectionHeadersOffset + i * XBE_SECTION_HEADER_SIZE;
        DWORD flags = read_le32(sh + XBE_SEC_FLAGS);
        DWORD va = read_le32(sh + XBE_SEC_VA);
        DWORD vsize = read_le32(sh + XBE_SEC_VSIZE);
        DWORD rawOffset = read_le32(sh + XBE_SEC_RAW_OFFSET);
        DWORD rawSize = read_le32(sh + XBE_SEC_RAW_SIZE);
        DWORD nameVa = read_le32(sh + XBE_SEC_NAME_VA);
        DWORD copySize;
        char name[33];

        get_section_name(xbe, base, nameVa, name);
        trace_section(i, name, flags, va, vsize, rawOffset, rawSize);

        if (vsize == 0u)
        {
            trace("FAIL: zero-sized virtual section");
            return 0;
        }

        if (va < base || !guest_range_ok(memory, va, vsize))
        {
            trace("FAIL: section virtual range lies outside 64 MiB guest RAM");
            return 0;
        }

        if (rawSize != 0u && !range_ok(rawOffset, rawSize, xbe->size))
        {
            trace("FAIL: section raw range lies outside XBE file");
            return 0;
        }

        copySize = rawSize < vsize ? rawSize : vsize;

        memset(memory->base + va, 0, vsize);
        if (copySize != 0u)
            memcpy(memory->base + va, xbe->data + rawOffset, copySize);

        if (entryPoint >= va && entryPoint < va + vsize)
            entryMapped = 1;

        sectionsLoaded++;
        totalCopied += copySize;
    }

    trace_u32("Sections loaded: ", sectionsLoaded);
    trace_u32("Initialized section bytes copied: ", totalCopied);

    ok &= check(sectionsLoaded == sectionCount,
                "PASS: every XBE section loaded",
                "FAIL: not every XBE section loaded");

    ok &= check(entryMapped,
                "PASS: decoded entry point lies inside a loaded section",
                "FAIL: decoded entry point is not inside a loaded section");

    ok &= check(guest_range_ok(memory, thunkVa, 4u),
                "PASS: decoded kernel thunk VA lies inside guest RAM",
                "FAIL: decoded kernel thunk VA is outside guest RAM");

    /*
     * This is deliberately a structural identity check only.
     * Exact supported-XBE SHA-256 validation is a later step.
     * DO NOT execute entryPoint here.
     */
    trace("ENTRY POINT EXECUTION: DISABLED BY PHASE 2B DESIGN");

    return ok;
}

VOID __cdecl main()
{
    MercGuestMemory memory;
    XbeBuffer xbe;
    int result = 0;
    DWORD started = 0;
    DWORD nextHeartbeat = 1000u;

    ZeroMemory(&memory, sizeof(memory));
    ZeroMemory(&xbe, sizeof(xbe));

    s_logFile = CreateFileA(
        "game:\\merc360-phase2b-xbe.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 2B RETAIL XBE PARSE/LOAD DIAGNOSTIC START");
    trace("Expected user file: game:\\default.xbe");
    trace("This test NEVER executes the XBE entry point");

    do
    {
        if (!guest_memory_init(&memory))
        {
            trace("FATAL: could not allocate 64 MiB guest arena");
            break;
        }
        trace("PASS: 64 MiB guest arena allocated and cleared");

        if (!load_file("game:\\default.xbe", &xbe))
        {
            trace("FATAL: could not read game:\\default.xbe");
            trace("Copy your own supported original-Xbox retail default.xbe beside this XEX");
            break;
        }

        trace_u32("Retail XBE file bytes: ", xbe.size);

        result = load_supported_xbe(&xbe, &memory);
        if (result)
            trace("PHASE 2B XBE LOAD RESULT: PASS");
        else
            trace("PHASE 2B XBE LOAD RESULT: FAIL");
    }
    while (0);

    unload_file(&xbe);

    if (memory.base)
    {
        guest_memory_shutdown(&memory);
        trace("Guest arena released");
    }

    trace("Press A to exit, or automatic exit after 10 seconds");
    started = GetTickCount();

    for (;;)
    {
        XINPUT_STATE state;
        DWORD elapsed = GetTickCount() - started;

        if (elapsed >= 10000u)
        {
            trace("10-second post-test timeout - exiting");
            break;
        }

        ZeroMemory(&state, sizeof(state));
        if (XInputGetState(0, &state) == ERROR_SUCCESS &&
            (state.Gamepad.wButtons & XINPUT_GAMEPAD_A) != 0)
        {
            trace("Controller A detected - exiting");
            break;
        }

        if (elapsed >= nextHeartbeat)
        {
            trace("POST-TEST HEARTBEAT");
            nextHeartbeat += 1000u;
        }

        Sleep(33);
    }

    trace("PHASE 2B RETAIL XBE PARSE/LOAD DIAGNOSTIC END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}
