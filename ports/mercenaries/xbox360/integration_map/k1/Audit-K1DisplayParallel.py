#!/usr/bin/env python3
"""Source-only twin-track audit: next XPP frontier + D3D/XGRPH/AvSetDisplayMode.

Reads existing xboxrecomp cached xrefs and metadata plus original *local*
translated source. No XBE/game bytes or disassembly are generated or committed.
Never stages a function, patches display_calls, or starts an XDK build.
"""
import argparse
import bisect
import collections
import hashlib
import importlib.util
import json
import re
import zipfile
from pathlib import Path

EXPECTED_SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
XPP=(0x002D559B,0x002D5579,0x002D5574)
GRAPHICS=(0x002888A0,0x00288F80,0x00288B30,0x00289E20,
          0x0028A090,0x00288960,0x0029C13E)
DEFINITION=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?(?:__forceinline[ \t]+)?"
                      r"void[ \t]+sub_([0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)\s*\{")
HELPER=re.compile(r"\b(recomp_[A-Za-z0-9_]+)\s*\(")
DIRECT=re.compile(r"\bsub_([0-9A-Fa-f]{8})\s*\(")
STACK=re.compile(r"\besp\s*(?:\+=|-=|=)\s*[^;\n]+;")
PREFIX="NO_XDK_BUILD_NO_GUEST_PATCH_NO_FAKE_DISPLAY"


def va(v):
    return int(str(v),0)


def hx(v):
    return "0x%08X"%v


def enclosing(v,starts,functions):
    pos=bisect.bisect_right(starts,v)-1
    if pos<0:
        return None
    row=functions[starts[pos]]
    return row if v<va(row["end"]) else None


def original_loader(path):
    spec=importlib.util.spec_from_file_location("merc360_original_reader",str(path))
    if spec is None or spec.loader is None:
        raise ValueError("Original generated source reader not found")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_files(args):
    for field in ("recon","xrefs","ranges","generated","emitter","shards","host"):
        p=getattr(args,field)
        if not p.exists():
            raise ValueError("Missing locally saved analysis input: "+str(p))
    if len(list(args.shards.glob("translated_???.cpp")))!=64:
        raise ValueError("Expected exactly 64 post-XPP TrueTUs")


def inspect(args):
    check_files(args)
    with zipfile.ZipFile(args.recon) as z:
        inventory=json.loads(z.read("xboxrecomp_manifest.json"))
        summary=z.read("merc360_frontier_summary.txt").decode("utf-8-sig")
    if (inventory.get("functions")!=16662 or
        inventory.get("no_raw_game_bytes") is not True or
        EXPECTED_SHA not in summary):
        raise ValueError("Wrong XBE or incomplete xboxrecomp cache")
    funcs={va(f["address"]):f for f in inventory["function_list"]}
    starts=sorted(funcs)
    if len(funcs)!=16662:
        raise ValueError("Duplicate xboxrecomp function entries")
    compiled=set()
    for p in args.shards.glob("translated_???.cpp"):
        for match in DEFINITION.finditer(p.read_text(encoding="utf-8",errors="replace")):
            compiled.add(int(match.group(1),16))
    if len(compiled)<13000:
        raise ValueError("Incomplete compiled TrueTU inventory")
    reader=original_loader(args.emitter)
    _,by_name=reader.load_ranges(args.ranges)
    generated=reader.load_generated(args.generated,by_name)
    if len(generated)<10000:
        raise ValueError("Original translator code corpus incomplete")
    xrefs=json.loads(args.xrefs.read_text(encoding="utf-8-sig"))
    if not isinstance(xrefs,list) or len(xrefs)<100:
        raise ValueError("Saved xboxrecomp xrefs.json missing or too small")
    calls=collections.defaultdict(set)
    imports=collections.defaultdict(list)
    for x in xrefs:
        try:
            frm,to=va(x["from"]),va(x["to"])
        except (KeyError,ValueError,TypeError):
            continue
        if x.get("type")=="call":
            calls[to].add(frm)
        if x.get("type")=="kernel_call":
            imports[str(x.get("kernel_name","")).lower()].append((frm,to))
    targets=[]
    excerpt=["LOCAL ONLY: original generated XPP source from YOUR retail XBE",
             "DO NOT COMMIT THIS FILE OR SEND ORIGINAL GAME BYTES TO GITHUB",""]
    for group,address_list in (("XPP_HARDWARE",XPP),("GRAPHICS_PREDICTIVE",GRAPHICS)):
        for address in address_list:
            meta=funcs.get(address,{})
            original=generated.get(address)
            raw=original["source"] if original else ""
            masked=reader.mask_noncode(raw)
            incoming=sorted(calls.get(address,set()))
            inbound_compiled=[]
            for from_insn in incoming:
                owner=enclosing(from_insn,starts,funcs)
                if owner and va(owner["address"]) in compiled:
                    inbound_compiled.append(from_insn)
            helpers=sorted(set(HELPER.findall(masked)))
            children=sorted(set(int(n,16) for n in DIRECT.findall(masked))
                            -{address})
            record={
                "group":group,
                "address":hx(address),
                "section":meta.get("section","UNKNOWN"),
                "size":meta.get("size"),
                "num_instructions":meta.get("instructions"),
                "disasm_confidence":meta.get("confidence"),
                "compiled_in_latest_true_tus":address in compiled,
                "original_source_present":original is not None,
                "original_source_file":original["file"] if original else None,
                "original_source_sha256":hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else None,
                "exact_entry_label":bool(re.search(r"\bloc_%08X\s*:"%address,raw)),
                "source_trace":("RECOMP_TRACE_FUNC(0x%08Xu)"%address) in raw,
                "guest_stack_statements":STACK.findall(masked)[:12],
                "original_host_helpers":helpers,
                "original_direct_children":[hx(c) for c in children],
                "uncompiled_direct_children":[hx(c) for c in children if c not in compiled],
                "static_direct_callsites":len(incoming),
                "compiled_inbound_callsites":[hx(c) for c in inbound_compiled[:80]],
                "manifest_called_by":[hx(va(c)) for c in meta.get("called_by",[])[:80]],
            }
            targets.append(record)
            if group=="XPP_HARDWARE":
                excerpt.extend([
                    "== %s / %s / sha256=%s =="%(hx(address),
                        original["file"] if original else "NO GENERATED BODY",
                        record["original_source_sha256"]),
                    raw if raw else "MISSING ORIGINAL GENERATED BODY",""])
    av=[]
    for key, entries in imports.items():
        if key=="avsetdisplaymode":
            for frm,thunk in entries:
                owner=enclosing(frm,starts,funcs)
                parent_va=va(owner["address"]) if owner else None
                av.append({
                    "callsite":hx(frm),"kernel_thunk":hx(thunk),
                    "containing_function":hx(parent_va) if parent_va is not None else None,
                    "section":owner.get("section") if owner else None,
                    "caller_compiled":parent_va in compiled if parent_va is not None else False,
                })
    av=sorted(av,key=lambda x:x["callsite"])
    return {
        "status":PREFIX,
        "latest_hardware":{
            "previous_ticks":27107567,"new_ticks":27107590,"gain":23,
            "xinput_d5574_executed":True,"controller_mask":"0x00000001",
            "observed_next_direct_frontier":hx(0x002D559B),
            "display_calls":0,"framebuffer":"0x00000000","av_set_calls":0},
        "source":{"functions":len(funcs),"compiled_true_tu_bodies":len(compiled),
                  "translator_bodies":len(generated),"xrefs":len(xrefs),
                  "source_bytes_committed":False},
        "target_audits":targets,
        "av_set_display_mode":{
            "saved_exact_kernel_thunk_callsite_count":len(av),
            "callsites":av,
            "other_named_av_kernel_import_xrefs":{
                k:len(v) for k,v in imports.items()
                if k.startswith("av") and k!="avsetdisplaymode"},
            "limitation":("An absent named xref does not prove AvSetDisplayMode "
                          "is unreachable: indirect/function-pointer calls may be missed.")
        }
    }, "\n".join(excerpt)


def report_lines(state):
    s=state["source"]
    h=state["latest_hardware"]
    out=["[DISPLAY-RECON] TWO-TRACK OFFLINE SOURCE AUDIT",
         "Hardware ticks: %d -> %d (+%d)"%(h["previous_ticks"],h["new_ticks"],h["gain"]),
         "XPP D5574 PASS, connected controller mask=00000001",
         "NEXT HARDWARE FRONTIER: 0x002D559B (DIRECT, fault=0)",
         "AvSetDisplayMode=0, guest display_calls=0, framebuffer=00000000",
         "Saved functions=%d, compiled bodies=%d, original bodies=%d, xrefs=%d"%
         (s["functions"],s["compiled_true_tu_bodies"],s["translator_bodies"],s["xrefs"]),""]

    for f in state["target_audits"]:
        if f["address"]=="0x002888A0":
            out.extend(["","[DISPLAY-RECON] GRAPHICS TARGETS"])
        out.append("%s [%s] size=%s compiled=%s generated=%s inbound_compiled=%d"%
                   (f["address"],f["section"],f["size"],f["compiled_in_latest_true_tus"],
                    f["original_source_present"],len(f["compiled_inbound_callsites"])))
        out.append("  helpers="+",".join(f["original_host_helpers"]))
        out.append("  guest_stack="+str(f["guest_stack_statements"]))
        out.append("  missing_direct_children="+",".join(f["uncompiled_direct_children"][:15]))
        out.append("  source_sha256="+str(f["original_source_sha256"]))
    av=state["av_set_display_mode"]
    out.extend(["","[DISPLAY-RECON] AvSetDisplayMode KERNEL THUNK CALLERS",
                "Verified exact-name kernel xrefs: %d"%av["saved_exact_kernel_thunk_callsite_count"]])
    for x in av["callsites"][:80]:
        out.append("  callsite=%s thunk=%s owner=%s section=%s compiled=%s"%
                   (x["callsite"],x["kernel_thunk"],x["containing_function"],
                    x["section"],x["caller_compiled"]))
    out.append("Other AV kernel xrefs: "+str(av["other_named_av_kernel_import_xrefs"]))
    out.extend([av["limitation"],"NO XDK BUILD. NO BYPASSED VP/MMIO. NO FAKE PIXELS."])
    return "\n".join(out)+"\n"


def self_test():
    data={0x10:{"address":"0x00000010","end":"0x00000020"},
          0x20:{"address":"0x00000020","end":"0x00000030"}}
    assert enclosing(0x1F,[0x10,0x20],data)==data[0x10]
    assert enclosing(0x30,[0x10,0x20],data) is None
    assert STACK.findall("esp += 12u;") == ["esp += 12u;"]
    assert DIRECT.findall("sub_002D559B();")==["002D559B"]
    assert HELPER.findall("recomp_xinput_get_device_changes();")==[
        "recomp_xinput_get_device_changes"]
    assert len(GRAPHICS)==7 and len(XPP)==3
    print("[DISPLAY-RECON] SYNTHETIC PASS: function owners, helper calls, stack signatures")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for name in ("recon","xrefs","ranges","generated","emitter","shards","host","out","excerpts"):
        p.add_argument("--"+name,type=Path)
    a=p.parse_args()
    if a.self_test:
        self_test()
        return
    for name in ("recon","xrefs","ranges","generated","emitter","shards","host","out","excerpts"):
        if getattr(a,name) is None:
            p.error("--"+name+" is required unless --self-test")
    if a.out.resolve()==a.excerpts.resolve():
        raise ValueError("Audit and original source excerpts must not overwrite each other")
    state,excerpts=inspect(a)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.excerpts.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(report_lines(state)+"\nFULL METADATA JSON:\n"+
                     json.dumps(state,indent=2)+"\n",encoding="utf-8")
    a.excerpts.write_text(excerpts,encoding="utf-8")
    print("[DISPLAY-RECON] XPP D559B + seven graphics targets audited")
    print("[DISPLAY-RECON] AvSetDisplayMode named kernel callsites=%d"%
          state["av_set_display_mode"]["saved_exact_kernel_thunk_callsite_count"])
    print("[DISPLAY-RECON] Cached xrefs only; no disassembly, XDK or Xbox run")
    print("[DISPLAY-RECON] SUMMARY: "+str(a.out))
    print("[DISPLAY-RECON] LOCAL-ONLY XPP SOURCE: "+str(a.excerpts))


if __name__=="__main__":
    main()
