"""Phase 3C regression checks for SSE/XMM + MMX guest-memory emission."""

from types import SimpleNamespace
from tools.recomp import lifter


def mem(size, base="ecx", disp=4):
    return SimpleNamespace(
        type="mem", mem_size=size, mem_base=base, mem_index=None,
        mem_scale=1, mem_disp=disp
    )


def reg(name):
    return SimpleNamespace(type="reg", reg=name)


def insn(text=""):
    return SimpleNamespace(op_str=text)


def main():
    l = lifter.Lifter()

    lifter.configure_guest_memory_abi(False)
    assert l._lift_sse(insn(), "movq", [reg("mm0"), mem(8)]) == [
        "g_mm0 = (uint64_t)(MEM64(ecx + 4)); /* movq */"
    ]
    assert l._lift_sse(insn(), "movss", [mem(4), reg("xmm0")]) == [
        "MEMF(ecx + 4) = xmm0; /* movss */"
    ]

    lifter.configure_guest_memory_abi(True)

    assert l._lift_sse(insn(), "movq", [reg("mm0"), mem(8)]) == [
        "g_mm0 = (uint64_t)(GUEST_READ64(ecx + 4)); /* movq */"
    ]
    assert l._lift_sse(insn(), "movq", [mem(8), reg("mm0")]) == [
        "GUEST_WRITE64(ecx + 4, (uint64_t)(g_mm0)); /* movq */"
    ]

    assert l._lift_sse(insn(), "movss", [mem(4), reg("xmm0")]) == [
        "GUEST_WRITEF32(ecx + 4, xmm0); /* movss */"
    ]
    assert l._lift_sse(insn(), "addss", [reg("xmm0"), mem(4)]) == [
        "xmm0 = xmm0 + GUEST_READF32(ecx + 4); /* addss */"
    ]
    assert l._lift_sse(insn(), "addsd", [reg("xmm0"), mem(8)]) == [
        "xmm0 = xmm0 + GUEST_READF64(ecx + 4); /* addsd */"
    ]

    # Packed XMM moves retain helper calls; the runtime helper implementation
    # selects explicit lane-wise guest access for the Xbox 360 target.
    assert l._lift_sse(insn(), "movaps", [reg("xmm0"), mem(16)]) == [
        "recomp_xmm_load(xmm0v, ecx + 4); /* movaps */"
    ]
    assert l._lift_sse(insn(), "movups", [mem(16), reg("xmm0")]) == [
        "recomp_xmm_store(ecx + 4, xmm0v); /* movups */"
    ]
    assert l._lift_sse(insn(), "movsd", [mem(8), reg("xmm0")]) == [
        "recomp_xmm_storesd(ecx + 4, xmm0v); /* movsd */"
    ]

    # MMX arithmetic with a memory source must read through GUEST_READ64.
    pand = l._lift_sse(insn(), "pand", [reg("mm0"), mem(8)])
    assert pand == [
        "g_mm0 = (uint64_t)(g_mm0 & GUEST_READ64(ecx + 4)); /* pand */"
    ]

    lifter.configure_guest_memory_abi(False)
    print("PASS: Phase 3C SSE/MMX guest-memory lifter emission")


if __name__ == "__main__":
    main()
