"""TypeSpec decomposer — grammar locked against LESSONS-LEARNED L8-L11."""

import pytest

from fm_web.models import TypeSpec


class TestBasicTypes:
    def test_free_text(self):
        t = TypeSpec.decompose("F")
        assert t.base == "F" and t.name == "FREE TEXT"
        assert not t.is_required and not t.is_audit and not t.is_multiple

    def test_numeric(self):
        assert TypeSpec.decompose("N").base == "N"

    def test_date(self):
        t = TypeSpec.decompose("D")
        assert t.base == "D" and t.name == "DATE/TIME"

    def test_computed_date_is_two_char(self):
        # LESSONS-LEARNED L8: "DC" is one token, not D + modifier "C".
        t = TypeSpec.decompose("DC")
        assert t.base == "DC" and t.name == "COMPUTED DATE"

    def test_set_of_codes(self):
        assert TypeSpec.decompose("S").base == "S"

    def test_word_processing(self):
        assert TypeSpec.decompose("W").name == "WORD PROCESSING"


class TestPointerTypes:
    def test_integer_pointer(self):
        t = TypeSpec.decompose("P200")
        assert t.base == "P" and t.pointer_file == 200.0

    def test_decimal_pointer(self):
        # L8: P50.68 is pointer to subfile 50.68 — float not int.
        t = TypeSpec.decompose("P50.68")
        assert t.pointer_file == 50.68

    def test_trailing_apostrophe_is_required(self):
        # L9: P200' means required + pointer to 200, not a typo.
        t = TypeSpec.decompose("P200'")
        assert t.pointer_file == 200.0
        assert t.is_required


class TestPrefixFlags:
    def test_required(self):
        t = TypeSpec.decompose("RF")
        assert t.base == "F" and t.is_required and not t.is_audit

    def test_audit(self):
        t = TypeSpec.decompose("*F")
        assert t.base == "F" and t.is_audit and not t.is_required

    def test_required_plus_audit(self):
        t = TypeSpec.decompose("R*F")
        assert t.is_required and t.is_audit

    def test_multiple_alone_has_no_base(self):
        t = TypeSpec.decompose("M")
        assert t.base == "M" and t.name == "MULTIPLE"
        assert not t.is_multiple


class TestMultipleCompound:
    def test_MRD_is_multiple_required_date(self):
        # L8: MRD — the 'M' is a prefix, R is required, D is base.
        # This is the parser bug Q6 that vista-fm-browser never fully
        # nailed down. fm-web locks the correct interpretation.
        t = TypeSpec.decompose("MRD")
        assert t.is_multiple
        assert t.is_required
        assert t.base == "D"

    def test_MF_is_multiple_free_text(self):
        t = TypeSpec.decompose("MF")
        assert t.is_multiple and t.base == "F"

    def test_standalone_M_stays_multiple_base(self):
        # No following base char — M is the base, not a prefix.
        t = TypeSpec.decompose("M")
        assert t.base == "M"
        assert not t.is_multiple


class TestNumericSpec:
    def test_numeric_width_and_decimals(self):
        t = TypeSpec.decompose("NJ3,0")
        assert t.base == "N"
        assert t.numeric_width == 3
        assert t.numeric_decimals == 0

    def test_numeric_width_only(self):
        t = TypeSpec.decompose("NJ8")
        assert t.numeric_width == 8
        assert t.numeric_decimals is None


class TestLowercaseModifiers:
    def test_lowercase_a_preserved_but_uninterpreted(self):
        # L8: Q5 open question — lowercase modifiers held separately.
        t = TypeSpec.decompose("Fa")
        assert t.base == "F"
        assert t.lowercase_mods == "a"

    def test_multiple_lowercase_modifiers(self):
        t = TypeSpec.decompose("Ftm")
        assert t.base == "F"
        assert set(t.lowercase_mods) == {"t", "m"}


class TestRawPreserved:
    def test_raw_always_kept(self):
        for s in ["F", "RF", "P50.68", "NJ3,0", "MRD", "Fa", ""]:
            assert TypeSpec.decompose(s).raw == s

    def test_empty_input(self):
        t = TypeSpec.decompose("")
        assert t.base == ""
        assert t.name == "UNKNOWN"

    def test_garbage_input_does_not_raise(self):
        # Never raise on parse — unknown gracefully degrades.
        t = TypeSpec.decompose("!!!")
        assert t.base == ""


class TestImmutability:
    def test_frozen(self):
        t = TypeSpec.decompose("F")
        with pytest.raises(Exception):
            t.base = "N"  # type: ignore[misc]
