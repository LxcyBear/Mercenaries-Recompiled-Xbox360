#!/usr/bin/env python3
"""
Phase 3L: select a bounded dependency-closed real Mercenaries cluster that combines
real conditional/flag + x87/XMM state with at least one ordinary backward
guest branch. Generated backedges are instrumented for proof and all guest
basic-block labels receive a hard execution-budget tick.

The root and members are not hand-picked. The selector starts from real retail
function metadata, recursively follows every statically named translated C call
(ordinary CALL, tail JMP, and external conditional transfer), and only accepts
a root when the entire reachable translated cluster closes inside a bounded,
auditable set.

Unlike Phase 3J, an accepted Phase 3L-A closure must also contain both:
  * real conditional/flag control flow
  * a supported x87 or XMM/SSE architectural-state surface.

Generated retail-derived C stays local under build/.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.recomp import config
from tools.recomp.lifter import configure_guest_memory_abi
from tools.recomp.translator import BatchTranslator


MIN_CLUSTER = 5
MAX_CLUSTER = 10
MIN_DEPTH = 2
MAX_TOTAL_BYTES = 2200
MAX_TOTAL_INSNS = 560
MAX_FUNC_BYTES = 480
MAX_FUNC_INSNS = 140
MAX_ROOTS = 2200

# Do not rediscover prior isolated/composite hardware fixtures or the Phase 3J
# dependency-closed cluster. Phase 3L must widen into new retail functions.
PREVIOUSLY_PROVEN = {
    0x00208F30,
    0x001EF850,
    0x0021AB90,
    0x00050010,
    0x0004CFF0,
    0x0008DE60,
    0x000AE4E0,
    0x000AE510,
    0x000AE540,
    0x000B14D0,
    0x000B2080,
    0x00209720,
    0x001F3400,
    0x0020F910,
    0x0020F920,
    0x0022F31D,
    0x0022F3F3,
    0x0022F49E,
    0x0022F561,
}

FUNC_DEF_RE = re.compile(
    r"\bvoid\s+(sub_[0-9A-Fa-f]{8})\s*\(\s*void\s*\)")
SUB_CALL_RE = re.compile(r"\b(sub_([0-9A-Fa-f]{8}))\s*\(\s*\)")
RET_N_RE = re.compile(r"/\*\s*ret\s+\d+\s*\*/", re.IGNORECASE)
PLAIN_RET_RE = re.compile(r"/\*\s*ret\s*\*/", re.IGNORECASE)

CALL_TOKEN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")

FORBIDDEN_SOURCE_RE = re.compile(
    r"\b(?:"
    r"RECOMP_ICALL(?:_SAFE)?|RECOMP_ITAIL(?:_SAFE)?|"
    r"mm[0-7]|g_mm[0-7]|"
    r"XBOX_MEMCPY|XBOX_REP_MOVS|"
    r"RECOMP_RDTSC|__debugbreak|"
    r"xbox_[A-Za-z0-9_]+|"
    r"x87_round_integral|sin|cos|atan2|log2|exp2|trunc|fmod"
    r")\b"
)

FP_SURFACE_RE = re.compile(
    r"\b(?:"
    r"fp_push|fp_pop|fp_popp|fp_top|fp_st|fp_st1|"
    r"g_fp_stack|g_fp_top|"
    r"GUEST_READF32|GUEST_READF64|GUEST_WRITEF32|GUEST_WRITEF64|"
    r"recomp_xmm_[A-Za-z0-9_]+|"
    r"xmm[0-7]|xmm[0-7]v|g_xmm[0-7]"
    r")\b"
)

FLAG_SURFACE_RE = re.compile(
    r"(?:\b_flags\b|\bif\s*\(|\bgoto\s+loc_|"
    r"\bCMP_[A-Z]+\s*\(|\bTEST_[A-Z]+\s*\()"
)


# Phase 3L-A intentionally composes wider flag + FP state without adding
# unbounded execution. Forward acyclic branch control remains allowed; backward
# guest edges/loops and dynamic dispatch remain deferred until this mixed-state
# closure is hardware-proven.
FORBIDDEN_CONTROL_RE = re.compile(
    r"\b(?:while|for|switch)\s*\("
)

C_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

ALLOWED_CALLS = {
    "if", "while", "for", "switch", "sizeof",
    "RECOMP_TRACE_FUNC",
    "GUEST_READ8", "GUEST_READ16", "GUEST_READ32", "GUEST_READ64",
    "GUEST_SREAD8", "GUEST_SREAD16", "GUEST_SREAD32", "GUEST_SREAD64",
    "GUEST_WRITE8", "GUEST_WRITE16", "GUEST_WRITE32", "GUEST_WRITE64",
    "RECOMP_READ8", "RECOMP_READ16", "RECOMP_READ32", "RECOMP_READ64",
    "RECOMP_WRITE8", "RECOMP_WRITE16", "RECOMP_WRITE32", "RECOMP_WRITE64",
    "PUSH32", "POP32",
    "LO8", "HI8", "LO16", "SET_LO8", "SET_HI8", "SET_LO16",
    "SX8", "SX16", "ZX8", "ZX16", "BSWAP32",
    "CMP_EQ", "CMP_NE", "CMP_B", "CMP_AE", "CMP_BE", "CMP_A",
    "CMP_L", "CMP_GE", "CMP_LE", "CMP_G",
    "TEST_Z", "TEST_NZ", "TEST_S", "EVEN_PARITY8",
    "GUEST_READF32", "GUEST_READF64", "GUEST_WRITEF32", "GUEST_WRITEF64",
    "recomp_xmm_load", "recomp_xmm_store", "recomp_xmm_copy",
    "recomp_xmm_zero", "recomp_xmm_loadss", "recomp_xmm_loadsd",
    "recomp_xmm_copysd", "recomp_xmm_storesd",
    "recomp_xmm_movlps_load", "recomp_xmm_movlps_store",
    "recomp_xmm_movhps_load", "recomp_xmm_movhps_store",
    "recomp_xmm_movlhps", "recomp_xmm_movhlps",
    "recomp_xmm_set_u32", "recomp_xmm_get_u32",
    "recomp_xmm_movq_copy", "recomp_xmm_movq_load",
    "recomp_xmm_minps", "recomp_xmm_maxps",
    "recomp_xmm_minps_mem", "recomp_xmm_maxps_mem",
    "recomp_xmm_bitwise", "recomp_xmm_bitwise_mem",
    "recomp_xmm_shufps", "recomp_xmm_shufps_mem",
    "recomp_xmm_unpcklps", "recomp_xmm_unpckhps",
    "recomp_xmm_unpcklps_mem", "recomp_xmm_unpckhps_mem",
    "recomp_xmm_unary_ps", "recomp_xmm_unary_ps_mem",
    "recomp_xmm_cmp_ps", "recomp_xmm_cmp_ps_mem",
    "recomp_xmm_movmskps",
    "RECOMP_XMM_BINARY_RR", "RECOMP_XMM_BINARY_RM",
    "fp_push", "fp_pop", "fp_popp", "fp_top", "fp_st", "fp_st1",
    "fabs", "sqrt", "sqrtf", "isnan",
}


def parse_addr(value):
    if isinstance(value, int):
        return value
    return int(value, 16)


def int_field(info, name, default=0):
    value = info.get(name, default)
    if isinstance(value, str):
        return int(value, 0)
    return int(value or 0)


def executable_c(source):
    """Strip generated C comments before semantic surface scanning."""
    return C_COMMENT_RE.sub(" ", source)


def static_dependencies(source, own_name):
    source = executable_c(source)
    deps = []
    seen = set()

    for match in SUB_CALL_RE.finditer(source):
        name = match.group(1)
        if name == own_name:
            continue
        addr = int(match.group(2), 16)
        if addr not in seen:
            deps.append(addr)
            seen.add(addr)

    return deps


def guest_backward_edges(translator, addr, info):
    """
    Return ordinary intra-function backward guest branches. LOOP/LOOPE/LOOPNE
    remain outside Phase 3L-A because their implicit counter semantics deserve a
    separate gate.
    """
    end = int_field(info, "end", addr + int_field(info, "size"))
    if end <= addr:
        end = addr + int_field(info, "size")

    try:
        raw = translator.translator._read_func_bytes(addr, end)
        instructions = translator.translator.disasm.disassemble_function(
            raw, addr, end)
    except Exception:
        return None, "guest control-flow disassembly failed"

    edges = []
    for insn in instructions:
        if insn.mnemonic in ("loop", "loope", "loopne"):
            return None, "LOOP/LOOPE/LOOPNE deferred from Phase 3L-A"

        if not insn.is_branch or insn.jump_target is None:
            continue

        target = int(insn.jump_target)
        if addr <= target < end and target <= insn.address:
            edges.append((int(insn.address), target))

    return edges, ""


LOC_RE = re.compile(r"^(\s*)loc_([0-9A-Fa-f]{8})\s*:\s*;\s*$")
GOTO_RE = re.compile(r"goto\s+loc_([0-9A-Fa-f]{8})\s*;")


def instrument_generated_control(source):
    """
    Add one execution-budget tick at every generated guest label and annotate
    backward gotos so the hardware harness can prove a real backedge executed.
    """
    out = []
    current_va = None

    for line in source.splitlines():
        match = LOC_RE.match(line)
        if match:
            current_va = int(match.group(2), 16)
            out.append(line)
            out.append(
                f"{match.group(1)}    RECOMP_BUDGET_TICK(0x{current_va:08X}u);")
            continue

        if current_va is not None and "goto loc_" in line:
            def repl(goto_match):
                target = int(goto_match.group(1), 16)
                original = goto_match.group(0)
                if target <= current_va:
                    return (
                        "{ RECOMP_TRACE_BACKEDGE("
                        f"0x{current_va:08X}u, 0x{target:08X}u); "
                        + original + " }")
                return original
            line = GOTO_RE.sub(repl, line)

        out.append(line)

    return "\n".join(out) + ("\n" if source.endswith("\n") else "")

def source_surface_ok(source, own_name, dependency_names):
    executable = executable_c(source)

    forbidden_match = FORBIDDEN_SOURCE_RE.search(executable)
    if forbidden_match:
        return False, (
            "unsupported dynamic/SIMD/FPU/runtime surface: " +
            forbidden_match.group(0)
        )

    if FORBIDDEN_CONTROL_RE.search(executable):
        return False, "generated C loop/switch surface deferred from Phase 3L-A"

    defs = FUNC_DEF_RE.findall(executable)
    if defs != [own_name]:
        return False, "function signature is not one exact void sub_XXXXXXXX(void)"

    # RET shape is intentionally encoded in generated comments by the lifter:
    #   esp += 4;     return; /* ret */
    #   esp += 4 + N; return; /* ret N */
    # Helper/control-flow scans use the comment-stripped source, but return
    # classification must inspect the raw generated source.
    ret_n_matches = list(RET_N_RE.finditer(source))
    plain_ret_matches = list(PLAIN_RET_RE.finditer(source))

    if not ret_n_matches and not plain_ret_matches:
        return False, "no translated RET"

    # Nested translated callees may use callee-cleanup RET-N. Phase 3F already
    # proved this behavior on modified Xbox 360 hardware. Keep the first
    # dependency-closed cluster bounded by rejecting unusually large cleanups.
    for match in ret_n_matches:
        imm_match = re.search(
            r"ret\s+(\d+)", match.group(0), re.IGNORECASE)
        if not imm_match:
            return False, "unparseable ret-N member"
        if int(imm_match.group(1), 10) > 64:
            return False, "ret-N cleanup exceeds Phase 3L-A bound"

    allowed = set(ALLOWED_CALLS)
    allowed.add(own_name)
    allowed.update(dependency_names)

    unknown = []
    for token in CALL_TOKEN_RE.findall(executable):
        if token not in allowed:
            unknown.append(token)

    if unknown:
        return False, "unknown helper(s): " + ", ".join(
            sorted(set(unknown))[:8])

    return True, ""


def source_features(source):
    executable = executable_c(source)
    return {
        "fp": bool(FP_SURFACE_RE.search(executable)),
        "flags": bool(FLAG_SURFACE_RE.search(executable)),
    }


def depth_from(root, graph):
    visiting = set()
    memo = {}

    def walk(node):
        if node in visiting:
            raise RuntimeError("cycle")
        if node in memo:
            return memo[node]

        visiting.add(node)
        children = graph.get(node, [])
        value = 0 if not children else 1 + max(walk(c) for c in children)
        visiting.remove(node)
        memo[node] = value
        return value

    return walk(root)


def topo_dependencies_first(root, graph):
    visiting = set()
    visited = set()
    order = []

    def visit(node):
        if node in visiting:
            raise RuntimeError("cycle")
        if node in visited:
            return

        visiting.add(node)
        for child in graph.get(node, []):
            visit(child)
        visiting.remove(node)
        visited.add(node)
        order.append(node)

    visit(root)
    return order


def main():
    # The lifter's translated RET identity is encoded in generated comments.
    # Keep this invariant executable so a future comment-stripping refactor
    # fails immediately instead of producing a misleading selector histogram.
    _ret_probe = "esp += 4; return; /* ret */"
    _retn_probe = "esp += 8; return; /* ret 4 */"
    if not PLAIN_RET_RE.search(_ret_probe):
        raise SystemExit("[Phase3L] internal error: plain RET classifier broken")
    if not RET_N_RE.search(_retn_probe):
        raise SystemExit("[Phase3L] internal error: RET-N classifier broken")
    if (PLAIN_RET_RE.search(executable_c(_ret_probe)) or
            RET_N_RE.search(executable_c(_retn_probe))):
        raise SystemExit(
            "[Phase3L] internal error: RET classifiers unexpectedly survive "
            "comment stripping")

    ap = argparse.ArgumentParser()
    ap.add_argument("--xbe", required=True)
    ap.add_argument("--disasm-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--main-out", required=True)
    args = ap.parse_args()

    xbe = os.path.abspath(args.xbe)
    disasm_dir = os.path.abspath(args.disasm_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    functions_path = os.path.join(disasm_dir, "functions.json")
    labels_path = os.path.join(disasm_dir, "labels.json")

    configure_guest_memory_abi(True)
    config.configure_from_xbe(xbe)

    translator = BatchTranslator(
        xbe_path=xbe,
        func_json_path=functions_path,
        labels_json_path=labels_path if os.path.isfile(labels_path) else None,
        identified_json_path=None,
        abi_json_path=None,
        output_dir=str(out_dir),
        discover_entry_splits=False,
    )

    funcs = translator.func_db
    lift_cache = {}
    dependency_cache = {}
    surface_cache = {}

    def lift(addr):
        if addr not in lift_cache:
            info = funcs.get(addr)
            if info is None:
                lift_cache[addr] = None
            else:
                try:
                    lift_cache[addr] = translator.translate_single(addr)
                except Exception:
                    lift_cache[addr] = None
        return lift_cache[addr]

    def dependencies(addr):
        if addr in dependency_cache:
            return dependency_cache[addr]

        source = lift(addr)
        info = funcs.get(addr)
        if source is None or info is None:
            dependency_cache[addr] = None
            return None

        own_name = info.get("name", f"sub_{addr:08X}")
        result = static_dependencies(source, own_name)
        dependency_cache[addr] = result
        return result

    def build_closure(root):
        graph = {}
        closure = set()
        backedge_map = {}
        queue = [root]

        while queue:
            addr = queue.pop()

            if addr in closure:
                continue

            if len(closure) >= MAX_CLUSTER:
                return None, "closure exceeds max member count"

            info = funcs.get(addr)
            if info is None:
                return None, f"missing dependency boundary 0x{addr:08X}"

            expected_name = f"sub_{addr:08X}"
            if info.get("name") != expected_name:
                return None, "named/non-anonymous dependency in cluster"

            if addr in PREVIOUSLY_PROVEN:
                return None, "cluster reuses a prior Phase 3E-J hardware-proven function"

            size = int_field(info, "size")
            insns = int_field(info, "num_instructions", 999999)
            if size <= 0 or size > MAX_FUNC_BYTES:
                return None, "member size outside Phase 3L-A bound"
            if insns <= 0 or insns > MAX_FUNC_INSNS:
                return None, "member instruction count outside Phase 3L-A bound"

            source = lift(addr)
            if not source:
                return None, "member translation failed"

            backedges, backedge_error = guest_backward_edges(
                translator, addr, info)
            if backedges is None:
                return None, backedge_error

            deps = dependencies(addr)
            if deps is None:
                return None, "member dependency scan failed"

            dep_names = []
            for dep in deps:
                dep_info = funcs.get(dep)
                if dep_info is None:
                    return None, f"static dependency 0x{dep:08X} missing"
                dep_names.append(dep_info.get("name", f"sub_{dep:08X}"))

            ok, why = source_surface_ok(
                source, expected_name, dep_names)
            if not ok:
                return None, why

            closure.add(addr)
            graph[addr] = list(deps)
            backedge_map[addr] = list(backedges)

            for dep in deps:
                if dep not in closure:
                    queue.append(dep)

        try:
            depth = depth_from(root, graph)
            order = topo_dependencies_first(root, graph)
        except RuntimeError:
            return None, "recursive/cyclic translated dependency graph"

        total_bytes = sum(int_field(funcs[a], "size") for a in closure)
        total_insns = sum(
            int_field(funcs[a], "num_instructions") for a in closure)

        if len(closure) < MIN_CLUSTER:
            return None, "closure too small"
        if depth < MIN_DEPTH:
            return None, "dependency depth too shallow"
        if total_bytes > MAX_TOTAL_BYTES:
            return None, "closure byte budget exceeded"
        if total_insns > MAX_TOTAL_INSNS:
            return None, "closure instruction budget exceeded"

        feature_rows = {
            addr: source_features(lift(addr))
            for addr in closure
        }
        fp_members = sorted(
            addr for addr, features in feature_rows.items()
            if features["fp"])
        flag_members = sorted(
            addr for addr, features in feature_rows.items()
            if features["flags"])

        if not fp_members:
            return None, "closure lacks required x87/XMM/SSE surface"
        if not flag_members:
            return None, "closure lacks required conditional/flag surface"

        backedge_members = sorted(
            addr for addr, edges in backedge_map.items() if edges)
        if not backedge_members:
            return None, "closure lacks required backward guest edge"

        # The root must return normally to the harness with exactly one
        # ordinary return slot. Nested dependencies may use bounded RET-N, but
        # the root remains plain-RET so final ESP has one exact expectation.
        root_source = lift(root)
        if (len(PLAIN_RET_RE.findall(root_source)) != 1 or
                RET_N_RE.search(root_source)):
            return None, "root must have exactly one plain RET and no RET-N"

        return {
            "root": root,
            "closure": closure,
            "graph": graph,
            "depth": depth,
            "order": order,
            "total_bytes": total_bytes,
            "total_insns": total_insns,
            "fp_members": fp_members,
            "flag_members": flag_members,
            "backedge_members": backedge_members,
            "backedge_map": backedge_map,
        }, ""

    candidates = []
    rejects = Counter()
    reject_details = []

    roots = []
    for addr, info in funcs.items():
        if addr in PREVIOUSLY_PROVEN:
            continue

        if info.get("name") != f"sub_{addr:08X}":
            continue

        size = int_field(info, "size")
        insns = int_field(info, "num_instructions", 999999)
        calls_to = info.get("calls_to", [])

        if not calls_to:
            continue
        if size <= 0 or size > MAX_FUNC_BYTES:
            continue
        if insns <= 0 or insns > MAX_FUNC_INSNS:
            continue

        roots.append(addr)

    roots.sort(key=lambda a: (
        -len(funcs[a].get("calls_to", [])),
        int_field(funcs[a], "size"),
        a,
    ))

    for root in roots[:MAX_ROOTS]:
        result, why = build_closure(root)
        if not result:
            rejects[why] += 1
            if len(reject_details) < 40:
                reject_details.append((root, why))
            continue

        candidates.append(result)

    if not candidates:
        print("[Phase3L] NO BOUNDED DEPENDENCY-CLOSED CLUSTER FOUND")
        print(f"[Phase3L] Candidate roots considered: {min(len(roots), MAX_ROOTS)}")
        for reason, count in rejects.most_common(16):
            print(f"[Phase3L] reject {count:4d}: {reason}")
        if reject_details:
            print("[Phase3L] First root rejection details:")
            for addr, reason in reject_details:
                print(f"[Phase3L]   0x{addr:08X}: {reason}")
        raise SystemExit(2)

    # Prefer the largest closure, then deepest graph, then smallest code budget.
    candidates.sort(key=lambda c: (
        -len(c["closure"]),
        -c["depth"],
        -len(c["fp_members"]),
        -len(c["flag_members"]),
        -len(c["backedge_members"]),
        c["total_bytes"],
        c["total_insns"],
        c["root"],
    ))
    chosen = candidates[0]

    root = chosen["root"]
    order = chosen["order"]
    graph = chosen["graph"]

    forward_decls = "\n".join(
        f"static void {funcs[a]['name']}(void);" for a in sorted(chosen["closure"])
    )

    bodies = []
    generated_files = []
    for addr in order:
        name = funcs[addr]["name"]
        source = instrument_generated_control(lift(addr))

        # Definitions are made static locally; guest semantics are untouched
        # except for Phase 3L safety/proof instrumentation.
        static_source, count = re.subn(
            rf"\bvoid\s+{re.escape(name)}\s*\(\s*void\s*\)",
            f"static void {name}(void)",
            source,
            count=1,
        )
        if count != 1:
            raise SystemExit(
                f"[Phase3L] could not localize function definition {name}")

        filename = f"{name}.c"
        (out_dir / filename).write_text(
            static_source + "\n", encoding="utf-8")
        generated_files.append(filename)
        bodies.append(static_source)

    cluster_source = "\n\n".join(bodies)

    edges = []
    for src in sorted(chosen["closure"]):
        for dst in graph.get(src, []):
            edges.append({
                "from": f"0x{src:08X}",
                "to": f"0x{dst:08X}",
            })

    selection = {
        "root": f"0x{root:08X}",
        "root_name": funcs[root]["name"],
        "members": [f"0x{a:08X}" for a in sorted(chosen["closure"])],
        "member_names": [funcs[a]["name"] for a in sorted(chosen["closure"])],
        "dependency_order": [f"0x{a:08X}" for a in order],
        "edges": edges,
        "member_count": len(chosen["closure"]),
        "depth": chosen["depth"],
        "total_bytes": chosen["total_bytes"],
        "total_instructions": chosen["total_insns"],
        "fp_members": [f"0x{a:08X}" for a in chosen["fp_members"]],
        "flag_members": [f"0x{a:08X}" for a in chosen["flag_members"]],
        "backedge_members": [
            f"0x{a:08X}" for a in chosen["backedge_members"]],
        "backedges": [
            {
                "member": f"0x{member:08X}",
                "from": f"0x{src:08X}",
                "to": f"0x{dst:08X}",
            }
            for member in sorted(chosen["backedge_map"])
            for src, dst in chosen["backedge_map"][member]
        ],
        "generated_files": generated_files,
    }
    (out_dir / "selection.json").write_text(
        json.dumps(selection, indent=2) + "\n",
        encoding="utf-8")

    template = Path(args.template).read_text(encoding="utf-8")
    replacements = {
        "/*__P3L_FORWARD_DECLS__*/": forward_decls,
        "/*__P3L_CLUSTER_BODIES__*/": cluster_source,
        "__P3L_ROOT_NAME__": funcs[root]["name"],
        "__P3L_ROOT_VA__": f"0x{root:08X}u",
        "__P3L_MEMBER_COUNT__": str(len(chosen["closure"])),
        "__P3L_DEPTH__": str(chosen["depth"]),
        "/*__P3L_MEMBER_VAS__*/": ", ".join(
            f"0x{a:08X}u" for a in sorted(chosen["closure"])),
    }

    for token, value in replacements.items():
        if token not in template:
            raise SystemExit(f"[Phase3L] template token missing: {token}")
        template = template.replace(token, value)

    Path(args.main_out).write_text(template, encoding="utf-8")

    print("[Phase3L] SELECTED DEPENDENCY-CLOSED CLUSTER")
    print(f"[Phase3L] Root: {funcs[root]['name']} @ 0x{root:08X}")
    print(
        f"[Phase3L] Members: {len(chosen['closure'])}, "
        f"depth={chosen['depth']}, "
        f"bytes={chosen['total_bytes']}, "
        f"insns={chosen['total_insns']}")
    print(
        "[Phase3L] Wider surfaces: "
        f"fp_members={len(chosen['fp_members'])}, "
        f"flag_members={len(chosen['flag_members'])}")
    print("[Phase3L] FP/XMM members:")
    for addr in chosen["fp_members"]:
        print(f"[Phase3L]   0x{addr:08X} {funcs[addr]['name']}")
    print("[Phase3L] Conditional/flag members:")
    for addr in chosen["flag_members"]:
        print(f"[Phase3L]   0x{addr:08X} {funcs[addr]['name']}")
    print("[Phase3L] Backward-edge members:")
    for addr in chosen["backedge_members"]:
        print(f"[Phase3L]   0x{addr:08X} {funcs[addr]['name']}")
        for src, dst in chosen["backedge_map"][addr]:
            print(f"[Phase3L]     0x{src:08X} -> 0x{dst:08X}")
    print("[Phase3L] Static edges:")
    for edge in edges:
        print(f"[Phase3L]   {edge['from']} -> {edge['to']}")
    print("[Phase3L] Dependency-first compile order:")
    for addr in order:
        print(f"[Phase3L]   0x{addr:08X} {funcs[addr]['name']}")
    print(f"[Phase3L] XDK source: {args.main_out}")


if __name__ == "__main__":
    main()
