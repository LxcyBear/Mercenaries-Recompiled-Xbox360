#!/usr/bin/env python3
"""Locally derive the V6c retail-297 repair from the user's already downloaded Fix2.
No game code, XDK files, or binaries are included. The output is source-only.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
FIX = Path.home() / "Downloads" / "Merc360-K1-V6c-Stage-20EB00-Fix2.py"
OUT = Path.home() / "Downloads" / "Merc360-K1-V6c-Stage-20EB00-Retail297-LOCAL.py"
PC = ROOT / ".deps" / "mercenaries-pc-reference"
COMMIT = "f513ae4e041401b7b032410016940971488d523b"
RETAIL = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"

def fail(reason):
    raise SystemExit("[K1-V6c-297] STOP: " + reason)

def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

if not FIX.is_file():
    fail("Already-downloaded Fix2 not found: " + str(FIX))
if not (PC / ".git").exists():
    fail("Pinned PC reference checkout missing: " + str(PC))
head = subprocess.run(["git", "-C", str(PC), "rev-parse", "HEAD"],
                      capture_output=True, text=True)
if head.returncode != 0 or head.stdout.strip().lower() != COMMIT:
    fail("PC reference not at pinned original commit " + COMMIT)
inventory = PC / "ports/mercenaries/data/generated-patch-inventory.json"
patchfile = PC / "ports/mercenaries/scripts/Patch-Generated.py"
if not inventory.is_file() or not patchfile.is_file():
    fail("Original PC patch #297 evidence missing")
data = json.loads(inventory.read_text(encoding="utf-8-sig"))
items = [p for p in data.get("transformations", [])
         if p.get("index") == 297 and p.get("name") == "PblJoystick logical input checkpoint"]
if (data.get("retail_xbe_sha256", "").upper() != RETAIL or len(items) != 1
    or items[0].get("guest_sites") != ["0020F0D6"]
    or items[0].get("host_helpers") != ["recomp_input_logical_checkpoint"]):
    fail("PC patch 297 identity/retail provenance mismatch")
patchtext = patchfile.read_text(encoding="utf-8-sig")
m = re.search(r'GeneratedPatch\(\s*"PblJoystick logical input checkpoint"\s*,\s*"""(.*?)"""\s*,\s*"""(.*?)"""\s*,\s*\)', patchtext, re.S)
if not m or digest(m.group(1)) != items[0]["before_sha256"] or digest(m.group(2)) != items[0]["after_sha256"]:
    fail("PC patch 297 original before/after hash mismatch")
if (m.group(1) != "loc_0020F0D6: ;\n    POP32(esp, esi);" or
    m.group(2) != "loc_0020F0D6: ;\n    recomp_input_logical_checkpoint(esi);\n    POP32(esp, esi);"):
    fail("Unexpected PC patch 297 semantics")

src = FIX.read_text(encoding="utf-8")
needle = "    root_source=bodies[ROOT]['source']\n"
if src.count(needle) != 1 or "base.mask_noncode(root_source)" not in src:
    fail("Fix2 structure differs; refusing uncertain patch")
insertion = '''    # Verified pinned PC developer patch 297, original retail exit.
    # Remove only the PC-added instrumentation call at exact guest label.
    pc_only=re.compile(
        r"(?m)^([ \\t]*loc_0020F0D6:[ \\t]*;[ \\t]*\\n)"
        r"([ \\t]*PHASE4C_BUDGET_TICK\\(0x0020F0D6u\\);[ \\t]*\\n)?"
        r"[ \\t]*recomp_input_logical_checkpoint\\(esi\\);[ \\t]*\\n"
        r"(?=[ \\t]*POP32\\(esp,[ \\t]*esi\\);)")
    root_source,removed=pc_only.subn(lambda match: match.group(1)+(match.group(2) or ""),root_source)
    if removed!=1 or "recomp_input_logical_checkpoint" in root_source:
        die("Retail patch #297 exact exit site not uniquely restored")
    if root_source.count("esp += 8; return; /* ret 4 */")!=1:
        die("Original guest ret4 exit changed")
    bodies[ROOT]=dict(bodies[ROOT],source=root_source)
    print("[K1-V6c] RETAIL PATCH 297 RESTORED: original PblJoystick POP32/ret4")
'''
updated = src.replace(needle, needle + insertion, 1)
if updated == src or updated.count("RETAIL PATCH 297 RESTORED") != 1:
    fail("No unique verified edit")
if OUT.is_file() and OUT.read_text(encoding="utf-8") != updated:
    fail("Refusing overwrite of different existing derived local script: " + str(OUT))
OUT.write_text(updated, encoding="utf-8")
subprocess.run([sys.executable, "-m", "py_compile", str(OUT)], check=True)
print("[K1-V6c-297] Pinned patch #297 verified; local derived Python syntax PASS")
print("[K1-V6c-297] Script:", OUT)
print("[K1-V6c-297] Run: python \"" + str(OUT) + "\"")
