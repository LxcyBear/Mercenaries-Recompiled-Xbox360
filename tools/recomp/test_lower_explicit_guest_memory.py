import unittest

from tools.recomp.lower_explicit_guest_memory import LoweringError, lower_source


class LowerExplicitGuestMemoryTests(unittest.TestCase):
    def lower(self, text):
        return lower_source(text)[0]

    def test_scalar_read(self):
        out = self.lower("eax = MEM32(esi + 4);")
        self.assertEqual(out, "eax = GUEST_READ32(esi + 4);")

    def test_nested_read(self):
        out = self.lower("eax = MEM32(MEM32(esi) + 8);")
        self.assertEqual(out, "eax = GUEST_READ32(GUEST_READ32(esi) + 8);")

    def test_simple_write(self):
        out = self.lower("MEM16(edx + 2) = eax;")
        self.assertEqual(out, "GUEST_WRITE16(edx + 2, eax);")

    def test_write_rhs_reads(self):
        out = self.lower("MEM32(edi) = MEM32(esi) + MEM8(ebx);")
        self.assertEqual(
            out,
            "GUEST_WRITE32(edi, GUEST_READ32(esi) + GUEST_READ8(ebx));",
        )

    def test_compound_write(self):
        out = self.lower("MEM16(edx + esi * 2) -= 1;")
        self.assertEqual(
            out,
            "GUEST_WRITE16(edx + esi * 2, "
            "GUEST_READ16(edx + esi * 2) - (1));",
        )

    def test_float_write(self):
        out = self.lower("MEMF(esp + 8) = MEMF(esi + 4) * 0.5f;")
        self.assertEqual(
            out,
            "GUEST_WRITEF32(esp + 8, GUEST_READF32(esi + 4) * 0.5f);",
        )

    def test_post_increment_statement(self):
        out = self.lower("MEM32(eax)++;")
        self.assertEqual(
            out, "GUEST_WRITE32(eax, GUEST_READ32(eax) + 1);")

    def test_prefix_decrement_statement(self):
        out = self.lower("--MEM8(eax);")
        self.assertEqual(
            out, "GUEST_WRITE8(eax, GUEST_READ8(eax) - 1);")

    def test_comments_and_strings_are_not_rewritten(self):
        src = '/* MEM32(x) = 1; */\nconst char *s = "MEM32(y)";\neax = MEM32(z);'
        out = self.lower(src)
        self.assertIn("/* MEM32(x) = 1; */", out)
        self.assertIn('"MEM32(y)"', out)
        self.assertIn("eax = GUEST_READ32(z);", out)

    def test_explicit_marker_is_added(self):
        out = self.lower(
            "#define RECOMP_GENERATED_CODE\n#include \"recomp_funcs.h\"\n")
        self.assertIn("#define RECOMP_EXPLICIT_GUEST_MEMORY_ABI", out)

    def test_for_body_write(self):
        out = self.lower(
            "{ uint32_t _i; for (_i = 0; _i < ecx; _i++) "
            "MEM32(edi + _i*4) = eax; }")
        self.assertEqual(
            out,
            "{ uint32_t _i; for (_i = 0; _i < ecx; _i++) "
            "GUEST_WRITE32(edi + _i*4, eax); }",
        )

    def test_if_body_write(self):
        out = self.lower("if (eax) MEM8(edi) = 0;")
        self.assertEqual(out, "if (eax) GUEST_WRITE8(edi, 0);")

    def test_write_inside_if_condition_is_rejected(self):
        with self.assertRaises(LoweringError):
            self.lower("if ((MEM32(eax) = 1) != 0) foo();")

    def test_expression_valued_write_is_rejected(self):
        with self.assertRaises(LoweringError):
            self.lower("foo(MEM32(eax) = 1);")

    def test_bitwise_and_read_is_not_address_of(self):
        out = self.lower("esi = esi & MEM32(0x30D88C);")
        self.assertEqual(
            out, "esi = esi & GUEST_READ32(0x30D88C);")

    def test_bitwise_and_mem64_read_is_not_address_of(self):
        out = self.lower("g_mm1 = (uint64_t)(g_mm1 & MEM64(esp));")
        self.assertEqual(
            out, "g_mm1 = (uint64_t)(g_mm1 & GUEST_READ64(esp));")


    def test_logical_and_read_is_not_address_of(self):
        out = self.lower(
            "if (MEM32(esi + 8) == 1u && MEM8(esi + 4)) {")
        self.assertEqual(
            out,
            "if (GUEST_READ32(esi + 8) == 1u && GUEST_READ8(esi + 4)) {",
        )

    def test_address_of_lvalue_is_rejected(self):
        with self.assertRaises(LoweringError):
            self.lower("foo(&MEM32(eax));")


if __name__ == "__main__":
    unittest.main()
