#!/usr/bin/env python3
"""No-retail-source XPP D559B synthetic safety checks; no XDK or console."""
import importlib.util
from pathlib import Path

p=Path(__file__).with_name("Stage-XppD559B.py")
spec=importlib.util.spec_from_file_location("xpp_d559b",p)
assert spec and spec.loader
x=importlib.util.module_from_spec(spec)
spec.loader.exec_module(x)

def refuses(fn,*a,**kw):
    try:
        fn(*a,**kw)
    except ValueError:
        return
    raise AssertionError("Safety guard did not refuse invalid source")

def main():
    assert x.ROOT==0x002D559B and x.SECOND==0x002D5579
    assert len(x.SOURCE_SHA)==2
    assert "XInputGetState(port,&state)==ERROR_SUCCESS" in x.NATIVE
    assert "xpp_native_previous_device_mask=current" in x.NATIVE
    assert "current & ~previous" in x.NATIVE
    assert "previous & ~current" in x.NATIVE
    assert "GUEST_WRITE32(insertions_address,inserted)" in x.NATIVE
    assert "GUEST_WRITE32(removals_address,removed)" in x.NATIVE
    assert "insertions_address>=0x00010000u" in x.NATIVE
    assert "removals_address<=0x03FFFFFCu" in x.NATIVE
    assert "(inserted|removed)!=0u" in x.NATIVE
    assert "recomp_xinput_init_devices" not in x.NATIVE
    for nl in ("\n","\r\n"):
        sample=x.HEADER+nl+"void caller(void)"+nl+"{"+nl+(
            "phase4c_direct_frontier(0x002D559Bu);"+nl+
            "phase4c_direct_frontier(0x002D5579u);"+nl)+"}"+nl
        changed,counts=x.rewrite(sample,x.VAs)
        assert counts=={"0x002D559B":1,"0x002D5579":1}
        assert changed.count("sub_002D559B();")==1
        assert changed.count("sub_002D5579();")==1
        assert changed.count("void sub_002D559B(void);")==1
        assert changed.count("void sub_002D5579(void);")==1
        assert "phase4c_direct_frontier" not in changed
        near=sample.replace("0x002D559Bu","0x002D5590u")
        no,counts=x.rewrite(near,(x.ROOT,))
        assert counts["0x002D559B"]==0 and "0x002D5590u" in no
        refuses(x.rewrite,sample.replace(x.HEADER,""),x.VAs)
        host=("P6DQ-R51-MM173-FRAME-20261029-A"+nl+
              "phase4c_direct_frontier(0x002D559Bu);"+nl)
        hosted,counts=x.rewrite(host,x.VAs,is_host=True)
        assert counts["0x002D559B"]==1
        assert hosted.startswith("void sub_002D559B(void);")
        assert "phase4c_direct_frontier(" not in hosted
    assert x.BRIDGE in x.NATIVE
    print("[XPP-D559B] SYNTHETIC PASS: real XInput scan, persisted mask, fenced guest output")
    print("[XPP-D559B] SYNTHETIC PASS: precise D559B/D5579 direct callsites, LF/CRLF and fail-closed")
    print("[XPP-D559B] NO RETAIL SOURCE, NO XDK BUILD, NO FAKE PIXELS")

if __name__=="__main__":
    main()
