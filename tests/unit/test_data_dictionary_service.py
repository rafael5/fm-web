"""DataDictionaryService — TDD against FakeRPCBroker.

DD browsing is built on ``DDR LISTER FILE=1`` (the FILE registry) and
``DDR GETS ENTRY DATA FILE=1 IENS=n,`` (per-file metadata) — per
LESSONS-LEARNED L31. No ``DDR GET DD`` dependency.
"""

from __future__ import annotations

import pytest

from fm_web.broker import FakeRPCBroker
from fm_web.models import FieldDef, FileDef
from fm_web.services.data_dictionary import DataDictionaryService

# ---- fixtures ------------------------------------------------------


def _file_list_response(rows: list[tuple[str, str]]) -> str:
    """Build a DDR LISTER response for FILE registry (file #1).

    Each row is (file_number_as_ien, label). Format:
        count\r\nien^label\r\n...
    """
    lines = [str(len(rows))] + [f"{ien}^{lbl}" for ien, lbl in rows]
    return "\r\n".join(lines) + "\r\n"


def _gets_response(pairs: list[tuple[str, str, str]]) -> str:
    """Build a DDR GETS response.

    Each tuple is (file, field_number, value). VEHU shape: the payload
    starts with ``[Data]`` followed by ``file^iens^field^mult^value``.
    """
    body_lines = [f"{f}^1^{fn}^^{v}" for f, fn, v in pairs]
    return "[Data]\r\n" + "\r\n".join(body_lines) + "\r\n"


@pytest.fixture
def broker_with_files() -> FakeRPCBroker:
    """FakeRPCBroker preloaded with a 3-file registry."""
    broker = FakeRPCBroker(
        responses={
            "DDR LISTER": _file_list_response(
                [
                    ("2", "PATIENT"),
                    ("200", "NEW PERSON"),
                    ("9.4", "PACKAGE"),
                ]
            ),
        },
    )
    broker.connect()
    return broker


# ---- list_files ----------------------------------------------------


class TestListFiles:
    def test_returns_files_from_registry(self, broker_with_files):
        svc = DataDictionaryService(broker_with_files)
        files = svc.list_files()
        assert [f.file_number for f in files] == [2.0, 200.0, 9.4]
        assert [f.label for f in files] == ["PATIENT", "NEW PERSON", "PACKAGE"]

    def test_empty_registry(self):
        broker = FakeRPCBroker(responses={"DDR LISTER": _file_list_response([])})
        broker.connect()
        svc = DataDictionaryService(broker)
        assert svc.list_files() == []

    def test_uses_ddr_lister_on_file_1(self, broker_with_files):
        """Must call DDR LISTER with FILE=1 — the FILE registry
        (per L31, not the deprecated DDR GET DD)."""
        svc = DataDictionaryService(broker_with_files)
        svc.list_files()
        calls = [c for c in broker_with_files.calls if c.rpc_name == "DDR LISTER"]
        assert calls, "expected at least one DDR LISTER call"
        # First arg must be "1" for the FILE registry
        assert calls[0].params[0] == "1"


# ---- get_file ------------------------------------------------------


class TestGetFile:
    def test_returns_file_header_and_fields(self):
        # One GETS call for the file header (name, global),
        # one LISTER call for the field subfile.
        broker = FakeRPCBroker(
            responses={
                # File header: NEW PERSON with .01=NAME and .1=GLOBAL ROOT
                (
                    "DDR GETS ENTRY DATA",
                    (
                        ("FIELDS", ".01;.1"),
                        ("FILE", "1"),
                        ("FLAGS", "E"),
                        ("IENS", "200,"),
                    ),
                ): _gets_response(
                    [
                        ("1", ".01", "NEW PERSON"),
                        ("1", ".1", "^VA(200,"),
                    ]
                ),
                # Field subfile of file 1 (#1.01): fields on file 200.
                (
                    "DDR LISTER",
                    ("1", ",200,", "P", "200", "", "0", "", "B", "", ""),
                ): _file_list_response(
                    [
                        (".01", "NAME"),
                        ("2", "ACCESS CODE"),
                    ]
                ),
            },
        )
        broker.connect()
        svc = DataDictionaryService(broker)
        f = svc.get_file(200)
        assert isinstance(f, FileDef)
        assert f.file_number == 200.0
        assert f.label == "NEW PERSON"
        assert f.global_root == "^VA(200,"
        assert set(f.fields.keys()) == {0.01, 2.0}

    def test_returns_none_for_missing_file(self):
        broker = FakeRPCBroker(
            responses={"DDR GETS ENTRY DATA": "[Data]\r\n"},
        )
        broker.connect()
        svc = DataDictionaryService(broker)
        assert svc.get_file(99999) is None


# ---- get_field -----------------------------------------------------


class TestGetField:
    def test_returns_field_with_type_spec(self):
        broker = FakeRPCBroker(
            responses={
                # GETS on file 1 subfile for (file 200, field .01)
                # Uses IENS=".01,200," (subfile ien, parent ien)
                (
                    "DDR GETS ENTRY DATA",
                    (
                        ("FIELDS", "*"),
                        ("FILE", "1.01"),
                        ("FLAGS", "E"),
                        ("IENS", ".01,200,"),
                    ),
                ): _gets_response(
                    [
                        ("1.01", ".01", "NAME"),
                        ("1.01", "1", "RF"),  # raw type
                        ("1.01", "2", "0;1"),  # storage
                    ]
                ),
            },
        )
        broker.connect()
        svc = DataDictionaryService(broker)
        fd = svc.get_field(200, 0.01)
        assert isinstance(fd, FieldDef)
        assert fd.label == "NAME"
        assert fd.type.raw == "RF"
        assert fd.type.is_required and fd.type.base == "F"
        assert fd.storage == "0;1"

    def test_returns_none_for_missing_field(self):
        broker = FakeRPCBroker(
            responses={"DDR GETS ENTRY DATA": "[Data]\r\n"},
        )
        broker.connect()
        svc = DataDictionaryService(broker)
        assert svc.get_field(200, 999) is None


# ---- list_cross_refs -----------------------------------------------


class TestListCrossRefs:
    def test_returns_indexes_from_index_file(self):
        # INDEX file #.11 — listing scoped to entries for file 200.
        broker = FakeRPCBroker(
            responses={
                # DDR LISTER on file .11 with a screen for our file number
                (
                    "DDR LISTER",
                    (
                        ".11",
                        "",
                        "P",
                        "200",
                        "",
                        "0",
                        "",
                        "B",
                        'I $P(^DD("IX",Y,0),U)=200',
                        "",
                    ),
                ): _file_list_response(
                    [
                        ("42", "B"),
                        ("43", "AC"),
                    ]
                ),
            },
        )
        broker.connect()
        svc = DataDictionaryService(broker)
        xrefs = svc.list_cross_refs(200)
        assert [x.name for x in xrefs] == ["B", "AC"]
        assert all(x.file_number == 200.0 for x in xrefs)
