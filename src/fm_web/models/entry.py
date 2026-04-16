"""Domain models for FileMan entries."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FieldValue(BaseModel):
    """One field value on an entry — external (resolved) form by default.

    FLAGS="E" on DDR GETS ENTRY DATA returns external form (dates
    rendered, pointers resolved, set codes labeled). We never see the
    internal form unless the caller explicitly asked for it.
    See LESSONS-LEARNED L18.
    """

    model_config = ConfigDict(frozen=True)

    field_number: float
    value: str
    is_external: bool = True


class Entry(BaseModel):
    """One FileMan entry (row).

    ``fields`` is keyed by FileMan field number — callers usually know
    the numbers ahead of time (they requested them via the ``fields``
    param of DDR GETS or DDR LISTER). When we list entries with a
    default field set (just .01), ``fields`` holds just that field.
    """

    model_config = ConfigDict(frozen=True)

    file_number: float
    ien: str
    fields: dict[float, FieldValue] = Field(default_factory=dict)

    @property
    def name(self) -> str:
        """Convenience accessor for field .01 (NAME)."""
        v = self.fields.get(0.01)
        return v.value if v else ""


class EntryPage(BaseModel):
    """A paginated slice of entries + a cursor for the next page.

    ``next_cursor`` is the last ``external_value`` (usually the .01
    field) from this page — pass it back as ``cursor`` to fetch the
    next page. ``None`` when the page is the last.
    """

    model_config = ConfigDict(frozen=True)

    file_number: float
    entries: list[Entry]
    next_cursor: str | None = None
