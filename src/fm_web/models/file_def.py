"""Domain models for FileMan file + field definitions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .type_spec import TypeSpec


class FieldDef(BaseModel):
    """One field in a FileMan file."""

    model_config = ConfigDict(frozen=True)

    file_number: float
    field_number: float
    label: str
    type: TypeSpec
    title: str = ""
    storage: str = ""  # e.g. "0;3" — zero-node piece 3
    input_transform: str = ""
    help_prompt: str = ""
    description: list[str] = Field(default_factory=list)
    set_values: dict[str, str] = Field(default_factory=dict)  # S-type only


class FileDef(BaseModel):
    """One FileMan file's header + field list."""

    model_config = ConfigDict(frozen=True)

    file_number: float
    label: str
    global_root: str  # e.g. "^DPT(" — display only
    package: str = ""  # resolved display name, not a lookup key
    description: list[str] = Field(default_factory=list)
    fields: dict[float, FieldDef] = Field(default_factory=dict)

    @property
    def field_count(self) -> int:
        return len(self.fields)


class CrossRefInfo(BaseModel):
    """One cross-reference on a FileMan file."""

    model_config = ConfigDict(frozen=True)

    ien: str
    file_number: float
    name: str  # "B", "AC", "ADFN", …
    xref_type: str = ""  # "REGULAR" / "MUMPS" / ""
    description: str = ""
