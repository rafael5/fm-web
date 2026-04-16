"""EntryService — list + get entries with cursor pagination."""

from __future__ import annotations

from fm_web.broker import FakeRPCBroker
from fm_web.models import Entry, EntryPage
from fm_web.services.entries import EntryService


def _lister_rows(rows: list[tuple[str, str]]) -> str:
    lines = [str(len(rows))] + [f"{ien}^{ext}" for ien, ext in rows]
    return "\r\n".join(lines) + "\r\n"


def _gets_rows(pairs: list[tuple[str, str, str, str]]) -> str:
    """Each tuple: (file, ien, field, value). VEHU 5-piece shape."""
    body = [f"{f}^{i}^{fn}^^{v}" for f, i, fn, v in pairs]
    return "[Data]\r\n" + "\r\n".join(body) + "\r\n"


class TestListEntries:
    def test_returns_entries_with_default_field(self):
        broker = FakeRPCBroker(
            responses={
                "DDR LISTER": _lister_rows(
                    [
                        ("1", "ALICE"),
                        ("2", "BOB"),
                        ("3", "CAROL"),
                    ]
                ),
            },
        )
        broker.connect()
        svc = EntryService(broker)
        page = svc.list_entries(2, limit=3)
        assert isinstance(page, EntryPage)
        assert page.file_number == 2.0
        assert [e.ien for e in page.entries] == ["1", "2", "3"]
        assert [e.name for e in page.entries] == ["ALICE", "BOB", "CAROL"]

    def test_cursor_is_last_external_value(self):
        broker = FakeRPCBroker(
            responses={
                "DDR LISTER": _lister_rows([("1", "ALICE"), ("2", "BOB")]),
            },
        )
        broker.connect()
        svc = EntryService(broker)
        page = svc.list_entries(2, limit=2)
        assert page.next_cursor == "BOB"

    def test_no_cursor_when_page_short(self):
        broker = FakeRPCBroker(
            responses={
                "DDR LISTER": _lister_rows([("1", "ALICE")]),
            },
        )
        broker.connect()
        svc = EntryService(broker)
        page = svc.list_entries(2, limit=10)
        # Only one row returned; we asked for 10. Page is complete.
        assert page.next_cursor is None

    def test_cursor_passed_as_from_value(self):
        # When called with cursor="BOB", the underlying LISTER should
        # receive from_value="BOB" (position index 4 in the param list).
        broker = FakeRPCBroker(
            responses={"DDR LISTER": _lister_rows([])},
        )
        broker.connect()
        svc = EntryService(broker)
        svc.list_entries(2, limit=5, cursor="BOB")
        call = next(c for c in broker.calls if c.rpc_name == "DDR LISTER")
        assert call.params[0]["FROM"] == "BOB"


class TestGetEntry:
    def test_returns_entry_with_all_requested_fields(self):
        broker = FakeRPCBroker(
            responses={
                "DDR GETS ENTRY DATA": _gets_rows(
                    [
                        ("2", "1", ".01", "PATIENT,TEST"),
                        ("2", "1", ".02", "MALE"),
                        ("2", "1", ".03", "JAN 1, 1960"),
                    ]
                ),
            },
        )
        broker.connect()
        svc = EntryService(broker)
        e = svc.get_entry(2, "1", fields=".01;.02;.03")
        assert isinstance(e, Entry)
        assert e.file_number == 2.0
        assert e.ien == "1"
        assert e.fields[0.01].value == "PATIENT,TEST"
        assert e.fields[0.02].value == "MALE"

    def test_external_form_by_default(self):
        # Captured call must request FLAGS="E" (external form) —
        # LESSONS-LEARNED L18: we never parse internal form in v1.
        broker = FakeRPCBroker(
            responses={"DDR GETS ENTRY DATA": "[Data]\r\n"},
        )
        broker.connect()
        svc = EntryService(broker)
        svc.get_entry(2, "1")
        call = next(c for c in broker.calls if c.rpc_name == "DDR GETS ENTRY DATA")
        params_dict = call.params[0]
        assert params_dict["FLAGS"] == "E"
        assert params_dict["IENS"] == "1,"

    def test_returns_none_when_no_data(self):
        broker = FakeRPCBroker(
            responses={"DDR GETS ENTRY DATA": "[Data]\r\n"},
        )
        broker.connect()
        svc = EntryService(broker)
        assert svc.get_entry(2, "999") is None
