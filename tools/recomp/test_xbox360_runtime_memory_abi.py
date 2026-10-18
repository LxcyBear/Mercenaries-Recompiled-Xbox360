"""Regression checks for Phase 3D explicit-memory cleanup."""

from types import SimpleNamespace
from tools.recomp import lifter
from tools.recomp.audit_explicit_guest_memory import find_legacy_accesses


def insn():
    return SimpleNamespace()


def main():
    l = lifter.Lifter()

    lifter.configure_guest_memory_abi(False)
    assert l._lift_string_op(insn(), "movsd") == [
        "MEM32(edi) = MEM32(esi); esi += 4; edi += 4; /* movsd */"
    ]

    lifter.configure_guest_memory_abi(True)

    assert l._lift_string_op(insn(), "movsb") == [
        "GUEST_WRITE8(edi, GUEST_READ8(esi)); esi++; edi++; /* movsb */"
    ]
    assert l._lift_string_op(insn(), "movsd") == [
        "GUEST_WRITE32(edi, GUEST_READ32(esi)); esi += 4; edi += 4; /* movsd */"
    ]
    assert l._lift_string_op(insn(), "stosw") == [
        "GUEST_WRITE16(edi, LO16(eax)); edi += 2; /* stosw */"
    ]
    assert l._lift_string_op(insn(), "lodsd") == [
        "eax = GUEST_READ32(esi); esi += 4; /* lodsd */"
    ]

    l._direction_step = 1
    rep = l._lift_rep_string(insn(), "rep stosd")
    assert "GUEST_WRITE32(edi + _i*4, eax);" in rep[0]
    assert "MEM32(" not in rep[0]

    cmps = l._lift_rep_string(insn(), "repe cmpsw")
    joined = "\n".join(cmps)
    assert "GUEST_READ16(esi)" in joined
    assert "GUEST_READ16(edi)" in joined
    assert "MEM16(" not in joined

    l._direction_step = -1
    rep_back = l._lift_rep_string(insn(), "rep movsd")
    joined_back = "\n".join(rep_back)
    assert "GUEST_WRITE32(edi - _i*4, GUEST_READ32(esi - _i*4));" in joined_back
    assert "MEM32(" not in joined_back

    assert find_legacy_accesses("eax = MEM32(ecx + 4);\n") == [
        (1, "eax = MEM32(ecx + 4);")
    ]
    assert find_legacy_accesses(
        "/* MEM32(ecx) = 1; */\n"
        "eax = GUEST_READ32(ecx);\n"
        "// MEMF(esp) = 1.0f;\n"
    ) == []

    lifter.configure_guest_memory_abi(False)
    print("PASS: Phase 3D explicit runtime/string memory cleanup")


if __name__ == "__main__":
    main()
