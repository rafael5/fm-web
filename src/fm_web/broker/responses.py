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

    Handles two wire shapes observed across VistA builds:

    * **4-piece** — ``file^iens^field^value`` (older FileMan DBS).
    * **5-piece** — ``file^iens^field^multiple_instance^value``
      (VEHU / newer builds). When the multiple-instance piece is empty
      (the common non-multi field case) the raw line looks like
      ``2^1^.01^^NAME`` — a double-caret before the value.

    Strategy: split into at most 5 pieces. If piece 4 is empty or has
    a form compatible with a multi-instance indicator, treat piece 5
    as the value; otherwise piece 4 is the value. Never raises —
    unrecognised lines are skipped.
    """
    out: list[GetsEntry] = []
    for raw_line in raw.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("^", 4)
        if len(parts) < 4:
            continue
        try:
            file_num = float(parts[0])
            field_num = float(parts[2])
        except ValueError:
            continue
        # Determine value position. If we got 5 pieces, piece 4 is the
        # multiple-instance marker and piece 5 is the value (VEHU shape).
        # With exactly 4 pieces and no leading caret, piece 4 is value.
        if len(parts) == 5:
            value = parts[4]
        else:
            value = parts[3]
        out.append(
            GetsEntry(
                file_number=file_num,
                iens=parts[1],
                field_number=field_num,
                value=value,
            )
        )
    return out


def parse_lister_response(raw: str) -> list[ListerEntry]:
    """Parse ``DDR LISTER`` output into :class:`ListerEntry` objects.

    Handles two wire shapes:

    * **Simple** — first line is a total count; each subsequent line
      is ``ien^external_value[^extra...]``.
    * **Sectioned (VEHU V0)** — response has ``[Misc]``, ``[Data]``,
      and optionally ``[Errors]`` section markers. Only lines inside
      the ``[Data]`` section are entries. ``[Misc]`` carries pagination
      metadata (``MORE^from_value^from_ien``).

    Lines starting with ``[`` are section markers and are always
    skipped. The first line of the simple format (the count) is also
    skipped.
    """
    out: list[ListerEntry] = []
    lines = raw.replace("\r\n", "\n").split("\n")
    in_data = False
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        # Section markers
        if line.startswith("["):
            in_data = line == "[Data]"
            continue
        # Simple format: skip the first line (count)
        if i == 0 and not in_data:
            # Might be a numeric count OR a [Misc] marker (handled above).
            # If it looks like a plain number, skip it.
            if line.isdigit():
                continue
        # If we saw a [Data] marker, only accept lines inside it.
        # If we never saw any section markers (simple format), accept
        # everything after the count line.
        if not in_data and any(ln.strip().startswith("[") for ln in lines):
            continue
        parts = line.split("^")
        ien = parts[0]
        # Skip metadata-like entries (MORE, BEGIN_diERRORS, etc.)
        if ien.startswith("MORE") or ien.startswith("BEGIN"):
            continue
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
