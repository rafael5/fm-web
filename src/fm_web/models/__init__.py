"""fm-web Pydantic v2 domain models — immutable value objects.

Re-typed clean per LESSONS-LEARNED L30 (no imports from
vista-fm-browser). Field names favour the FileMan vocabulary the UI
speaks; grammar of ``TypeSpec`` is documented inline with pointers to
the lessons that informed each quirk.
"""

from .entry import Entry, EntryPage, FieldValue
from .file_def import CrossRefInfo, FieldDef, FileDef
from .package import PackageDef
from .type_spec import TypeSpec

__all__ = [
    "CrossRefInfo",
    "Entry",
    "EntryPage",
    "FieldDef",
    "FieldValue",
    "FileDef",
    "PackageDef",
    "TypeSpec",
]
