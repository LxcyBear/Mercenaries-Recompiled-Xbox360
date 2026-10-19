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


OLD_PROJECTILE_CALL = "if ((edi != 0)) { sub_00020095(); return; }"
NEW_PROJECTILE_CALL = "if ((edi != 0)) goto loc_00020095;"

OLD_WEAPON_TAIL = "g_seh_ebp = ebp; sub_000357E4(); return;"
NEW_WEAPON_TAIL = "goto loc_000357E4;"


def _repair_residual_continuations(root: Path) -> tuple[int, int]:
    projectile = weapon = 0
    for path in sorted(root.glob("recomp_*.c")):
        text = path.read_text(encoding="utf-8")
        changed = False

        count = text.count(OLD_PROJECTILE_CALL)
        if count:
            if count != 1:
                raise RuntimeError(
                    f"{path.name}: unexpected projectile 0x00020095 call count {count}"
                )
            if "loc_00020095:" not in text:
                raise RuntimeError(
                    f"{path.name}: projectile 0x00020095 label missing"
                )
            text = text.replace(OLD_PROJECTILE_CALL, NEW_PROJECTILE_CALL)
            projectile += count
            changed = True
        elif NEW_PROJECTILE_CALL in text:
            projectile += text.count(NEW_PROJECTILE_CALL)

        count = text.count(OLD_WEAPON_TAIL)
        if count:
            if count != 4:
                raise RuntimeError(
                    f"{path.name}: unexpected weapon 0x000357E4 call count {count}"
                )
            if "loc_000357E4:" not in text:
                raise RuntimeError(
                    f"{path.name}: weapon 0x000357E4 label missing"
                )
            text = text.replace(OLD_WEAPON_TAIL, NEW_WEAPON_TAIL)
            weapon += count
            changed = True
        elif NEW_WEAPON_TAIL in text and "loc_000357E4:" in text:
            weapon += text.count(NEW_WEAPON_TAIL)

        if changed:
            path.write_text(text, encoding="utf-8", newline="")

    if projectile != 1 or weapon != 4:
        raise RuntimeError(
            "expected repaired continuation counts "
            f"projectile=1, weapon=4; found projectile={projectile}, weapon={weapon}"
        )
    return projectile, weapon


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
    projectile, weapon = _repair_residual_continuations(root)
    print(
        "PASS: Phase 3N residual continuation repairs ready: "
        f"projectile={projectile}, weapon={weapon}"
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
