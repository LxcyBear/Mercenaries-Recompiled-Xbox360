#!/usr/bin/env python3
"""Convert user-local TGP482 XBE scanner TOML into shareable symbol metadata.

Never includes XBE bytes, user paths, or generated guest code.
Scanner assignments are not all byte matches: some come from XTLID/constants.
"""
import argparse
import csv
import json
import re
import zipfile
from pathlib import Path

ASSIGNMENT=re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(0x[0-9a-fA-F]+|\d+)\s*(?:#.*)?$')
EXPECTED_TITLE=0x4C410015
EXPECTED_BUILD=5849
PRIORITY=("D3DDevice_Swap","XInputOpen","D3DDevice_SetVertexShader",
          "D3DDevice_SetStreamSource","D3DDevice_SetTexture",
          "D3DDevice_PersistDisplay","Direct3D_CreateDevice")
ORIGINAL_CANDIDATES=(0x002D52D4,0x002D5272,0x0028BDB0,
                     0x0028A530,0x00288F80,0x00288B30,0x00289E20)

def config_tables(path):
    tables={"xbe":{},"symbols":{},"data":{}}
    section=None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line=line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section=line[1:-1]
            continue
        if section not in tables:
            continue
        found=ASSIGNMENT.fullmatch(line)
        if found:
            key,raw=found.groups()
            if key in tables[section]:
                raise ValueError("Duplicate scanner metadata field: "+key)
            tables[section][key]=int(raw,0)
    if tables["xbe"].get("title")!=EXPECTED_TITLE or tables["xbe"].get("xdk")!=EXPECTED_BUILD:
        raise ValueError("Wrong scanner configuration Title ID or XDK build")
    if len(tables["symbols"])<200 or len(tables["data"])<8:
        raise ValueError("Unexpected incomplete scanner output; refusing misleading report")
    return tables

def old_functions(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        payload=json.loads(z.read("xboxrecomp_manifest.json"))
    if not payload.get("no_raw_game_bytes") or payload.get("functions")!=16662:
        raise ValueError("Old inventory does not match the expected metadata-only proof")
    return {int(row["address"],16):row for row in payload["function_list"]}

def main():
    ap=argparse.ArgumentParser()
    for key in ("config","old_zip","out_txt","out_csv"):
        ap.add_argument("--"+key.replace("_","-"),required=True,type=Path)
    a=ap.parse_args()
    tables=config_tables(a.config)
    previous=old_functions(a.old_zip)
    symbols=tables["symbols"]
    data=tables["data"]
    reverse={}
    for name,va in symbols.items():
        if va:
            reverse.setdefault(va,[]).append(name)
    lines=[
        "[TGP-XBR-SCAN] ===============================================",
        "[TGP-XBR-SCAN]  INDEPENDENT RETAIL XBE IDENTITIES - METADATA",
        "[TGP-XBR-SCAN] ===============================================",
        "[TGP-XBR-SCAN] TITLE ID: 0x4C410015  XDK library build: 5849",
        "[TGP-XBR-SCAN] Scanner-assigned functions: %d / %d"%(
            sum(bool(v) for v in symbols.values()),len(symbols)),
        "[TGP-XBR-SCAN] Scanner-assigned data: %d / %d"%(
            sum(bool(v) for v in data.values()),len(data)),
        "[TGP-XBR-SCAN] Some assignments use signature bytes, XTLID, or constants.",
        "[TGP-XBR-SCAN] These are NOT all byte-signature matches.",
        ""
    ]
    for name in PRIORITY:
        va=symbols.get(name,0)
        lines.append("[TGP-XBR-SCAN] %s = %s"%(
            name,("0x%08X"%va if va else "UNASSIGNED")))
        if va in previous:
            row=previous[va]
            lines.append("    xboxrecomp: %s %s..%s size=%s prior_pixel_batch=%s"%(
                row["section"],row["address"],row["end"],row["size"],
                row.get("present_in_pixel_true_tus")))
            lines.append("    xboxrecomp direct children: "+", ".join(row.get("calls_to",[])[:16]))
        elif va:
            containing=[r for start,r in previous.items()
                        if start<=va<int(r["end"],16)]
            lines.append("    no matching exact original function start; containing: "+
                         (", ".join(r["address"]+".."+r["end"] for r in containing[:3])
                          or "NONE"))
    lines.append("")
    lines.append("[TGP-XBR-SCAN] RECENT FRONTIERS / PREVIOUS SIZE-ONLY GUESSES:")
    for va in ORIGINAL_CANDIDATES:
        names=sorted(reverse.get(va,[]))
        old=previous.get(va)
        lines.append("    0x%08X: scanner=%s old_section=%s"%(
            va,",".join(names) if names else "UNASSIGNED",
            old["section"] if old else "NOT_EXACT"))
    lines.extend([
        "",
        "[TGP-XBR-SCAN] D3DDevice_Swap is a candidate presentation watchpoint,",
        "[TGP-XBR-SCAN] not proof guest execution reached frame presentation.",
        "[TGP-XBR-SCAN] Previous Xbox hardware frontier: 0x002D52D4 at 27,107,602 ticks.",
        "[TGP-XBR-SCAN] Unassigned symbols are not necessarily game-used functions.",
        "[TGP-XBR-SCAN] Only generic names/addresses are exported. No XBE bytes.",
    ])
    a.out_txt.parent.mkdir(parents=True,exist_ok=True)
    a.out_csv.parent.mkdir(parents=True,exist_ok=True)
    a.out_txt.write_text("\n".join(lines)+"\n",encoding="utf-8")
    with a.out_csv.open("w",newline="",encoding="utf-8") as fp:
        w=csv.writer(fp)
        w.writerow(("symbol","scanner_address","original_section","original_size",
                    "original_start_exact","old_pixel_batch"))
        for name,va in sorted(symbols.items()):
            old=previous.get(va)
            w.writerow((name,"0x%08X"%va if va else "",old["section"] if old else "",
                        old["size"] if old else "",bool(old) if va else False,
                        old.get("present_in_pixel_true_tus") if old else ""))
    print("\n".join(lines))
    print("[TGP-XBR-SCAN] REPORT="+str(a.out_txt))
    print("[TGP-XBR-SCAN] CSV="+str(a.out_csv))

if __name__=="__main__":
    main()
