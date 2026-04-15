"""Parsers for DDR* RPC response payloads.

Pure functions turning the caret-delimited text payloads returned by
``DDR LISTER``, ``DDR GETS ENTRY DATA``, and ``DDR FINDER`` into typed
Python objects. These live separately from :mod:`fm_web.broker.wire`
because they parse the *payload* (FileMan-level), not the envelope
(XWB-level).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class GetsEntry:
    """One field value returned by ``DDR GETS ENTRY DATA`` (``GETS^DIQ``).

    Wire format is ``file^iens^field^value`` per line.
    """

    file_number: float
    iens: str
    field_number: float
    value: str


@dataclass(slots=True)
class ListerEntry:
    """One entry returned by ``DDR LISTER`` (``LIST^DIC``).

    ``external_value`` is the display form of the .01 field (or
    whichever field drives the identifier). ``extra_fields`` holds any
    additional caret-pieces requested via the ``fields`` parameter,
    keyed by 1-based position.
    """

    ien: str
    external_value: str
    extra_fields: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------


def parse_gets_response(raw: str) -> list[GetsEntry]:
    """Parse ``DDR GETS ENTRY DATA`` output into :class:`GetsEntry` objects.

    Lines with fewer than four caret-pieces or non-numeric file/field
    numbers are silently skipped — FileMan sometimes emits header or
    divider lines we don't care about.
    """
    out: list[GetsEntry] = []
    for raw_line in raw.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("^", 3)
        if len(parts) < 4:
            continue
        try:
            file_num = float(parts[0])
            field_num = float(parts[2])
        except ValueError:
            continue
        out.append(
            GetsEntry(
                file_number=file_num,
                iens=parts[1],
                field_number=field_num,
                value=parts[3],
            )
        )
    return out


def parse_lister_response(raw: str) -> list[ListerEntry]:
    """Parse ``DDR LISTER`` output into :class:`ListerEntry` objects.

    Format: first line is the total count (discarded); each subsequent
    line is ``ien^external_value[^extra1[^extra2...]]``.
    """
    out: list[ListerEntry] = []
    lines = raw.replace("\r\n", "\n").split("\n")
    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("^")
        ien = parts[0]
        external_value = parts[1] if len(parts) > 1 else ""
        extras = {str(i): parts[i] for i in range(2, len(parts)) if parts[i]}
        out.append(
            ListerEntry(
                ien=ien,
                external_value=external_value,
                extra_fields=extras,
            )
        )
    return out


def parse_finder_response(raw: str) -> list[str]:
    """Parse ``DDR FINDER`` / ``DDR FIND1`` into a list of IEN strings.

    Format: first line is the total count (discarded); each subsequent
    line is one IEN.
    """
    lines = raw.replace("\r\n", "\n").split("\n")
    return [ln.strip() for ln in lines[1:] if ln.strip()]
