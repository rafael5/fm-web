"""DDR* response parsers."""

from fm_web.broker.responses import (
    GetsEntry,
    ListerEntry,
    parse_finder_response,
    parse_gets_response,
    parse_lister_response,
)


class TestParseGetsResponse:
    def test_single_line(self):
        raw = "2^1,^.01^WASHINGTON,GEORGE"
        assert parse_gets_response(raw) == [
            GetsEntry(2.0, "1,", 0.01, "WASHINGTON,GEORGE")
        ]

    def test_multi_line_crlf(self):
        raw = "2^1,^.01^A\r\n2^1,^.02^M\r\n"
        assert parse_gets_response(raw) == [
            GetsEntry(2.0, "1,", 0.01, "A"),
            GetsEntry(2.0, "1,", 0.02, "M"),
        ]

    def test_vehu_five_piece_format(self):
        # VEHU wire shape (confirmed via live recording):
        #   file^ien^field^multiple_instance^value
        # Empty mult instance is the common case for non-multi fields.
        raw = "2^1^.01^^PROGRAMMER,ONE"
        entries = parse_gets_response(raw)
        assert len(entries) == 1
        assert entries[0].value == "PROGRAMMER,ONE"

    def test_vehu_shape_with_value_carets_assigns_last_piece(self):
        # With the 5-piece parser, a line with 6+ pieces treats piece 5
        # as the value (everything after the mult marker). This is a
        # known limitation — value-carets cannot be distinguished from
        # mult pieces without schema context. Documented in parser
        # docstring.
        raw = "2^1^.09^^Y^Z"
        entries = parse_gets_response(raw)
        assert entries[0].value == "Y^Z"

    def test_malformed_lines_skipped(self):
        raw = "only three^fields^here\n2^1,^.01^good\n"
        assert parse_gets_response(raw) == [GetsEntry(2.0, "1,", 0.01, "good")]

    def test_empty_input(self):
        assert parse_gets_response("") == []


class TestParseListerResponse:
    def test_discards_count_line(self):
        raw = "3\r\n1^ALICE\r\n2^BOB\r\n3^CAROL\r\n"
        result = parse_lister_response(raw)
        assert [e.ien for e in result] == ["1", "2", "3"]
        assert [e.external_value for e in result] == ["ALICE", "BOB", "CAROL"]

    def test_extra_fields_by_position(self):
        raw = "1\r\n42^NAME^M^2450101\r\n"
        entry = parse_lister_response(raw)[0]
        assert entry.ien == "42"
        assert entry.external_value == "NAME"
        assert entry.extra_fields == {"2": "M", "3": "2450101"}

    def test_empty_extras_skipped(self):
        raw = "1\r\n1^A^^B\r\n"
        entry = parse_lister_response(raw)[0]
        # Position 2 is empty; should not appear.
        assert "2" not in entry.extra_fields
        assert entry.extra_fields == {"3": "B"}

    def test_empty_input(self):
        assert parse_lister_response("") == []
        assert parse_lister_response("0\r\n") == []


class TestParseFinderResponse:
    def test_extracts_iens(self):
        raw = "3\r\n1\r\n5\r\n42\r\n"
        assert parse_finder_response(raw) == ["1", "5", "42"]

    def test_single_result(self):
        raw = "1\r\n7\r\n"
        assert parse_finder_response(raw) == ["7"]

    def test_no_results(self):
        assert parse_finder_response("0\r\n") == []


def test_lister_entry_is_mutable_for_enrichment():
    # Services layer will enrich extra_fields after wire parse — dataclass
    # must not be frozen.
    e = ListerEntry(ien="1", external_value="A")
    e.extra_fields["2"] = "x"
    assert e.extra_fields == {"2": "x"}
