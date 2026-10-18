"""Phase 3B regression checks for signed + x87 guest-memory emission."""

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
    assert lifter._smem_accessor(2) == "SMEM16"
    assert lifter._fmt_float_mem_read(mem(4)) == "MEMF(ecx + 4)"
    assert lifter._fmt_float_mem_read(mem(8)) == "MEMD(ecx + 4)"

    lifter.configure_guest_memory_abi(True)

    assert lifter._smem_accessor(1) == "GUEST_SREAD8"
    assert lifter._smem_accessor(2) == "GUEST_SREAD16"
    assert lifter._smem_accessor(4) == "GUEST_SREAD32"
    assert lifter._smem_accessor(8) == "GUEST_SREAD64"

    assert lifter._fmt_float_mem_read(mem(4)) == "GUEST_READF32(ecx + 4)"
    assert lifter._fmt_float_mem_read(mem(8)) == "GUEST_READF64(ecx + 4)"
    assert lifter._fmt_float_mem_write(mem(4), "value") == (
        "GUEST_WRITEF32(ecx + 4, value);"
    )
    assert lifter._fmt_float_mem_write(mem(8), "value") == (
        "GUEST_WRITEF64(ecx + 4, value);"
    )

    assert l._lift_movsx(None, [reg("eax"), mem(2)]) == [
        "eax = (uint32_t)(int32_t)GUEST_SREAD16(ecx + 4);"
    ]

    assert l._lift_fpu(insn(), "fld", [mem(4)]) == [
        "fp_push(GUEST_READF32(ecx + 4)); /* fld float */"
    ]
    assert l._lift_fpu(insn(), "fstp", [mem(8)]) == [
        "GUEST_WRITEF64(ecx + 4, fp_top()); fp_pop(); /* fstp */"
    ]
    assert l._lift_fpu(insn(), "fild", [mem(2)]) == [
        "fp_push((double)GUEST_SREAD16(ecx + 4)); /* fild */"
    ]
    assert l._lift_fpu(insn(), "fistp", [mem(4)]) == [
        "GUEST_WRITE32(ecx + 4, X87_FIST32(fp_top())); fp_pop(); /* fistp */"
    ]
    assert l._lift_fpu(insn(), "fiadd", [mem(4)]) == [
        "fp_top() += (double)GUEST_SREAD32(ecx + 4); /* fiadd memory */"
    ]
    assert l._lift_fpu(insn(), "fadd", [mem(8)]) == [
        "fp_top() += GUEST_READF64(ecx + 4); /* fadd memory */"
    ]

    fcom = l._lift_fpu(insn("dword ptr [ecx+4]"), "fcom", [mem(4)])
    assert len(fcom) == 1
    assert "GUEST_READF32(ecx + 4)" in fcom[0]
    assert "MEMF(" not in fcom[0]

    lifter.configure_guest_memory_abi(False)
    print("PASS: Phase 3B signed/x87 guest-memory lifter emission")


if __name__ == "__main__":
    main()
