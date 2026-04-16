"""Data-dictionary service — built on DDR LISTER + DDR GETS ENTRY DATA.

Per LESSONS-LEARNED L31, fm-web does NOT use ``DDR GET DD`` (not
universal across VistA builds). Instead:

* **File enumeration** uses ``DDR LISTER FILE=1`` — the FILE registry
  where every FileMan file appears as an entry. IEN = file number.
* **File header** uses ``DDR GETS ENTRY DATA FILE=1 IENS=<n>,`` with
  fields ``.01`` (NAME) and ``.1`` (GLOBAL ROOT).
* **Field list** uses ``DDR LISTER`` on the FIELD subfile of file 1
  (sub-file number 1.01) — ``FILE=1 IENS=,<n>,`` walks all fields of
  file ``n``.
* **Per-field attributes** use ``DDR GETS ENTRY DATA FILE=1.01
  IENS=<fld>,<n>,``.
* **Cross-references** come from the INDEX file (#.11) via
  ``DDR LISTER`` scoped by a screen filtering entries for our file.

All four patterns rely on ``LIST^DIC`` + ``GETS^DIQ`` — core FileMan,
ships with every VistA.

This service is stateless; pass a connected broker at construction.
"""

from __future__ import annotations

import logging

from ..broker.responses import parse_gets_response, parse_lister_response
from ..models import CrossRefInfo, FieldDef, FileDef, TypeSpec

log = logging.getLogger(__name__)


def _strip_data_header(raw: str) -> str:
    """Drop the ``[Data]`` prefix line VEHU emits on DDR GETS responses.

    Our :func:`parse_gets_response` doesn't understand the header
    line; stripping here keeps the parser narrow.
    """
    return "\r\n".join(
        ln
        for ln in raw.replace("\r\n", "\n").split("\n")
        if ln and not ln.startswith("[Data]")
    )


def _fmt(n: int | float) -> str:
    """FileMan file/field number canonicalization.

    LESSONS-LEARNED L7: MUMPS subscripts are case-sensitive strings;
    ``.01`` and ``0.01`` are different subscripts. FileMan uses the
    leading-dot form for sub-unit numbers. Whole numbers stay
    integer-shaped.

    Examples::

        _fmt(2)     → "2"
        _fmt(2.0)   → "2"
        _fmt(0.01)  → ".01"
        _fmt(50.68) → "50.68"
    """
    if n == int(n):
        return str(int(n))
    s = str(n)
    return s[1:] if s.startswith("0.") else s


class DataDictionaryService:
    """Read-only DD browsing via the broker."""

    def __init__(self, broker) -> None:
        self._broker = broker

    # ---- file enumeration -------------------------------------------

    def list_files(self, *, limit: int = 200) -> list[FileDef]:
        """Enumerate FileMan files via the FILE registry.

        Returns shallow :class:`FileDef` records (label + file number;
        no fields loaded). Call :meth:`get_file` for the full header.
        """
        raw = self._broker.call(
            "DDR LISTER",
            {
                "FILE": "1",
                "IENS": "",
                "FIELDS": ".01",
                "FLAGS": "P",
                "MAX": str(limit),
                "FROM": "",
                "PART": "",
                "XREF": "B",
                "SCREEN": "",
                "ID": "",
            },
        )
        out: list[FileDef] = []
        for row in parse_lister_response(raw):
            try:
                num = float(row.ien)
            except ValueError:
                continue
            out.append(
                FileDef(
                    file_number=num,
                    label=row.external_value,
                    global_root="",
                )
            )
        return out

    # ---- file detail ------------------------------------------------

    def get_file(self, file_number: int | float) -> FileDef | None:
        """Return the full header + field list for one file."""
        n = _fmt(file_number)
        header_raw = self._broker.call(
            "DDR GETS ENTRY DATA",
            {"FILE": "1", "IENS": f"{n},", "FIELDS": ".01;.1", "FLAGS": "E"},
        )
        header = parse_gets_response(_strip_data_header(header_raw))
        if not header:
            return None

        label = ""
        global_root = ""
        for e in header:
            if e.field_number == 0.01:
                label = e.value
            elif abs(e.field_number - 0.1) < 1e-9:
                global_root = e.value
        if not label:
            return None

        # Walk the FIELD subfile of file 1 for this file.
        fields_raw = self._broker.call(
            "DDR LISTER",
            {
                "FILE": "1",
                "IENS": f",{n},",
                "FIELDS": "",
                "FLAGS": "P",
                "MAX": "200",
                "FROM": "",
                "PART": "",
                "XREF": "B",
                "SCREEN": "",
                "ID": "",
            },
        )
        fields: dict[float, FieldDef] = {}
        for row in parse_lister_response(fields_raw):
            try:
                fn = float(row.ien)
            except ValueError:
                continue
            # Shallow field — label only. Full attributes available via
            # :meth:`get_field`.
            fields[fn] = FieldDef(
                file_number=float(file_number),
                field_number=fn,
                label=row.external_value,
                type=TypeSpec.decompose(""),
            )

        return FileDef(
            file_number=float(file_number),
            label=label,
            global_root=global_root,
            fields=fields,
        )

    # ---- field detail -----------------------------------------------

    def get_field(
        self, file_number: int | float, field_number: int | float
    ) -> FieldDef | None:
        """Return a fully-decoded :class:`FieldDef` for one field.

        Uses file 1.01 (the FIELD subfile on the FILE registry) — IENS
        ``<field>,<file>,`` addresses one subfile entry.
        """
        n = _fmt(file_number)
        f = _fmt(field_number)
        raw = self._broker.call(
            "DDR GETS ENTRY DATA",
            {"FILE": "1.01", "IENS": f"{f},{n},", "FIELDS": "*", "FLAGS": "E"},
        )
        entries = parse_gets_response(_strip_data_header(raw))
        if not entries:
            return None

        label = ""
        raw_type = ""
        storage = ""
        title = ""
        for e in entries:
            if e.field_number == 0.01:
                label = e.value
            elif e.field_number == 1.0:
                raw_type = e.value
            elif e.field_number == 2.0:
                storage = e.value
            elif e.field_number == 3.0:
                title = e.value
        if not label:
            return None

        return FieldDef(
            file_number=float(file_number),
            field_number=float(field_number),
            label=label,
            type=TypeSpec.decompose(raw_type),
            title=title,
            storage=storage,
        )

    # ---- cross-references -------------------------------------------

    def list_cross_refs(self, file_number: int | float) -> list[CrossRefInfo]:
        """List INDEX (#.11) entries scoped to a file.

        Uses a server-side M screen on the LISTER call so we only get
        rows where piece 1 of ``^DD("IX", Y, 0)`` equals our file
        number — matches the ``file#^name^type^…`` encoding.
        """
        n = _fmt(file_number)
        screen = f'I $P(^DD("IX",Y,0),U)={n}'
        raw = self._broker.call(
            "DDR LISTER",
            {
                "FILE": ".11",
                "IENS": "",
                "FIELDS": "",
                "FLAGS": "P",
                "MAX": "200",
                "FROM": "",
                "PART": "",
                "XREF": "B",
                "SCREEN": screen,
                "ID": "",
            },
        )
        out: list[CrossRefInfo] = []
        for row in parse_lister_response(raw):
            out.append(
                CrossRefInfo(
                    ien=row.ien,
                    file_number=float(file_number),
                    name=row.external_value,
                )
            )
        return out
