"""FileMan type-code decomposer.

Re-typed clean per the LESSONS-LEARNED L8 guidance — the raw type
string at ``^DD(file, field, 0)`` piece 2 packs prefix flags, a base
type code, and optional suffix modifiers into one unstructured field.

Grammar (informal)::

    type      = prefix? base numeric_spec? suffix?
    prefix    = ("R" | "*" | "M")+
    base      = "F" | "N" | "D" | "DC" | "S" | "P" <file_num>
              | "M" | "C" | "W" | "K" | "V" | "A" | "B"
    numeric_spec = "J" width ("," decimals)?         ; only after N
    suffix    = ("'" | lowercase | uppercase_mod)+

Known pitfalls (all from vista-fm-browser):

* ``MRD`` → multiple + required + DATE (base=D) — not M + modifier "RD".
* ``DC`` → COMPUTED DATE, two-letter base — don't split as D + "C".
* ``P50.68`` → pointer to subfile file number 50.68 (decimal).
* ``P200'`` → pointer to 200 + required flag (trailing apostrophe).
* ``NJ3,0`` → numeric width 3, 0 decimals.
* Lowercase modifiers (``a``, ``t``, ``m``, ``p``, ``w``) are
  preserved but uninterpreted (Q5).

fm-web uses this mainly for display. On the hot path we delegate to
``DDR GETS ENTRY DATA`` which returns FileMan-decoded external form —
so a decomposer bug is display-only, not data-loss.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

_BASE_SINGLE_CHARS = frozenset("FNDSPMCWKVABI")
_PREFIX_CHARS = frozenset("R*")
_LOWERCASE_MODS = frozenset("atmpw")

_TYPE_NAMES: dict[str, str] = {
    "F": "FREE TEXT",
    "N": "NUMERIC",
    "D": "DATE/TIME",
    "DC": "COMPUTED DATE",
    "S": "SET OF CODES",
    "P": "POINTER",
    "M": "MULTIPLE",
    "C": "COMPUTED",
    "W": "WORD PROCESSING",
    "K": "MUMPS",
    "V": "VARIABLE POINTER",
    "A": "AUDIT",
    "B": "BOOLEAN",
    "I": "INTEGER",
}


class TypeSpec(BaseModel):
    """Decomposed FileMan type.

    ``raw`` preserves the exact string from ``^DD`` for display and
    audit; all other fields are interpretation of it.
    """

    model_config = ConfigDict(frozen=True)

    raw: str
    base: str
    name: str
    is_required: bool = False
    is_audit: bool = False
    is_multiple: bool = False
    pointer_file: float | None = None
    numeric_width: int | None = None
    numeric_decimals: int | None = None
    modifiers: str = ""  # leftover characters after base + suffix flags
    lowercase_mods: str = ""  # lowercase letters preserved separately

    @classmethod
    def decompose(cls, raw: str) -> "TypeSpec":
        """Parse a raw FileMan type string into a :class:`TypeSpec`.

        Always returns a TypeSpec. Unknown inputs keep ``raw`` and get
        ``base=""``, ``name="UNKNOWN"`` — we never raise on parse.
        """
        s = raw.strip()
        if not s:
            return cls(raw=raw, base="", name="UNKNOWN")

        i = 0
        is_required = False
        is_audit = False
        is_multiple = False

        # Prefix flags — ``R`` (required), ``*`` (audit) may repeat.
        while i < len(s) and s[i] in _PREFIX_CHARS:
            if s[i] == "R":
                is_required = True
            elif s[i] == "*":
                is_audit = True
            i += 1

        # Multiple prefix — ``M`` is a prefix only when followed by a
        # recognised base character (``MRD``: multiple+required+DATE).
        if i < len(s) - 1 and s[i] == "M":
            nxt = s[i + 1]
            # Peek past any further R/* prefix flags
            j = i + 1
            while j < len(s) and s[j] in _PREFIX_CHARS:
                if s[j] == "R":
                    is_required = True
                elif s[j] == "*":
                    is_audit = True
                j += 1
            if j < len(s) and s[j] in _BASE_SINGLE_CHARS and s[j] != "M":
                is_multiple = True
                i = j
                nxt = s[j]  # noqa: F841 — kept for readability

        # Base type.
        if i >= len(s):
            return cls(
                raw=raw,
                base="",
                name="UNKNOWN",
                is_required=is_required,
                is_audit=is_audit,
                is_multiple=is_multiple,
            )

        base = s[i]
        # Reject unrecognised base characters — keep raw, mark UNKNOWN.
        if base not in _BASE_SINGLE_CHARS:
            return cls(
                raw=raw,
                base="",
                name="UNKNOWN",
                is_required=is_required,
                is_audit=is_audit,
                is_multiple=is_multiple,
            )

        pointer_file: float | None = None
        width: int | None = None
        decimals: int | None = None

        # COMPUTED DATE — two-char base "DC"
        if base == "D" and i + 1 < len(s) and s[i + 1] == "C":
            base = "DC"
            i += 2
        else:
            i += 1

        # Pointer: ``P<file>`` where file can be decimal (e.g. 50.68).
        if base == "P":
            num = []
            while i < len(s) and (s[i].isdigit() or s[i] == "."):
                num.append(s[i])
                i += 1
            if num:
                try:
                    pointer_file = float("".join(num))
                except ValueError:
                    pointer_file = None

        # Numeric spec ``J<width>,<decimals>``
        if base == "N" and i < len(s) and s[i] == "J":
            i += 1
            num = []
            while i < len(s) and s[i].isdigit():
                num.append(s[i])
                i += 1
            if num:
                width = int("".join(num))
            if i < len(s) and s[i] == ",":
                i += 1
                dec = []
                while i < len(s) and s[i].isdigit():
                    dec.append(s[i])
                    i += 1
                if dec:
                    decimals = int("".join(dec))

        # Remaining chars: trailing apostrophe = required-here flag;
        # lowercase letters kept separately; everything else in
        # ``modifiers``.
        tail = s[i:]
        mods: list[str] = []
        lowers: list[str] = []
        for ch in tail:
            if ch == "'":
                is_required = True
            elif ch in _LOWERCASE_MODS:
                lowers.append(ch)
            else:
                mods.append(ch)

        name = _TYPE_NAMES.get(base, "UNKNOWN") if base else "UNKNOWN"
        return cls(
            raw=raw,
            base=base,
            name=name,
            is_required=is_required,
            is_audit=is_audit,
            is_multiple=is_multiple,
            pointer_file=pointer_file,
            numeric_width=width,
            numeric_decimals=decimals,
            modifiers="".join(mods),
            lowercase_mods="".join(lowers),
        )
