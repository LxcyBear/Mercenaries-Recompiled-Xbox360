#!/usr/bin/env python3
"""
Phase 3J: select the first bounded dependency-closed real Mercenaries cluster.

Unlike Phase 3I, the root and members are not hand-picked. The selector starts
from real retail function metadata, recursively follows every statically named
translated C call (ordinary CALL, tail JMP, and external conditional transfer),
and only accepts a root when the entire reachable translated cluster closes
inside a small, auditable set.

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


MIN_CLUSTER = 4
MAX_CLUSTER = 8
MIN_DEPTH = 2
MAX_TOTAL_BYTES = 1400
MAX_TOTAL_INSNS = 360
MAX_FUNC_BYTES = 320
MAX_FUNC_INSNS = 96
MAX_ROOTS = 2200

# Do not "discover" the already hand-selected Phase 3E-I fixtures again.
PREVIOUSLY_PROVEN = {
    0x00208F30,
    0x001EF850,
    0x0021AB90,
    0x00050010,
    0x0004CFF0,
    0x0008DE60,
}

FUNC_DEF_RE = re.compile(
    r"\bvoid\s+(sub_[0-9A-Fa-f]{8})\s*\(\s*void\s*\)")
SUB_CALL_RE = re.compile(r"\b(sub_([0-9A-Fa-f]{8}))\s*\(\s*\)")
RET_N_RE = re.compile(r"/\*\s*ret\s+\d+\s*\*/", re.IGNORECASE)
PLAIN_RET_RE = re.compile(r"/\*\s*ret\s*\*/", re.IGNORECASE)

CALL_TOKEN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")

FORBIDDEN_SOURCE_RE = re.compile(
    r"\b(?:"
    r"RECOMP_ICALL|RECOMP_ITAIL|"
    r"recomp_xmm_[A-Za-z0-9_]+|"
    r"xmm[0-7]|xmm[0-7]v|g_xmm[0-7]|"
    r"mm[0-7]|g_mm[0-7]|"
    r"fp_push|fp_pop|fp_popp|fp_top|fp_st|fp_st1|"
    r"g_fp_stack|g_fp_top|"
    r"GUEST_READF32|GUEST_READF64|GUEST_WRITEF32|GUEST_WRITEF64|"
    r"XBOX_MEMCPY|XBOX_REP_MOVS|"
    r"RECOMP_RDTSC|__debugbreak|"
    r"xbox_[A-Za-z0-9_]+"
    r")\b"
)

# The first 3J cluster is about dependency closure/scale, not loops. Branching
# flag coverage widens in 3K. Keeping 3J-A acyclic and branch-light guarantees
# that its static dependency chain is actually exercised by deterministic seed.
FORBIDDEN_CONTROL_RE = re.compile(
    r"\b(?:while|for)\s*\(|\bgoto\s+loc_|\bif\s*\("
)

C_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

ALLOWED_CALLS = {
    "RECOMP_TRACE_FUNC",
    "GUEST_READ8", "GUEST_READ16", "GUEST_READ32", "GUEST_READ64",
    "GUEST_SREAD8", "GUEST_SREAD16", "GUEST_SREAD32", "GUEST_SREAD64",
    "GUEST_WRITE8", "GUEST_WRITE16", "GUEST_WRITE32", "GUEST_WRITE64",
    "RECOMP_READ8", "RECOMP_READ16", "RECOMP_READ32", "RECOMP_READ64",
    "RECOMP_WRITE8", "RECOMP_WRITE16", "RECOMP_WRITE32", "RECOMP_WRITE64",
    "PUSH32", "POP32",
    "LO8", "HI8", "LO16", "SET_LO8", "SET_HI8", "SET_LO16",
    "SX8", "SX16", "ZX8", "ZX16", "BSWAP32",
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


def source_surface_ok(source, own_name, dependency_names):
    executable = executable_c(source)

    if FORBIDDEN_SOURCE_RE.search(executable):
        return False, "unsupported dynamic/SIMD/FPU/runtime surface"

    if FORBIDDEN_CONTROL_RE.search(executable):
        return False, "branch/loop control flow deferred to Phase 3K"

    defs = FUNC_DEF_RE.findall(executable)
    if defs != [own_name]:
        return False, "function signature is not one exact void sub_XXXXXXXX(void)"

    if RET_N_RE.search(source):
        return False, "ret-N member deferred from first closed cluster"

    if not PLAIN_RET_RE.search(source):
        return False, "no plain translated RET"

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
                return None, "cluster reuses prior hand-selected Phase 3E-I function"

            size = int_field(info, "size")
            insns = int_field(info, "num_instructions", 999999)
            if size <= 0 or size > MAX_FUNC_BYTES:
                return None, "member size outside first-cluster bound"
            if insns <= 0 or insns > MAX_FUNC_INSNS:
                return None, "member instruction count outside first-cluster bound"

            source = lift(addr)
            if not source:
                return None, "member translation failed"

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

        # The root must return normally to the harness.
        root_source = lift(root)
        if len(PLAIN_RET_RE.findall(root_source)) != 1:
            return None, "root must have exactly one plain RET"

        return {
            "root": root,
            "closure": closure,
            "graph": graph,
            "depth": depth,
            "order": order,
            "total_bytes": total_bytes,
            "total_insns": total_insns,
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
        print("[Phase3J] NO BOUNDED DEPENDENCY-CLOSED CLUSTER FOUND")
        print(f"[Phase3J] Candidate roots considered: {min(len(roots), MAX_ROOTS)}")
        for reason, count in rejects.most_common(16):
            print(f"[Phase3J] reject {count:4d}: {reason}")
        if reject_details:
            print("[Phase3J] First root rejection details:")
            for addr, reason in reject_details:
                print(f"[Phase3J]   0x{addr:08X}: {reason}")
        raise SystemExit(2)

    # Prefer the largest closure, then deepest graph, then smallest code budget.
    candidates.sort(key=lambda c: (
        -len(c["closure"]),
        -c["depth"],
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
        source = lift(addr)

        # Definitions are made static locally; generated semantics are untouched.
        static_source, count = re.subn(
            rf"\bvoid\s+{re.escape(name)}\s*\(\s*void\s*\)",
            f"static void {name}(void)",
            source,
            count=1,
        )
        if count != 1:
            raise SystemExit(
                f"[Phase3J] could not localize function definition {name}")

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
        "generated_files": generated_files,
    }
    (out_dir / "selection.json").write_text(
        json.dumps(selection, indent=2) + "\n",
        encoding="utf-8")

    template = Path(args.template).read_text(encoding="utf-8")
    replacements = {
        "/*__P3J_FORWARD_DECLS__*/": forward_decls,
        "/*__P3J_CLUSTER_BODIES__*/": cluster_source,
        "__P3J_ROOT_NAME__": funcs[root]["name"],
        "__P3J_ROOT_VA__": f"0x{root:08X}u",
        "__P3J_MEMBER_COUNT__": str(len(chosen["closure"])),
        "__P3J_DEPTH__": str(chosen["depth"]),
        "/*__P3J_MEMBER_VAS__*/": ", ".join(
            f"0x{a:08X}u" for a in sorted(chosen["closure"])),
    }

    for token, value in replacements.items():
        if token not in template:
            raise SystemExit(f"[Phase3J] template token missing: {token}")
        template = template.replace(token, value)

    Path(args.main_out).write_text(template, encoding="utf-8")

    print("[Phase3J] SELECTED DEPENDENCY-CLOSED CLUSTER")
    print(f"[Phase3J] Root: {funcs[root]['name']} @ 0x{root:08X}")
    print(
        f"[Phase3J] Members: {len(chosen['closure'])}, "
        f"depth={chosen['depth']}, "
        f"bytes={chosen['total_bytes']}, "
        f"insns={chosen['total_insns']}")
    print("[Phase3J] Static edges:")
    for edge in edges:
        print(f"[Phase3J]   {edge['from']} -> {edge['to']}")
    print("[Phase3J] Dependency-first compile order:")
    for addr in order:
        print(f"[Phase3J]   0x{addr:08X} {funcs[addr]['name']}")
    print(f"[Phase3J] XDK source: {args.main_out}")


if __name__ == "__main__":
    main()
