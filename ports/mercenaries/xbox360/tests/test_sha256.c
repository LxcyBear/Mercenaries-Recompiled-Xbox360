/*
 * Portable SHA-256 contract test for Phase 2C.
 *
 * Mirrors the self-contained Xbox 360 diagnostic's hashing implementation.
 * This does not read or include any retail game content.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint8_t  BYTE;
typedef uint32_t DWORD;
typedef uint64_t QWORD;

typedef struct Sha256Context
{
    DWORD state[8];
    QWORD bitCount;
    BYTE buffer[64];
    DWORD bufferLength;
} Sha256Context;

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
    ctx->bitCount = 0u;
    ctx->bufferLength = 0u;
}

static void sha256_update(Sha256Context* ctx, const BYTE* data, DWORD length)
{
    DWORD offset = 0u;
    ctx->bitCount += (QWORD)length * 8u;

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
            ctx->bufferLength = 0u;
        }
    }
}

static void sha256_final(Sha256Context* ctx, BYTE digest[32])
{
    QWORD bits = ctx->bitCount;
    DWORD i;

    ctx->buffer[ctx->bufferLength++] = 0x80u;

    if (ctx->bufferLength > 56u)
    {
        while (ctx->bufferLength < 64u)
            ctx->buffer[ctx->bufferLength++] = 0u;
        sha256_transform(ctx, ctx->buffer);
        ctx->bufferLength = 0u;
    }

    while (ctx->bufferLength < 56u)
        ctx->buffer[ctx->bufferLength++] = 0u;

    for (i = 0; i < 8u; ++i)
        ctx->buffer[56u + i] = (BYTE)(bits >> (56u - i * 8u));

    sha256_transform(ctx, ctx->buffer);

    for (i = 0; i < 8u; ++i)
        sha_write_be32(digest + i * 4u, ctx->state[i]);
}

static void sha256_bytes(const BYTE* data, DWORD length, BYTE digest[32])
{
    Sha256Context ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, data, length);
    sha256_final(&ctx, digest);
}

static int check_vector(const char* input, const char* expected)
{
    BYTE digest[32];
    char actual[65];
    static const char hex[] = "0123456789abcdef";
    DWORD i;

    sha256_bytes((const BYTE*)input, (DWORD)strlen(input), digest);

    for (i = 0; i < 32u; ++i)
    {
        actual[i * 2u] = hex[(digest[i] >> 4) & 0x0Fu];
        actual[i * 2u + 1u] = hex[digest[i] & 0x0Fu];
    }
    actual[64] = '\0';

    if (strcmp(actual, expected) != 0)
    {
        fprintf(stderr, "FAIL\nexpected %s\nactual   %s\n", expected, actual);
        return 0;
    }

    return 1;
}

int main(void)
{
    int ok = 1;

    ok &= check_vector(
        "",
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    ok &= check_vector(
        "abc",
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    ok &= check_vector(
        "The quick brown fox jumps over the lazy dog",
        "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592");

    if (!ok)
        return 1;

    puts("PASS: SHA-256 standard vectors");
    return 0;
}
