"""
Phase 3A regression checks for explicit scalar guest-memory emission.

The normal generator must retain historical MEM lvalue output unless the
Xbox-360-oriented explicit ABI is selected.  The explicit mode must describe
read/write direction so a big-endian target can route and byte-swap safely.
"""

from types import SimpleNamespace

from tools.recomp import lifter


def mem(size, base="ecx", disp=4):
    return SimpleNamespace(
        type="mem",
        mem_size=size,
        mem_base=base,
        mem_index=None,
        mem_scale=1,
        mem_disp=disp,
    )


def reg(name):
    return SimpleNamespace(type="reg", reg=name)


def imm(value):
    return SimpleNamespace(type="imm", imm=value)


def main():
    m32 = mem(4)

    lifter.configure_guest_memory_abi(False)
    assert lifter.guest_memory_abi_is_explicit() is False
    assert lifter._fmt_mem_read(m32) == "MEM32(ecx + 4)"
    assert lifter._fmt_mem_write(m32, "eax") == "MEM32(ecx + 4) = eax;"

    legacy_rmw = lifter.Lifter()._lift_alu_binop(
        None, [m32, reg("eax")], "add"
    )
    assert legacy_rmw == ["MEM32(ecx + 4) = MEM32(ecx + 4) + eax;"]

    lifter.configure_guest_memory_abi(True)
    assert lifter.guest_memory_abi_is_explicit() is True

    assert lifter._fmt_mem_read(mem(1)) == "GUEST_READ8(ecx + 4)"
    assert lifter._fmt_mem_read(mem(2)) == "GUEST_READ16(ecx + 4)"
    assert lifter._fmt_mem_read(mem(4)) == "GUEST_READ32(ecx + 4)"
    assert lifter._fmt_mem_read(mem(8)) == "GUEST_READ64(ecx + 4)"

    assert lifter._fmt_mem_write(mem(1), "eax") == (
        "GUEST_WRITE8(ecx + 4, eax);"
    )
    assert lifter._fmt_mem_write(mem(2), "eax") == (
        "GUEST_WRITE16(ecx + 4, eax);"
    )
    assert lifter._fmt_mem_write(mem(4), "eax") == (
        "GUEST_WRITE32(ecx + 4, eax);"
    )
    assert lifter._fmt_mem_write(mem(8), "eax") == (
        "GUEST_WRITE64(ecx + 4, eax);"
    )

    explicit_rmw = lifter.Lifter()._lift_alu_binop(
        None, [m32, reg("eax")], "add"
    )
    assert explicit_rmw == [
        "GUEST_WRITE32(ecx + 4, GUEST_READ32(ecx + 4) + eax);"
    ]

    # MOV-like source/destination formatting also follows the selected ABI.
    assert lifter._fmt_operand_read(m32) == "GUEST_READ32(ecx + 4)"
    assert lifter._fmt_operand_write(m32, "0x1234") == (
        "GUEST_WRITE32(ecx + 4, 0x1234);"
    )

    # Restore the default so this test cannot leak explicit mode into a caller.
    lifter.configure_guest_memory_abi(False)
    print("PASS: Phase 3A scalar guest-memory lifter emission")


if __name__ == "__main__":
    main()
