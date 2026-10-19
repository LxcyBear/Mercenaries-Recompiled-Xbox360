"""Pin Phase 4B-C2 memory/protection imports to guest-owned semantics."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def function_body(text: str, name: str) -> str:
    match = re.search(
        r"\b" + re.escape(name) + r"\s*\([^;]*?\)\s*\{",
        text,
        re.S,
    )
    if not match:
        raise AssertionError(f"missing function {name}")
    start = text.index("{", match.start())
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"unterminated function {name}")


class Phase4BMemoryOwnershipTests(unittest.TestCase):
    def test_virtual_allocation_is_page_backed(self):
        bridge = (ROOT / "src/kernel/kernel_bridge.c").read_text(encoding="utf-8")
        body = function_body(bridge, "bridge_NtAllocateVirtualMemory")
        self.assertIn("xbox_HeapAllocPageRounded", body)
        self.assertIn("xbox_GuestMemoryCommit", body)
        self.assertIn("xbox_GuestMemoryDecommit", body)
        self.assertNotIn("xbox_HeapAlloc(size, 4096", body)

    def test_free_uses_same_guest_allocator(self):
        bridge = (ROOT / "src/kernel/kernel_bridge.c").read_text(encoding="utf-8")
        body = function_body(bridge, "bridge_NtFreeVirtualMemory")
        self.assertIn("xbox_HeapReleasePageRounded", body)
        self.assertIn("xbox_GuestMemoryDecommit", body)
        self.assertNotIn("xbox_NtFreeVirtualMemory", body)
        self.assertNotIn("VirtualFree(", body)

    def test_protection_is_guest_metadata(self):
        bridge = (ROOT / "src/kernel/kernel_bridge.c").read_text(encoding="utf-8")
        body = function_body(bridge, "bridge_MmSetAddressProtect")
        self.assertIn("xbox_GuestMemorySetProtect", body)
        self.assertNotIn("xbox_MmSetAddressProtect", body)
        self.assertNotIn("VirtualProtect(", body)

    def test_guest_page_metadata_is_page_granular(self):
        layout = (ROOT / "src/kernel/xbox_memory_layout.c").read_text(
            encoding="utf-8"
        )
        for symbol in (
            "xbox_GuestMemorySetProtect",
            "xbox_GuestMemoryQueryProtect",
            "xbox_GuestMemoryDecommit",
            "xbox_GuestMemoryCommit",
            "xbox_GuestMemoryIsCommitted",
            "xbox_HeapReleasePageRounded",
        ):
            with self.subTest(symbol=symbol):
                self.assertIn(symbol, layout)

        self.assertIn("XBOX_GUEST_PAGE_SIZE 4096u", layout)
        self.assertIn("g_guest_page_protect", layout)
        self.assertIn("g_guest_page_committed", layout)

    def test_release_rejects_non_page_backed_or_stale_allocations(self):
        layout = (ROOT / "src/kernel/xbox_memory_layout.c").read_text(
            encoding="utf-8"
        )
        body = function_body(layout, "xbox_HeapReleasePageRounded")
        self.assertIn("xbox_HeapFreeTracked", body)

        tracked = function_body(layout, "xbox_HeapFreeTracked")
        self.assertIn("require_page_backed", tracked)
        self.assertIn("XBOX_HEAP_CLASS_PAGE_BACKED", tracked)
        self.assertIn("!allocation->in_use", tracked)

    def test_audit_tracks_two_guest_native_migrations(self):
        audit = (
            ROOT
            / "ports/mercenaries/xbox360/phase4a_kernel_surface_audit"
            / "audit_phase4a_kernel_surface.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"bridge_NtFreeVirtualMemory"', audit)
        self.assertIn('"bridge_MmSetAddressProtect"', audit)
        self.assertIn('"guest_native_bound"', audit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
