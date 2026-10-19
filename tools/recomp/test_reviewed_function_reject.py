"""Regression coverage for reviewed non-code function rejects."""

from tools.disasm.cache import AnalysisCache
from tools.disasm.functions import FunctionDetector


def main():
    rejected = 0x002DBC98
    detector = FunctionDetector(
        None, None, None, None,
        rejected_function_addresses=[rejected],
    )
    detector._add_candidate(rejected, 0.99, "seed_vtable_thunk")
    detector._add_candidate(0x002DBC0F, 0.99, "seed_vtable_thunk")

    assert rejected not in detector._candidates
    assert 0x002DBC0F in detector._candidates

    base_key = AnalysisCache._opts_key(
        False, ["XPP"], [0x002DBC98], [], []
    )
    reject_key = AnalysisCache._opts_key(
        False, ["XPP"], [0x002DBC98], [], [rejected]
    )
    assert base_key != reject_key

    print("PASS: reviewed function reject blocks every candidate source")


if __name__ == "__main__":
    main()
