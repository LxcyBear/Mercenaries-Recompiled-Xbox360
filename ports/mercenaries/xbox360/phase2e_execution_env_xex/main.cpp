/*
 * Mercenaries Xbox 360 - Phase 2E retail XBE parse/load diagnostic.
 *
 * SELF-CONTAINED XDK TEST. This program DOES NOT execute guest code.
 *
 * Input:
 *     game:\default.xbe
 *
 * The file must come from the user's own supported original-Xbox retail copy.
 * Nothing from the retail game is included in this source repository.
 *
 * Phase 2E proves:
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
#define MERC_XBE_FILE_SIZE        0x00313000u
#define MERC_XBE_HEADERS_SIZE     0x00000A70u
#define MERC_XBE_IMAGE_SIZE       0x00868AA0u
#define MERC_TLS_VA               0x00302CB4u
#define MERC_KERNEL_THUNK_VA      0x002DBCE0u

/* Supported Mercenaries guest execution-environment layout. */
#define MERC_FAKE_TLS_VA           0x00700000u
#define MERC_FAKE_KTHREAD_VA       0x00760000u
#define MERC_KERNEL_DATA_BASE      0x0087E000u
#define MERC_KERNEL_DATA_SIZE      0x00001000u
#define MERC_STACK_BASE            0x00880000u
#define MERC_STACK_SIZE            0x00040000u
#define MERC_STACK_TOP             0x008BFFF0u
#define MERC_HEAP_BASE             0x008C0000u

#define MERC_RAM_MASK              0x03FFFFFFu
#define MERC_RAM_MIRROR_END        0x74000000u
#define MERC_KSEG_BASE             0x80000000u
#define MERC_KSEG_END              0xC0000000u
#define MERC_SYNTH_FENCE_BASE      0x80000000u
#define MERC_SYNTH_FENCE_END       0x80001000u
#define MERC_SYNTH_KERNEL_BASE     0x80010000u
#define MERC_SYNTH_KERNEL_END      0x80011000u

#define KDATA_HARDWARE_INFO        0x000u
#define KDATA_KRNL_VERSION         0x010u
#define KDATA_TICK_COUNT           0x020u

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


static void trace(const char* line);

typedef struct Sha256Context
{
    DWORD state[8];
    unsigned __int64 bitCount;
    BYTE buffer[64];
    DWORD bufferLength;
} Sha256Context;

static const BYTE kSupportedXbeSha256[32] =
{
    0xAA, 0x08, 0xEA, 0x21, 0xD9, 0x52, 0xAC, 0x35,
    0xF4, 0x9C, 0x02, 0xC7, 0xE2, 0xED, 0x08, 0xAA,
    0x25, 0xAD, 0x75, 0x35, 0xFB, 0xBB, 0xCC, 0xC9,
    0x56, 0x36, 0x77, 0x5F, 0x37, 0xBE, 0x99, 0xD7
};

static const char* kExpectedSectionNames[MERC_SECTION_COUNT] =
{
    ".text", "XMV", "XACTENG", "D3D", "XGRPH", "DSOUND", "WMADEC",
    "XPP", ".rdata", ".data", "DOLBY", "\x24\x24XTIMAGE", "\x24\x24XSIMAGE", ".XTLID"
};

static DWORD sha_rotr(DWORD value, DWORD count)
{
    return (value >> count) | (value << (32u - count));
}

static DWORD sha_choose(DWORD x, DWORD y, DWORD z)
{
    return (x & y) ^ ((~x) & z);
}

static DWORD sha_majority(DWORD x, DWORD y, DWORD z)
{
    return (x & y) ^ (x & z) ^ (y & z);
}

static DWORD sha_big_sigma0(DWORD x)
{
    return sha_rotr(x, 2u) ^ sha_rotr(x, 13u) ^ sha_rotr(x, 22u);
}

static DWORD sha_big_sigma1(DWORD x)
{
    return sha_rotr(x, 6u) ^ sha_rotr(x, 11u) ^ sha_rotr(x, 25u);
}

static DWORD sha_small_sigma0(DWORD x)
{
    return sha_rotr(x, 7u) ^ sha_rotr(x, 18u) ^ (x >> 3u);
}

static DWORD sha_small_sigma1(DWORD x)
{
    return sha_rotr(x, 17u) ^ sha_rotr(x, 19u) ^ (x >> 10u);
}

static DWORD sha_read_be32(const BYTE* p)
{
    return ((DWORD)p[0] << 24) |
           ((DWORD)p[1] << 16) |
           ((DWORD)p[2] << 8) |
           ((DWORD)p[3]);
}

static void sha_write_be32(BYTE* p, DWORD value)
{
    p[0] = (BYTE)(value >> 24);
    p[1] = (BYTE)(value >> 16);
    p[2] = (BYTE)(value >> 8);
    p[3] = (BYTE)value;
}

static void sha256_transform(Sha256Context* ctx, const BYTE block[64])
{
    static const DWORD k[64] =
    {
        0x428A2F98u, 0x71374491u, 0xB5C0FBCFu, 0xE9B5DBA5u,
        0x3956C25Bu, 0x59F111F1u, 0x923F82A4u, 0xAB1C5ED5u,
        0xD807AA98u, 0x12835B01u, 0x243185BEu, 0x550C7DC3u,
        0x72BE5D74u, 0x80DEB1FEu, 0x9BDC06A7u, 0xC19BF174u,
        0xE49B69C1u, 0xEFBE4786u, 0x0FC19DC6u, 0x240CA1CCu,
        0x2DE92C6Fu, 0x4A7484AAu, 0x5CB0A9DCu, 0x76F988DAu,
        0x983E5152u, 0xA831C66Du, 0xB00327C8u, 0xBF597FC7u,
        0xC6E00BF3u, 0xD5A79147u, 0x06CA6351u, 0x14292967u,
        0x27B70A85u, 0x2E1B2138u, 0x4D2C6DFCu, 0x53380D13u,
        0x650A7354u, 0x766A0ABBu, 0x81C2C92Eu, 0x92722C85u,
        0xA2BFE8A1u, 0xA81A664Bu, 0xC24B8B70u, 0xC76C51A3u,
        0xD192E819u, 0xD6990624u, 0xF40E3585u, 0x106AA070u,
        0x19A4C116u, 0x1E376C08u, 0x2748774Cu, 0x34B0BCB5u,
        0x391C0CB3u, 0x4ED8AA4Au, 0x5B9CCA4Fu, 0x682E6FF3u,
        0x748F82EEu, 0x78A5636Fu, 0x84C87814u, 0x8CC70208u,
        0x90BEFFFAu, 0xA4506CEBu, 0xBEF9A3F7u, 0xC67178F2u
    };
    DWORD w[64];
    DWORD a, b, cc, d, e, f, g, h;
    DWORD t1, t2;
    DWORD i;

    for (i = 0; i < 16u; ++i)
        w[i] = sha_read_be32(block + i * 4u);

    for (i = 16u; i < 64u; ++i)
        w[i] = sha_small_sigma1(w[i - 2u]) + w[i - 7u] +
               sha_small_sigma0(w[i - 15u]) + w[i - 16u];

    a = ctx->state[0];
    b = ctx->state[1];
    cc = ctx->state[2];
    d = ctx->state[3];
    e = ctx->state[4];
    f = ctx->state[5];
    g = ctx->state[6];
    h = ctx->state[7];

    for (i = 0; i < 64u; ++i)
    {
        t1 = h + sha_big_sigma1(e) + sha_choose(e, f, g) + k[i] + w[i];
        t2 = sha_big_sigma0(a) + sha_majority(a, b, cc);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = cc;
        cc = b;
        b = a;
        a = t1 + t2;
    }

    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += cc;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

static void sha256_init(Sha256Context* ctx)
{
    ctx->state[0] = 0x6A09E667u;
    ctx->state[1] = 0xBB67AE85u;
    ctx->state[2] = 0x3C6EF372u;
    ctx->state[3] = 0xA54FF53Au;
    ctx->state[4] = 0x510E527Fu;
    ctx->state[5] = 0x9B05688Cu;
    ctx->state[6] = 0x1F83D9ABu;
    ctx->state[7] = 0x5BE0CD19u;
    ctx->bitCount = 0;
    ctx->bufferLength = 0;
}

static void sha256_update(Sha256Context* ctx, const BYTE* data, DWORD length)
{
    DWORD offset = 0;

    ctx->bitCount += ((unsigned __int64)length) * 8ui64;

    while (offset < length)
    {
        DWORD available = 64u - ctx->bufferLength;
        DWORD remaining = length - offset;
        DWORD take = remaining < available ? remaining : available;

        memcpy(ctx->buffer + ctx->bufferLength, data + offset, take);
        ctx->bufferLength += take;
        offset += take;

        if (ctx->bufferLength == 64u)
        {
            sha256_transform(ctx, ctx->buffer);
            ctx->bufferLength = 0;
        }
    }
}

static void sha256_final(Sha256Context* ctx, BYTE digest[32])
{
    unsigned __int64 bits = ctx->bitCount;
    DWORD i;

    ctx->buffer[ctx->bufferLength++] = 0x80u;

    if (ctx->bufferLength > 56u)
    {
        while (ctx->bufferLength < 64u)
            ctx->buffer[ctx->bufferLength++] = 0;
        sha256_transform(ctx, ctx->buffer);
        ctx->bufferLength = 0;
    }

    while (ctx->bufferLength < 56u)
        ctx->buffer[ctx->bufferLength++] = 0;

    for (i = 0; i < 8u; ++i)
        ctx->buffer[56u + i] = (BYTE)(bits >> (56u - i * 8u));

    sha256_transform(ctx, ctx->buffer);

    for (i = 0; i < 8u; ++i)
        sha_write_be32(digest + i * 4u, ctx->state[i]);

    memset(ctx, 0, sizeof(*ctx));
}

static void sha256_bytes(const BYTE* data, DWORD length, BYTE digest[32])
{
    Sha256Context ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, data, length);
    sha256_final(&ctx, digest);
}

static void digest_to_hex(const BYTE digest[32], char output[65])
{
    static const char hex[] = "0123456789ABCDEF";
    DWORD i;

    for (i = 0; i < 32u; ++i)
    {
        output[i * 2u] = hex[(digest[i] >> 4) & 0x0Fu];
        output[i * 2u + 1u] = hex[digest[i] & 0x0Fu];
    }

    output[64] = '\0';
}

static int verify_supported_xbe_hash(const XbeBuffer* xbe)
{
    BYTE digest[32];
    char hex[65];
    char line[128];

    if (!xbe || !xbe->data)
        return 0;

    sha256_bytes(xbe->data, xbe->size, digest);
    digest_to_hex(digest, hex);

    sprintf(line, "Computed SHA-256: %s", hex);
    trace(line);

    if (memcmp(digest, kSupportedXbeSha256, 32u) != 0)
    {
        trace("FAIL: SHA-256 does not match supported retail Mercenaries XBE");
        return 0;
    }

    trace("PASS: SHA-256 exactly matches supported retail Mercenaries XBE");
    return 1;
}

static int range_all_zero(const BYTE* data, DWORD length)
{
    DWORD i;
    for (i = 0; i < length; ++i)
        if (data[i] != 0)
            return 0;
    return 1;
}


static HANDLE s_logFile = INVALID_HANDLE_VALUE;

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P2E] ");
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

    ok &= check(xbe->size == MERC_XBE_FILE_SIZE,
                "PASS: XBE file size matches supported retail build",
                "FAIL: XBE file size does not match supported retail build");

    ok &= check(base == MERC_XBE_BASE,
                "PASS: XBE base matches supported Mercenaries",
                "FAIL: XBE base does not match supported Mercenaries");

    ok &= check(headersSize == MERC_XBE_HEADERS_SIZE,
                "PASS: XBE header size matches supported retail build",
                "FAIL: XBE header size does not match supported retail build");

    ok &= check(imageSize == MERC_XBE_IMAGE_SIZE,
                "PASS: XBE image size matches supported retail build",
                "FAIL: XBE image size does not match supported retail build");

    ok &= check(entryPoint == MERC_ENTRY_POINT,
                "PASS: retail entry point matches supported Mercenaries",
                "FAIL: retail entry point does not match supported Mercenaries");

    ok &= check(sectionCount == MERC_SECTION_COUNT,
                "PASS: section count matches supported Mercenaries",
                "FAIL: section count does not match supported Mercenaries");

    ok &= check(tlsVa == MERC_TLS_VA,
                "PASS: TLS VA matches supported retail build",
                "FAIL: TLS VA does not match supported retail build");

    ok &= check(thunkVa == MERC_KERNEL_THUNK_VA,
                "PASS: kernel thunk VA matches supported retail build",
                "FAIL: kernel thunk VA does not match supported retail build");

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

    if (!check(memcmp(memory->base + base, xbe->data, headersSize) == 0,
               "PASS: entire XBE header exactly copied to guest 0x00010000",
               "FAIL: guest XBE header differs from source"))
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

        if (strcmp(name, kExpectedSectionNames[i]) != 0)
        {
            char mismatch[160];
            sprintf(mismatch,
                    "FAIL: section %u name mismatch: actual='%s' expected='%s'",
                    (unsigned int)i, name, kExpectedSectionNames[i]);
            trace(mismatch);
            return 0;
        }

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

        {
            DWORD previous;
            for (previous = 0; previous < i; ++previous)
            {
                const BYTE* prevSh =
                    xbe->data + sectionHeadersOffset +
                    previous * XBE_SECTION_HEADER_SIZE;
                DWORD prevVa = read_le32(prevSh + XBE_SEC_VA);
                DWORD prevVsize = read_le32(prevSh + XBE_SEC_VSIZE);
                DWORD end = va + vsize;
                DWORD prevEnd = prevVa + prevVsize;

                if (va < prevEnd && prevVa < end)
                {
                    trace("FAIL: virtual XBE sections overlap");
                    return 0;
                }
            }
        }

        copySize = rawSize < vsize ? rawSize : vsize;

        memset(memory->base + va, 0, vsize);
        if (copySize != 0u)
            memcpy(memory->base + va, xbe->data + rawOffset, copySize);

        if (copySize != 0u &&
            memcmp(memory->base + va, xbe->data + rawOffset, copySize) != 0)
        {
            trace("FAIL: loaded initialized section bytes differ from source");
            return 0;
        }

        if (vsize > copySize &&
            !range_all_zero(memory->base + va + copySize, vsize - copySize))
        {
            trace("FAIL: zero-fill tail contains nonzero bytes");
            return 0;
        }

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

    trace("PASS: every loaded section matches source bytes + zero-fill invariant");
    trace("ENTRY POINT EXECUTION: DISABLED BY PHASE 2E DESIGN");

    return ok;
}


static int guest_ram_offset(DWORD address, DWORD width, DWORD* offsetOut)
{
    DWORD offset;

    if (!offsetOut || width == 0u)
        return 0;

    if (address < MERC_RAM_MIRROR_END)
    {
        offset = address & MERC_RAM_MASK;
    }
    else if (address >= MERC_KSEG_BASE && address < MERC_KSEG_END)
    {
        if ((address >= MERC_SYNTH_FENCE_BASE &&
             address < MERC_SYNTH_FENCE_END) ||
            (address >= MERC_SYNTH_KERNEL_BASE &&
             address < MERC_SYNTH_KERNEL_END))
            return 0;

        offset = address & MERC_RAM_MASK;
    }
    else
    {
        return 0;
    }

    if (offset >= MERC_GUEST_RAM_SIZE ||
        width > MERC_GUEST_RAM_SIZE - offset)
        return 0;

    *offsetOut = offset;
    return 1;
}

static BYTE* guest_ram_ptr(MercGuestMemory* memory,
                           DWORD address,
                           DWORD width)
{
    DWORD offset;

    if (!memory || !memory->base ||
        !guest_ram_offset(address, width, &offset))
        return NULL;

    return memory->base + offset;
}

static const BYTE* guest_ram_cptr(const MercGuestMemory* memory,
                                  DWORD address,
                                  DWORD width)
{
    DWORD offset;

    if (!memory || !memory->base ||
        !guest_ram_offset(address, width, &offset))
        return NULL;

    return memory->base + offset;
}

static WORD env_read_le16(const BYTE* p)
{
    return (WORD)((WORD)p[0] | ((WORD)p[1] << 8));
}

static void env_write_le16(BYTE* p, WORD value)
{
    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
}

static void env_write_le32(BYTE* p, DWORD value)
{
    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
    p[2] = (BYTE)(value >> 16);
    p[3] = (BYTE)(value >> 24);
}

static int guest_read8(const MercGuestMemory* memory,
                       DWORD address,
                       BYTE* value)
{
    const BYTE* p = guest_ram_cptr(memory, address, 1u);
    if (!p || !value)
        return 0;
    *value = *p;
    return 1;
}

static int guest_read16(const MercGuestMemory* memory,
                        DWORD address,
                        WORD* value)
{
    const BYTE* p = guest_ram_cptr(memory, address, 2u);
    if (!p || !value)
        return 0;
    *value = env_read_le16(p);
    return 1;
}

static int guest_read32(const MercGuestMemory* memory,
                        DWORD address,
                        DWORD* value)
{
    const BYTE* p = guest_ram_cptr(memory, address, 4u);
    if (!p || !value)
        return 0;
    *value = read_le32(p);
    return 1;
}

static int guest_write8(MercGuestMemory* memory,
                        DWORD address,
                        BYTE value)
{
    BYTE* p = guest_ram_ptr(memory, address, 1u);
    if (!p)
        return 0;
    *p = value;
    return 1;
}

static int guest_write16(MercGuestMemory* memory,
                         DWORD address,
                         WORD value)
{
    BYTE* p = guest_ram_ptr(memory, address, 2u);
    if (!p)
        return 0;
    env_write_le16(p, value);
    return 1;
}

static int guest_write32(MercGuestMemory* memory,
                         DWORD address,
                         DWORD value)
{
    BYTE* p = guest_ram_ptr(memory, address, 4u);
    if (!p)
        return 0;
    env_write_le32(p, value);
    return 1;
}

static int get_loaded_image_end(const MercGuestMemory* memory,
                                DWORD* endOut)
{
    DWORD sectionCount = 0;
    DWORD sectionHeadersVa = 0;
    DWORD maxEnd = 0;
    DWORD i;

    if (!endOut ||
        !guest_read32(memory, MERC_XBE_BASE + XBE_OFF_SECTION_COUNT,
                      &sectionCount) ||
        !guest_read32(memory, MERC_XBE_BASE + XBE_OFF_SECTION_HEADERS,
                      &sectionHeadersVa))
        return 0;

    if (sectionCount != MERC_SECTION_COUNT)
        return 0;

    for (i = 0; i < sectionCount; ++i)
    {
        const BYTE* sh = guest_ram_cptr(
            memory,
            sectionHeadersVa + i * XBE_SECTION_HEADER_SIZE,
            XBE_SECTION_HEADER_SIZE);
        DWORD va;
        DWORD vsize;
        DWORD end;

        if (!sh)
            return 0;

        va = read_le32(sh + XBE_SEC_VA);
        vsize = read_le32(sh + XBE_SEC_VSIZE);

        if (va >= MERC_GUEST_RAM_SIZE ||
            vsize > MERC_GUEST_RAM_SIZE - va)
            return 0;

        end = va + vsize;
        if (end > maxEnd)
            maxEnd = end;
    }

    *endOut = maxEnd;
    return 1;
}

static int initialize_execution_environment(MercGuestMemory* memory)
{
    DWORD tlsDirectory = 0;
    DWORD tlsRawStart = 0;
    DWORD tlsRawEnd = 0;
    DWORD tlsIndexAddress = 0;
    DWORD tlsCallbacksAddress = 0;
    DWORD tlsZeroSize = 0;
    DWORD tlsCharacteristics = 0;
    DWORD tlsRawSize = 0;
    DWORD tlsPayloadSize = 0;
    DWORD tlsAlignedPayload = 0;
    DWORD tlsBlockSize = 0;
    DWORD loadedImageEnd = 0;
    DWORD value32 = 0;
    DWORD tlsBaseField = 0;
    DWORD tlsIndexRaw = 0;
    DWORD resolvedTls = 0;
    DWORD fakeKthread = 0;
    DWORD kthreadTls = 0;
    DWORD simulatedEsp = MERC_STACK_TOP;
    DWORD tickFixture = GetTickCount();
    WORD value16 = 0;
    BYTE value8 = 0;
    BYTE* tlsDestination = NULL;
    BYTE* stack = NULL;
    BYTE* kernelData = NULL;
    BYTE* rawCopy = NULL;
    const BYTE* rawSource = NULL;
    int ok = 1;

    trace("Beginning Phase 2E guest execution-environment construction");

    ok &= check(get_loaded_image_end(memory, &loadedImageEnd),
                "PASS: loaded XBE section high-water mark calculated",
                "FAIL: could not calculate loaded XBE section high-water mark");
    trace_u32("Loaded XBE high-water VA: ", loadedImageEnd);

    ok &= check(loadedImageEnd <= MERC_KERNEL_DATA_BASE,
                "PASS: kernel-data page begins above loaded XBE image",
                "FAIL: kernel-data page overlaps loaded XBE image");

    ok &= check(MERC_KERNEL_DATA_BASE + MERC_KERNEL_DATA_SIZE <=
                MERC_STACK_BASE,
                "PASS: kernel-data page ends before guest stack",
                "FAIL: kernel-data page overlaps guest stack");

    ok &= check(MERC_STACK_BASE + MERC_STACK_SIZE == MERC_HEAP_BASE,
                "PASS: 256 KiB stack terminates exactly at heap base",
                "FAIL: stack/heap boundary mismatch");

    ok &= check(MERC_STACK_TOP >= MERC_STACK_BASE &&
                MERC_STACK_TOP < MERC_HEAP_BASE &&
                (MERC_STACK_TOP & 0xFu) == 0u,
                "PASS: initial guest ESP is inside stack and 16-byte aligned",
                "FAIL: initial guest ESP invariant");

    if (!ok)
        return 0;

    if (!guest_read32(memory, MERC_XBE_BASE + XBE_OFF_TLS, &tlsDirectory) ||
        !check(tlsDirectory == MERC_TLS_VA,
               "PASS: TLS directory VA matches supported retail build",
               "FAIL: TLS directory VA mismatch"))
        return 0;

    if (!guest_read32(memory, tlsDirectory + 0u, &tlsRawStart) ||
        !guest_read32(memory, tlsDirectory + 4u, &tlsRawEnd) ||
        !guest_read32(memory, tlsDirectory + 8u, &tlsIndexAddress) ||
        !guest_read32(memory, tlsDirectory + 12u, &tlsCallbacksAddress) ||
        !guest_read32(memory, tlsDirectory + 16u, &tlsZeroSize) ||
        !guest_read32(memory, tlsDirectory + 20u, &tlsCharacteristics))
    {
        trace("FAIL: could not read six-field retail TLS directory");
        return 0;
    }

    trace_u32("TLS raw start: ", tlsRawStart);
    trace_u32("TLS raw end: ", tlsRawEnd);
    trace_u32("TLS index address: ", tlsIndexAddress);
    trace_u32("TLS callbacks address: ", tlsCallbacksAddress);
    trace_u32("TLS zero-fill bytes: ", tlsZeroSize);
    trace_u32("TLS characteristics: ", tlsCharacteristics);

    if (tlsRawEnd < tlsRawStart)
    {
        trace("FAIL: TLS raw end precedes raw start");
        return 0;
    }

    tlsRawSize = tlsRawEnd - tlsRawStart;

    if (tlsRawSize > 0x10000u ||
        tlsZeroSize > 0x10000u ||
        tlsRawSize > 0x10000u - tlsZeroSize)
    {
        trace("FAIL: TLS raw/zero sizes exceed Phase 2E sanity bounds");
        return 0;
    }

    tlsPayloadSize = tlsRawSize + tlsZeroSize;
    if (tlsPayloadSize > 0xFFF0u)
    {
        trace("FAIL: TLS payload too large for synthetic block");
        return 0;
    }

    tlsAlignedPayload = (tlsPayloadSize + 15u) & ~15u;
    tlsBlockSize = 4u + tlsAlignedPayload;

    if (tlsBlockSize > 0x10000u ||
        !guest_ram_ptr(memory, MERC_FAKE_TLS_VA, tlsBlockSize) ||
        !guest_ram_ptr(memory, MERC_FAKE_KTHREAD_VA, 0x2Cu))
    {
        trace("FAIL: synthetic TLS/KTHREAD ranges are invalid");
        return 0;
    }

    trace_u32("Synthetic TLS block bytes: ", tlsBlockSize);
    trace_u32("Synthetic TLS VA: ", MERC_FAKE_TLS_VA);
    trace_u32("Synthetic KTHREAD VA: ", MERC_FAKE_KTHREAD_VA);

    if (tlsRawSize != 0u)
    {
        rawSource = guest_ram_cptr(memory, tlsRawStart, tlsRawSize);
        if (!rawSource)
        {
            trace("FAIL: retail TLS raw source is outside routed guest RAM");
            return 0;
        }

        rawCopy = (BYTE*)malloc(tlsRawSize);
        if (!rawCopy)
        {
            trace("FAIL: temporary TLS raw-copy allocation failed");
            return 0;
        }

        memcpy(rawCopy, rawSource, tlsRawSize);
    }

    tlsDestination = guest_ram_ptr(memory, MERC_FAKE_TLS_VA, tlsBlockSize);
    memset(tlsDestination, 0, tlsBlockSize);

    if (!guest_write32(memory, MERC_FAKE_TLS_VA, MERC_FAKE_TLS_VA + 4u))
    {
        if (rawCopy) free(rawCopy);
        trace("FAIL: could not write synthetic TLS self/payload pointer");
        return 0;
    }

    if (tlsRawSize != 0u)
        memcpy(tlsDestination + 4u, rawCopy, tlsRawSize);

    ok &= check(tlsRawSize == 0u ||
                memcmp(tlsDestination + 4u, rawCopy, tlsRawSize) == 0,
                "PASS: TLS initialized payload copied exactly",
                "FAIL: TLS initialized payload copy mismatch");

    ok &= check(range_all_zero(tlsDestination + 4u + tlsRawSize,
                               tlsBlockSize - 4u - tlsRawSize),
                "PASS: TLS zero-fill + alignment tail is zero",
                "FAIL: TLS zero-fill/alignment tail contains nonzero bytes");

    if (rawCopy)
    {
        free(rawCopy);
        rawCopy = NULL;
    }

    ok &= check(guest_write32(memory, 0x00u, 0xFFFFFFFFu),
                "PASS: TIB SEH end-of-chain written",
                "FAIL: TIB SEH write");
    ok &= check(guest_write32(memory, 0x04u,
                              MERC_FAKE_TLS_VA + tlsBlockSize),
                "PASS: TIB TLS-addressing base written",
                "FAIL: TIB fs:[4] write");
    ok &= check(guest_write32(memory, 0x08u, MERC_STACK_BASE),
                "PASS: TIB stack limit written",
                "FAIL: TIB stack-limit write");
    ok &= check(guest_write32(memory, 0x18u, 0u),
                "PASS: TIB self pointer written",
                "FAIL: TIB self-pointer write");
    ok &= check(guest_write32(memory, 0x20u, 0u),
                "PASS: TIB PRCB compatibility pointer written",
                "FAIL: TIB PRCB write");
    ok &= check(guest_write32(memory, 0x28u, MERC_FAKE_KTHREAD_VA),
                "PASS: TIB CurrentThread/KTHREAD pointer written",
                "FAIL: TIB CurrentThread write");
    ok &= check(guest_write32(memory, MERC_FAKE_KTHREAD_VA + 0x28u,
                              MERC_FAKE_TLS_VA),
                "PASS: KTHREAD TlsData pointer written",
                "FAIL: KTHREAD TlsData write");

    if (tlsIndexAddress >= MERC_XBE_BASE &&
        tlsIndexAddress + 4u <= MERC_GUEST_RAM_SIZE)
    {
        DWORD negativeIndex = (DWORD)(0u - (tlsBlockSize / 4u));
        ok &= check(guest_write32(memory, tlsIndexAddress, negativeIndex),
                    "PASS: negative Xbox TLS index written",
                    "FAIL: TLS index write");
    }
    else
    {
        trace("FAIL: retail TLS index address is outside low guest RAM");
        ok = 0;
    }

    if (!ok)
        return 0;

    ok &= check(guest_read32(memory, 0x00u, &value32) &&
                value32 == 0xFFFFFFFFu,
                "PASS: TIB fs:[0] reads SEH terminator",
                "FAIL: TIB fs:[0] readback");

    ok &= check(guest_read32(memory, 0x04u, &tlsBaseField) &&
                tlsBaseField == MERC_FAKE_TLS_VA + tlsBlockSize,
                "PASS: TIB fs:[4] reads synthetic TLS base equation",
                "FAIL: TIB fs:[4] readback");

    ok &= check(guest_read32(memory, 0x28u, &fakeKthread) &&
                fakeKthread == MERC_FAKE_KTHREAD_VA,
                "PASS: TIB fs:[0x28] resolves fake KTHREAD",
                "FAIL: TIB CurrentThread readback");

    ok &= check(guest_read32(memory, fakeKthread + 0x28u, &kthreadTls) &&
                kthreadTls == MERC_FAKE_TLS_VA,
                "PASS: KTHREAD+0x28 resolves synthetic TLS block",
                "FAIL: KTHREAD TlsData chain");

    ok &= check(guest_read32(memory, MERC_FAKE_TLS_VA, &value32) &&
                value32 == MERC_FAKE_TLS_VA + 4u,
                "PASS: TLS first dword points to payload",
                "FAIL: TLS first-dword payload pointer");

    ok &= check(guest_read32(memory, tlsIndexAddress, &tlsIndexRaw),
                "PASS: TLS index readback",
                "FAIL: TLS index readback");

    if (ok)
    {
        LONG signedIndex = (LONG)tlsIndexRaw;
        LONG resolved = (LONG)tlsBaseField + signedIndex * 4;
        resolvedTls = (DWORD)resolved;

        trace_u32("Resolved fs:[4] + TLS index*4: ", resolvedTls);
        ok &= check(resolvedTls == MERC_FAKE_TLS_VA,
                    "PASS: Xbox negative TLS-index address equation resolves",
                    "FAIL: Xbox TLS-index address equation mismatch");
    }

    ok &= check(guest_read32(memory, 0x04000004u, &value32) &&
                value32 == tlsBaseField,
                "PASS: TIB is coherent through first 64 MiB mirror",
                "FAIL: TIB mirror coherence");

    kernelData = guest_ram_ptr(memory, MERC_KERNEL_DATA_BASE,
                               MERC_KERNEL_DATA_SIZE);
    stack = guest_ram_ptr(memory, MERC_STACK_BASE, MERC_STACK_SIZE);

    if (!kernelData || !stack)
    {
        trace("FAIL: kernel-data or stack backing is outside routed guest RAM");
        return 0;
    }

    memset(kernelData, 0, MERC_KERNEL_DATA_SIZE);
    memset(stack, 0, MERC_STACK_SIZE);

    ok &= check(guest_write32(memory,
                              MERC_KERNEL_DATA_BASE + KDATA_HARDWARE_INFO + 0u,
                              0u),
                "PASS: XboxHardwareInfo flags initialized as retail",
                "FAIL: XboxHardwareInfo flags write");
    ok &= check(guest_write8(memory,
                             MERC_KERNEL_DATA_BASE + KDATA_HARDWARE_INFO + 4u,
                             0xA1u) &&
                guest_write8(memory,
                             MERC_KERNEL_DATA_BASE + KDATA_HARDWARE_INFO + 5u,
                             0xB1u),
                "PASS: XboxHardwareInfo NV2A/MCPX revisions initialized",
                "FAIL: XboxHardwareInfo revision writes");

    ok &= check(guest_write16(memory,
                              MERC_KERNEL_DATA_BASE + KDATA_KRNL_VERSION + 0u,
                              1u) &&
                guest_write16(memory,
                              MERC_KERNEL_DATA_BASE + KDATA_KRNL_VERSION + 2u,
                              0u) &&
                guest_write16(memory,
                              MERC_KERNEL_DATA_BASE + KDATA_KRNL_VERSION + 4u,
                              5849u) &&
                guest_write16(memory,
                              MERC_KERNEL_DATA_BASE + KDATA_KRNL_VERSION + 6u,
                              0u),
                "PASS: XboxKrnlVersion 1.0.5849.0 initialized",
                "FAIL: XboxKrnlVersion writes");

    ok &= check(guest_write32(memory,
                              MERC_KERNEL_DATA_BASE + KDATA_TICK_COUNT,
                              tickFixture),
                "PASS: KeTickCount fixture initialized",
                "FAIL: KeTickCount fixture write");

    ok &= check(guest_read8(memory,
                            MERC_KERNEL_DATA_BASE + KDATA_HARDWARE_INFO + 4u,
                            &value8) && value8 == 0xA1u,
                "PASS: NV2A revision byte readback",
                "FAIL: NV2A revision readback");

    ok &= check(guest_read16(memory,
                             MERC_KERNEL_DATA_BASE + KDATA_KRNL_VERSION + 4u,
                             &value16) && value16 == 5849u,
                "PASS: kernel build 5849 endian-safe readback",
                "FAIL: kernel build readback");

    ok &= check(guest_read16(memory,
                             0x0487E014u,
                             &value16) && value16 == 5849u,
                "PASS: kernel data coherent through RAM mirror",
                "FAIL: kernel data mirror coherence");

    ok &= check(guest_read16(memory,
                             0x8087E014u,
                             &value16) && value16 == 5849u,
                "PASS: kernel data coherent through KSEG0 alias",
                "FAIL: kernel data KSEG0 coherence");

    simulatedEsp -= 4u;
    ok &= check(guest_write32(memory, simulatedEsp, 0xC0DEF00Du),
                "PASS: guest PUSH32 fixture wrote below initial ESP",
                "FAIL: guest PUSH32 fixture write");
    ok &= check(guest_read32(memory, simulatedEsp, &value32) &&
                value32 == 0xC0DEF00Du,
                "PASS: guest stack dword round-trip",
                "FAIL: guest stack dword round-trip");
    simulatedEsp += 4u;
    ok &= check(simulatedEsp == MERC_STACK_TOP,
                "PASS: guest POP32 fixture restores initial ESP",
                "FAIL: guest stack pointer did not restore");
    guest_write32(memory, MERC_STACK_TOP - 4u, 0u);

    trace_u32("Guest stack base: ", MERC_STACK_BASE);
    trace_u32("Guest stack top/initial ESP: ", MERC_STACK_TOP);
    trace_u32("Guest heap base: ", MERC_HEAP_BASE);
    trace_u32("Kernel data base: ", MERC_KERNEL_DATA_BASE);

    if (ok)
        trace("PASS: Phase 2E TIB/TLS/stack/kernel-data environment is internally coherent");

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
        "game:\\merc360-phase2e-env.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 2E GUEST EXECUTION ENVIRONMENT DIAGNOSTIC START");
    trace("BUILD TAG: P2E-ENV-20261018-A");
    trace("Expected user file: game:\\default.xbe");
    trace("Exact XBE is loaded as data; translated game entry remains disabled");

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

        if (!verify_supported_xbe_hash(&xbe))
        {
            trace("PHASE 2E EXACT RETAIL VERIFICATION: FAIL");
            break;
        }

        trace("PHASE 2E EXACT RETAIL VERIFICATION: PASS");

        result = load_supported_xbe(&xbe, &memory);
        if (!result)
        {
            trace("PHASE 2E VERIFIED XBE LOAD RESULT: FAIL");
            break;
        }

        trace("PHASE 2E VERIFIED XBE LOAD RESULT: PASS");

        result = initialize_execution_environment(&memory);
        if (result)
            trace("PHASE 2E EXECUTION ENVIRONMENT RESULT: PASS");
        else
            trace("PHASE 2E EXECUTION ENVIRONMENT RESULT: FAIL");
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

    trace("PHASE 2E GUEST EXECUTION ENVIRONMENT DIAGNOSTIC END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}
