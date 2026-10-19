"""Pin Phase 4B-B2 file/handle imports to the shared platform boundary."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

HOST_CALLS = (
    "CreateFileW", "CreateFileA", "ReadFile", "WriteFile", "CloseHandle",
    "GetFileAttributesW", "GetFileAttributesA",
    "SetFilePointer", "SetFilePointerEx",
    "GetFileInformationByHandle",
    "FindFirstFile", "FindFirstFileW", "FindNextFile", "FindNextFileW",
    "FindClose", "GetLastError", "SetLastError",
    "QueryPerformanceCounter", "QueryPerformanceFrequency",
)


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


def direct_host_calls(body: str) -> list[str]:
    return [
        name
        for name in HOST_CALLS
        if re.search(
            r"(?<![A-Za-z0-9_])" + re.escape(name) + r"\s*\(",
            body,
        )
    ]


class Phase4BFileBoundaryTests(unittest.TestCase):
    def test_nine_file_imports_route_through_platform_boundary(self):
        source = (ROOT / "src/kernel/kernel_file.c").read_text(encoding="utf-8")

        required = {
            "xbox_NtCreateFile": "merc_platform_file_open",
            "xbox_NtReadFile": "merc_platform_file_read",
            "xbox_NtWriteFile": "merc_platform_file_write",
            "xbox_NtClose": "merc_platform_file_close",
            "xbox_NtQueryInformationFile": "merc_platform_file_query_info",
            "xbox_NtSetInformationFile": "merc_platform_file_set_",
            "xbox_NtQueryFullAttributesFile": "merc_platform_file_query_path_info",
            "xbox_NtQueryDirectoryFile": "merc_platform_file_find_",
        }

        for name, platform_call in required.items():
            with self.subTest(function=name):
                body = function_body(source, name)
                self.assertIn(platform_call, body)
                self.assertEqual(
                    direct_host_calls(body),
                    [],
                    f"{name} still owns direct host calls",
                )

        open_body = function_body(source, "xbox_NtOpenFile")
        self.assertIn("xbox_NtCreateFile", open_body)
        self.assertEqual(direct_host_calls(open_body), [])

    def test_read_cache_uses_same_platform_backend(self):
        source = (ROOT / "src/kernel/kernel_file.c").read_text(encoding="utf-8")
        body = function_body(source, "read_file_through_guest_cache")
        self.assertIn("merc_platform_file_read", body)
        self.assertIn("merc_platform_file_last_error", body)
        self.assertIn("merc_platform_file_set_last_error", body)
        self.assertNotIn("ReadFile(", body)

    def test_xenon_backend_contains_hardware_proven_primitives(self):
        source = (ROOT / "src/platform/kernel_file_io.c").read_text(
            encoding="utf-8"
        )
        for call in (
            "CreateFileA",
            "ReadFile",
            "WriteFile",
            "GetFileInformationByHandle",
            "SetFilePointer",
            "SetEndOfFile",
            "GetFileAttributesA",
            "FindFirstFileA",
            "FindNextFileA",
            "FindClose",
            "CloseHandle",
            "DeleteFileA",
        ):
            with self.subTest(primitive=call):
                self.assertIn(call, source)

    def test_platform_backend_is_built_on_windows(self):
        cmake = (ROOT / "src/platform/CMakeLists.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "kernel_time_sync.c kernel_file_io.c",
            cmake,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
