"""Regression coverage for Phase 3N unresolved symbol-reference auditing."""

from pathlib import Path
import tempfile

from tools.recomp.audit_phase3n_portability import scan_tree


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "recomp_stubs_unresolved.c").write_text(
            "void sub_00123456(void) { esp += 4; "
            "/* 0x00123456: not detected; minimal guest ret */ }\n",
            encoding="utf-8",
        )
        (root / "recomp_0000.c").write_text(
            "void sub_00800000(void)\n"
            "{\n"
            "    void (*target)(void) = &sub_00123456;\n"
            "    (void)target;\n"
            "}\n",
            encoding="utf-8",
        )

        report = scan_tree(root)
        assert report["residual_unresolved_stubs"] == 1
        entry = report["unresolved_classification"]["entries"][0]
        assert entry["name"] == "sub_00123456"
        assert entry["reference_count"] == 1
        assert "&sub_00123456" in entry["references"][0]["sites"][0]["text"]

    print("PASS: Phase 3N unresolved audit catches address-taken references")


if __name__ == "__main__":
    main()
