#!/usr/bin/env python3
"""Repair Phase 3N's two known guest-pointer helper call sites in-place.

This is intentionally narrow and idempotent. It exists only so a failed
Stage-A lowering run can resume from its already translated/patched tree after
the canonical Patch-Generated.py source has been corrected.
"""

from pathlib import Path
import argparse
import sys

OLD_PARAMS = """    { void recomp_original_bug_cloud_params(volatile uint32_t *, volatile uint32_t *);
      recomp_original_bug_cloud_params(&MEM32(esp + 4), &MEM32(esp + 8)); }
"""
NEW_PARAMS = """    { void recomp_original_bug_cloud_params(volatile uint32_t *, volatile uint32_t *);
      const uint32_t _cloud_in_addr = esp + 4u;
      const uint32_t _cloud_out_addr = esp + 8u;
      uint32_t _cloud_in = GUEST_READ32(_cloud_in_addr);
      uint32_t _cloud_out = GUEST_READ32(_cloud_out_addr);
      recomp_original_bug_cloud_params(&_cloud_in, &_cloud_out);
      GUEST_WRITE32(_cloud_in_addr, _cloud_in);
      GUEST_WRITE32(_cloud_out_addr, _cloud_out); }
"""

OLD_COLORS = """    { void recomp_original_bug_cloud_colors(volatile float *);
      recomp_original_bug_cloud_colors(&MEMF(edx)); }
"""
NEW_COLORS = """    { void recomp_original_bug_cloud_colors(volatile float *);
      const uint32_t _cloud_rgba_addr = edx;
      float _cloud_rgba[36]; unsigned _cloud_i;
      for (_cloud_i = 0; _cloud_i < 36u; ++_cloud_i)
          _cloud_rgba[_cloud_i] = GUEST_READF32(_cloud_rgba_addr + _cloud_i * 4u);
      recomp_original_bug_cloud_colors(_cloud_rgba);
      for (_cloud_i = 0; _cloud_i < 36u; ++_cloud_i)
          GUEST_WRITEF32(_cloud_rgba_addr + _cloud_i * 4u, _cloud_rgba[_cloud_i]); }
"""


def repair(root: Path) -> tuple[int, int]:
    params = colors = 0
    for path in sorted(root.glob("recomp_*.c")):
        text = path.read_text(encoding="utf-8")
        changed = False

        if OLD_PARAMS in text:
            if text.count(OLD_PARAMS) != 1:
                raise RuntimeError(f"{path.name}: unexpected cloud-params match count")
            text = text.replace(OLD_PARAMS, NEW_PARAMS)
            params += 1
            changed = True
        elif NEW_PARAMS in text:
            params += 1

        if OLD_COLORS in text:
            if text.count(OLD_COLORS) != 1:
                raise RuntimeError(f"{path.name}: unexpected cloud-colors match count")
            text = text.replace(OLD_COLORS, NEW_COLORS)
            colors += 1
            changed = True
        elif NEW_COLORS in text:
            colors += 1

        if changed:
            path.write_text(text, encoding="utf-8", newline="")

    if params != 1 or colors != 1:
        raise RuntimeError(
            f"expected exactly one cloud params and one cloud colors bridge; "
            f"found params={params}, colors={colors}"
        )
    return params, colors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("generated_root", type=Path)
    args = parser.parse_args()
    try:
        params, colors = repair(args.generated_root)
    except (OSError, RuntimeError) as exc:
        print(f"FAIL: Phase 3N guest-pointer repair: {exc}", file=sys.stderr)
        return 1
    print(
        "PASS: Phase 3N guest-pointer bridges ready: "
        f"cloud_params={params}, cloud_colors={colors}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
