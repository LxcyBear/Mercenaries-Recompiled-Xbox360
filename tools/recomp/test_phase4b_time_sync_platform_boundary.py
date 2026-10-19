"""Pin Phase 4B-A2 timing/sync imports to the shared platform boundary."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

def function_body(text: str, name: str) -> str:
    match = re.search(r"\b" + re.escape(name) + r"\s*\([^;]*?\)\s*\{", text, re.S)
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

class Phase4BTimeSyncBoundaryTests(unittest.TestCase):
    def test_runtime_uses_platform_boundary(self):
        hal = (ROOT / "src/kernel/kernel_hal.c").read_text(encoding="utf-8")
        thread = (ROOT / "src/kernel/kernel_thread.c").read_text(encoding="utf-8")
        sync = (ROOT / "src/kernel/kernel_sync.c").read_text(encoding="utf-8")

        self.assertIn("merc_platform_query_system_time(CurrentTime)", function_body(hal, "xbox_KeQuerySystemTime"))
        self.assertIn("merc_platform_stall_us(MicroSeconds)", function_body(hal, "xbox_KeStallExecutionProcessor"))

        delay = function_body(thread, "xbox_KeDelayExecutionThread")
        self.assertIn("merc_platform_query_system_time(&now)", delay)
        host_sleep = function_body(thread, "xbox_host_aware_sleep")
        for call in (
            "merc_platform_query_performance_frequency",
            "merc_platform_query_performance_counter",
            "merc_platform_get_tick_count",
            "merc_platform_sleep",
        ):
            self.assertIn(call, host_sleep)

        self.assertIn("merc_platform_set_event", function_body(sync, "xbox_KeSetEvent"))
        self.assertIn("merc_platform_wait_single", function_body(sync, "xbox_KeWaitForSingleObject"))

    def test_backend_contains_hardware_proven_xdk_primitives(self):
        source = (ROOT / "src/platform/kernel_time_sync.c").read_text(encoding="utf-8")
        for call in (
            "QueryPerformanceCounter", "QueryPerformanceFrequency", "GetTickCount",
            "GetSystemTimeAsFileTime", "Sleep", "SleepEx", "SetEvent",
            "WaitForSingleObjectEx",
        ):
            self.assertIn(call, source)

if __name__ == "__main__":
    unittest.main(verbosity=2)
