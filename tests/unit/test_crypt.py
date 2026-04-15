"""XUSRB1 cipher — invertibility and marker-byte invariants."""

import random

from fm_web.broker.crypt import _Z, encrypt


class TestEncrypt:
    def test_wraps_with_marker_bytes(self):
        rng = random.Random(42)
        out = encrypt("hello", rng=rng)
        # First and last bytes encode the row indices used (chr(idx+31)).
        # idx is 1-20, so markers are in chr(32)..chr(51) — ASCII " " to "3".
        assert 32 <= ord(out[0]) <= 51
        assert 32 <= ord(out[-1]) <= 51

    def test_distinct_row_markers(self):
        # The two marker bytes must encode different rows.
        rng = random.Random(7)
        out = encrypt("abc", rng=rng)
        assert out[0] != out[-1]

    def test_deterministic_with_seeded_rng(self):
        rng_a = random.Random(123)
        rng_b = random.Random(123)
        assert encrypt("fakedoc1;1Doc!@#$", rng=rng_a) == encrypt(
            "fakedoc1;1Doc!@#$", rng=rng_b
        )

    def test_invertible_via_row_lookup(self):
        # With markers known, reverse the substitution table and recover
        # the plaintext — same algorithm DECRYP^XUSRB1 uses server-side.
        rng = random.Random(99)
        pt = "testuser;secret;with;special"
        ct = encrypt(pt, rng=rng)
        idix = ord(ct[0]) - 31
        associx = ord(ct[-1]) - 31
        assocstr = _Z[associx - 1]
        idstr = _Z[idix - 1]
        inverse = str.maketrans(assocstr, idstr)
        assert ct[1:-1].translate(inverse) == pt

    def test_table_has_20_rows_of_94(self):
        assert len(_Z) == 20
        for row in _Z:
            assert len(row) == 94
