#!/usr/bin/env python3
"""Source-free, retail-free, XDK-free integration-map regression tests."""
from __future__ import annotations
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT=Path(__file__).resolve().parent/"Build-IntegrationMap.py"

def run(*args):
    return subprocess.run(
        [sys.executable,str(SCRIPT),*map(str,args)],
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        text=True,timeout=20)

def check():
    with tempfile.TemporaryDirectory(prefix="merc360-map-test-") as temp:
        root=Path(temp)
        main=root/"main.cpp"
        main.write_text(
            "P6DQ-R76-XGSCNT-CENTRAL-ROUTE-20261029\n"
            "#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) \\\n"
            "  if (_phase4c_target == 0x80000080u) f(); \\\n"
            "  else f();\n"
            "#define RECOMP_ITAIL(xbox_va) f();\n"
            "void phase5bc_dispatch_packed_icall(uint32_t target) {\n"
            "  if (target == 0x80000097u) { f(); }\n"
            "}\n",encoding="utf-8")
        source=root/"guest.cpp"
        source.write_text(
            "P6DQ R59 FC4A ABI RESTORE:\n"
            + "".join(f"void sub_{x:08X}(void) {{ sub_00000001(); }}\n"
                      for x in range(13000))
            + "uint32_t test_mmio=0xFE80200Cu;\n" 
            + "uint32_t test_signed=-25157620;\n"
            + "uint32_t test_import=0x80000080u;\n",encoding="utf-8")
        hardware=root/"watson.txt"
        hardware.write_text(
            "P6DQ ROCKET JOURNAL HARD[0] kind=2 caller=002A5293 "
            "target=80000080 hits=5 esp=008BFA00 ticks=26720251\n"
            "BOUNDARY: kind=ICALL_SAFE caller=002A5293 "
            "target=80000080 esp=008BFA00\n",encoding="utf-8")
        out=root/"out"
        args=("--main",main,"--source",source,
              "--out",out,"--hardware-log",hardware)
        first=run(*args)
        assert first.returncode==0,first.stdout
        report=json.loads((out/"phase6-integration-map.json").read_text())
        assert report["counts"]["guest_functions"]==13000
        assert report["counts"]["explicit_kernel_routes"]==2
        assert report["counts"]["literal_mmio_addresses"]==1
        assert report["counts"]["guest_call_edges"]==13000
        assert not report["import_inventory"]["verified"]
        with (out/"kernel-coverage.csv").open(newline="") as f:
            coverage=list(csv.DictReader(f))
        known={int(item["ordinal"]) for item in coverage}
        assert (out/"guest-call-edges.csv").is_file()
        with (out/"mmio-literals.csv").open(newline="") as f:
            mmio=list(csv.DictReader(f))
        assert mmio==[{"address":"FE80200C","literal_mentions":"2",
                        "subsystem":"APU_CORE","status":"STATIC_CANDIDATE_ONLY"}]
        assert known=={128,151},coverage
        ledger=json.loads((out/"fault-ledger.json").read_text())
        assert len(ledger["faults"])==2
        assert sum(v["hits"] for v in ledger["faults"].values())==6
        # Running the same log again must never increase fault counts.
        second=run(*args)
        assert second.returncode==0,second.stdout
        ledger_again=json.loads((out/"fault-ledger.json").read_text())
        assert ledger_again==ledger
        # Explicitly prevent source audits from masquerading as Xbox logs.
        audit=root/"r77-source-audit.txt"
        audit.write_text("[Phase6R77] EXACT 80000080 KERNEL IMPORT AUDIT\n")
        not_hardware=run("--main",main,"--source",source,"--out",out,
                         "--hardware-log",audit)
        assert not_hardware.returncode!=0
        assert "source audit" in not_hardware.stdout.lower()
        # Never silently accept unknown/incorrect retail file bytes.
        fake_xbe=root/"not-real.xbe"
        fake_xbe.write_bytes(b"XBEH"+bytes(1024))
        wrong_xbe=run("--main",main,"--source",source,"--out",out,
                      "--retail-xbe",fake_xbe)
        assert wrong_xbe.returncode!=0
        assert "identity mismatch" in wrong_xbe.stdout
        assert (out/"PHASE6_MAP.md").is_file()
        planner=Path(__file__).resolve().parent/"Plan-IntegrationBatches.py"
        planned=subprocess.run([sys.executable,str(planner),"--out",str(out)],
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=20)
        assert planned.returncode==0,planned.stdout
        assert (out/"BATCH_PLAN.md").is_file()
        assert (out/"kernel-batch-priorities.csv").is_file()
        assert (out/"guest-abi-hotspots.csv").is_file()
        assert (out/"mmio-batch-families.csv").is_file()
        with (out/"kernel-batch-priorities.csv").open(newline="") as f:
            prioritized=list(csv.DictReader(f))
        assert prioritized[0]["ordinal"]=="128"
        assert prioritized[0]["priority"]=="P0_ACTIVE_HARDWARE_STOP"
        assert prioritized[0]["disposition"]=="HARDWARE_OBSERVED_IMPORT_SLOT_UNVERIFIED"
        assert not any(x["priority"]=="P2_DATA_RELOCATION" for x in prioritized)
        assert all(x["disposition"]!="IMPORTED_CALLABLE_NO_ROUTE_IDENTIFIED"
                   for x in prioritized)
        plan=(out/"BATCH_PLAN.md").read_text(encoding="utf-8")
        assert "NOT ASSESSED (retail XBE needed)" in plan
        assert "Hardware-observed kernel targets with unverified import slot: 1" in plan
        print("[IntegrationMapTest] PASS: hardware observations separate from retail import guesses")
        print("[IntegrationMapTest] PASS: batch planning does not mistake static references for missing imports")
        print("[IntegrationMapTest] PASS: route extraction, 13000 mock ABI edges, signed MMIO")
        print("[IntegrationMapTest] PASS: deterministic fault deduplication")
        print("[IntegrationMapTest] PASS: R77 source-audit and unverified XBE rejection")
        print("[IntegrationMapTest] NO game code, retail XBE, or XDK data used")

if __name__=="__main__":
    check()
