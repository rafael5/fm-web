"""Domain model for a FileMan PACKAGE (file #9.4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PackageDef(BaseModel):
    """One PACKAGE entry from file 9.4.

    ``prefix`` is the M namespace (e.g. ``XU``, ``OR``). ``files`` is
    populated only when the caller drills into the FILE subfile
    (``^DIC(9.4, IEN, 4, ...)``) — in a basic listing it's empty.
    LESSONS-LEARNED L12 notes that some sites ship a PACKAGE entry
    with a blank prefix; that's a data-quality issue, not a bug.
    """

    model_config = ConfigDict(frozen=True)

    ien: str
    name: str
    prefix: str = ""
    short_description: str = ""
    files: list[float] = Field(default_factory=list)
