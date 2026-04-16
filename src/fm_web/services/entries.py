"""Entry browser service — list + get entries via DDR LISTER/GETS."""

from __future__ import annotations

import logging

from ..broker.responses import parse_gets_response, parse_lister_response
from ..models import Entry, EntryPage, FieldValue

log = logging.getLogger(__name__)


def _strip_data_header(raw: str) -> str:
    return "\r\n".join(
        ln
        for ln in raw.replace("\r\n", "\n").split("\n")
        if ln and not ln.startswith("[Data]")
    )


def _fmt(n: int | float) -> str:
    if n == int(n):
        return str(int(n))
    s = str(n)
    return s[1:] if s.startswith("0.") else s


class EntryService:
    """Paginated read-only entry access for any FileMan file."""

    def __init__(self, broker) -> None:
        self._broker = broker

    # ---- list (paginated) -------------------------------------------

    def list_entries(
        self,
        file_number: int | float,
        *,
        limit: int = 25,
        cursor: str = "",
        xref: str = "B",
    ) -> EntryPage:
        """Return a page of entries from ``file_number``.

        ``cursor`` is the ``external_value`` from the end of the
        previous page (passed to ``DDR LISTER`` as ``FROM``).
        ``next_cursor`` on the returned :class:`EntryPage` is the
        last entry's external value when a full page was returned;
        ``None`` when the page is the tail of the data set.
        """
        n = _fmt(file_number)
        raw = self._broker.call(
            "DDR LISTER",
            n,
            "",
            "P",
            str(limit),
            cursor,
            "0",
            "",
            xref,
            "",
            "",
        )
        rows = parse_lister_response(raw)
        entries: list[Entry] = []
        for row in rows:
            entries.append(
                Entry(
                    file_number=float(file_number),
                    ien=row.ien,
                    fields={
                        0.01: FieldValue(
                            field_number=0.01,
                            value=row.external_value,
                            is_external=True,
                        ),
                    },
                )
            )
        # Next cursor = last row's display value IFF the page was full.
        next_cursor = entries[-1].name if entries and len(entries) >= limit else None
        return EntryPage(
            file_number=float(file_number),
            entries=entries,
            next_cursor=next_cursor,
        )

    # ---- single entry -----------------------------------------------

    def get_entry(
        self,
        file_number: int | float,
        ien: str,
        *,
        fields: str = "*",
    ) -> Entry | None:
        """Return one entry with the requested fields (external form).

        ``fields`` accepts the DDR GETS field selector: ``"*"`` = all
        top-level fields, ``"**"`` = all fields including multiples,
        or a caret-separated list like ``".01;.02;.03"``.
        """
        n = _fmt(file_number)
        iens = ien if ien.endswith(",") else f"{ien},"
        raw = self._broker.call(
            "DDR GETS ENTRY DATA",
            {"FILE": n, "IENS": iens, "FIELDS": fields, "FLAGS": "E"},
        )
        gets = parse_gets_response(_strip_data_header(raw))
        if not gets:
            return None
        value_map: dict[float, FieldValue] = {}
        for g in gets:
            value_map[g.field_number] = FieldValue(
                field_number=g.field_number,
                value=g.value,
                is_external=True,
            )
        return Entry(
            file_number=float(file_number),
            ien=ien,
            fields=value_map,
        )
