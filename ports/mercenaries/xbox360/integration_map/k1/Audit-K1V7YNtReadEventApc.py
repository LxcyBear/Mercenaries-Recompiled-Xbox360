#!/usr/bin/env python3
"""K1-V7Y: source-only NtReadFile callback ABI investigation, no patch or Xbox.

Verify both 62M-compatible parent candidates, find the exact rejection and
kernel frame guards in source, and report stack reads and control-flow context.
Never assume 44-byte frame is compatible with existing 36-byte path.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path

NEEDLE="STORAGE IO UNSUPPORTED: NtReadFile Event/APC callback form"
SYMBOL="phase5h_nt_read_file"
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
def digest(b):return hashlib.sha256(b).hexdigest()
def need(test,msg):
    if not test:raise ValueError(msg)
def line_context(lines,line,radius=36):
    lo=max(0,line-radius); hi=min(len(lines),line+radius+1)
    return "\n".join("%6d: %s"%(i+1,lines[i]) for i in range(lo,hi))
def braces(text,begin):
    pos=text.find("{",begin)
    need(pos!=-1,"Missing opening brace")
    depth=0
    # C++ source may have braces in strings but this is used only on a
    # uniquely found function body; matching top-level at column zero
    # prevents premature exits on deeply nested blocks.
    line_start=text.rfind("\n",0,pos)+1
    matches=list(re.finditer(r"(?m)^}\s*$",text[pos:]))
    need(bool(matches),"No top-level closing brace")
    return text[begin:pos+matches[0].end()]
def inspect(path,manifest_path):
    raw=path.read_bytes()
    manifest=json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    need(manifest.get("source_sha256")==digest(raw),
         "Source SHA mismatch for "+str(path))
    need(manifest.get("retail_original_xbe_sha256",RETAIL)==RETAIL,
         "Retail XBE identity mismatch")
    need(len(manifest.get("true_tu_sha256",{}))==64,"64 TrueTU manifest absent")
    text=raw.decode("utf-8").replace("\r\n","\n")
    lines=text.splitlines()
    string_hits=[i for i,line in enumerate(lines) if NEEDLE in line]
    need(len(string_hits)==1,"Unsupported callback branch absent/duplicated: "+str(path))
    guard_hits=[i for i,line in enumerate(lines)
                if "savedEsp != callEsp + 36u" in line]
    func=re.search(r"(?m)^(?:static\s+)?void\s+"+SYMBOL+r"\s*\(\s*uint32_t\s+savedEsp\s*\)\s*\{",text)
    need(func is not None,"Native NtReadFile handler unique owner missing")
    # Allow one owner with declaration earlier, reject duplicate definitions.
    need(len(re.findall(r"(?m)^(?:static\s+)?void\s+"+SYMBOL+
                        r"\s*\(\s*uint32_t\s+savedEsp\s*\)\s*\{",text))==1,
         "Duplicate NtReadFile function owners")
    fbody=braces(text,func.start())
    need(NEEDLE in fbody,"Callback reject not inside native NtReadFile handler")
    need("phase4c_escape" in fbody,"Native NtReadFile escape fence absent")
    need("ReadFile(" in fbody,"Native NtReadFile read path absent")
    # Extract guest stack offsets only for source review, not interpretation.
    reads=sorted({int(x) for x in re.findall(
        r"\bGUEST_READ32\s*\(\s*callEsp\s*\+\s*(\d+)u?\s*\)",fbody)})
    fields=sorted({x for x in re.findall(r"\b(?:event|apc|completion|context|iosb|callEsp|savedEsp)\w*\b",fbody,re.I)})
    return {"path":str(path),"sha256":digest(raw),
            "manifest_stage":manifest.get("stage",""),
            "fingerprints":[m.group(0) for m in re.finditer(
                r"K1-V7[XUV]-[A-Z0-9-]+20261106",text)][:8],
            "callback_rejection_line":string_hits[0]+1,
            "frame_guard_lines":[i+1 for i in guard_hits],
            "stack_read_offsets":reads,"interesting_identifiers":fields,
            "function_excerpt":fbody,
            "rejection_excerpt":line_context(lines,string_hits[0],54),
            "guard_excerpt":"\n\n".join(line_context(lines,i,25) for i in guard_hits[:2])}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v7i",required=True,type=Path)
    p.add_argument("--v7i-manifest",required=True,type=Path)
    p.add_argument("--v7x",required=True,type=Path)
    p.add_argument("--v7x-manifest",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    i=inspect(a.v7i,a.v7i_manifest)
    x=inspect(a.v7x,a.v7x_manifest)
    need(i["stack_read_offsets"]==x["stack_read_offsets"],
         "V7I/V7X NtReadFile stack accesses differ")
    need(i["function_excerpt"]==x["function_excerpt"],
         "V7I/V7X native NtReadFile handler differs")
    need(i["frame_guard_lines"],"Canonical 36-byte frame fence not present")
    need(i["callback_rejection_line"]>0,"Callback rejection missing")
    report={
        "stage":"V7Y_NTREAD_EVENT_APC_SOURCE_ONLY_AUDIT",
        "retail_xbe_sha256":RETAIL,
        "v7i_sha256":i["sha256"],"v7x_sha256":x["sha256"],
        "v7i_stage":i["manifest_stage"],"v7x_stage":x["manifest_stage"],
        "source_handlers_identical":True,
        "canonical_36_byte_frame_guard_lines":i["frame_guard_lines"],
        "callback_rejection_line":i["callback_rejection_line"],
        "callEsp_read_offsets":i["stack_read_offsets"],
        "interesting_identifiers":i["interesting_identifiers"],
        "hardware_xex_identity_proven":False,
        "44_byte_frame_corrected":False,
        "apc_event_callback_supported":False,
        "next":"Review local excerpt and retail call-site semantics before adding any real Event/APC support."}
    data=json.dumps(report,indent=2)+"\n\n=== NATIVE NTREADFILE OWNER ===\n"+i["function_excerpt"]+
    "\n\n=== CALLBACK REJECTION CONTEXT ===\n"+i["rejection_excerpt"]+
    "\n\n=== ORIGINAL FRAME GUARD CONTEXT ===\n"+i["guard_excerpt"]+"\n"
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(data,encoding="utf-8")
    print("[K1-V7Y] SOURCE PASS: V7I/V7X identical native NtReadFile handler")
    print("[K1-V7Y] rejection_line=%d frame_guards=%s callEsp_offsets=%s"%
          (i["callback_rejection_line"],i["frame_guard_lines"],i["stack_read_offsets"]))
    print("[K1-V7Y] Local forensic owner/context: "+str(a.output))
    print("[K1-V7Y] NO ABI BODGE / NO XDK / NO XBOX / NO FILE READ PERFORMED")
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("[K1-V7Y] HARD FENCE "+str(exc),file=sys.stderr);sys.exit(1)
