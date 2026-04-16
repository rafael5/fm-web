"""PACKAGE (file #9.4) browser service.

Packages exist at ``^DIC(9.4, IEN, ...)`` — the PACKAGE file. Each
package's owned files live on subfile #9.4,4 (``FILE`` multiple) —
one row per FileMan file the package introduces. The .01 field of
that subfile is a pointer to the FILE registry, so the subfile row's
IEN is the file number.

LESSONS-LEARNED L12 + L13 apply: some sites have PACKAGE entries
with blank PREFIX fields, and the total count can off-by-one for
header metadata. We expose what FileMan reports — no heuristic
attribution layer at this layer (that's a downstream analysis
concern, not a browser concern).
"""

from __future__ import annotations

from ..broker.responses import parse_gets_response, parse_lister_response
from ..models import PackageDef


def _strip_data_header(raw: str) -> str:
    return "\r\n".join(
        ln
        for ln in raw.replace("\r\n", "\n").split("\n")
        if ln and not ln.startswith("[Data]")
    )


class PackageService:
    def __init__(self, broker) -> None:
        self._broker = broker

    def list_packages(self, *, limit: int = 500) -> list[PackageDef]:
        """List every PACKAGE entry (shallow — no prefix/files loaded)."""
        raw = self._broker.call(
            "DDR LISTER",
            {
                "FILE": "9.4",
                "IENS": "",
                "FIELDS": "",
                "FLAGS": "P",
                "MAX": str(limit),
                "FROM": "",
                "PART": "",
                "XREF": "B",
                "SCREEN": "",
                "ID": "",
            },
        )
        return [
            PackageDef(ien=row.ien, name=row.external_value)
            for row in parse_lister_response(raw)
        ]

    def get_package(self, ien: str) -> PackageDef | None:
        """Full PACKAGE detail: name + prefix + short description."""
        raw = self._broker.call(
            "DDR GETS ENTRY DATA",
            {
                "FILE": "9.4",
                "IENS": f"{ien},",
                "FIELDS": ".01;1;3.4",
                "FLAGS": "E",
            },
        )
        entries = parse_gets_response(_strip_data_header(raw))
        if not entries:
            return None

        name = prefix = short_desc = ""
        for e in entries:
            if e.field_number == 0.01:
                name = e.value
            elif e.field_number == 1.0:
                prefix = e.value
            elif abs(e.field_number - 3.4) < 1e-9:
                short_desc = e.value
        if not name:
            return None
        return PackageDef(
            ien=ien,
            name=name,
            prefix=prefix,
            short_description=short_desc,
        )

    def files_by_package(self, ien: str, *, limit: int = 500) -> list[float]:
        """Return the FileMan file numbers owned by one package.

        Walks subfile #9.4,4 (the FILE multiple). Each row's IEN in the
        subfile is a pointer-to-FILE; we return the float file numbers
        (the LISTER row's IEN, cast to float).
        """
        raw = self._broker.call(
            "DDR LISTER",
            {
                "FILE": "9.4",
                "IENS": f",{ien},",
                "FIELDS": "",
                "FLAGS": "P",
                "MAX": str(limit),
                "FROM": "",
                "PART": "",
                "XREF": "B",
                "SCREEN": "",
                "ID": "",
            },
        )
        out: list[float] = []
        for row in parse_lister_response(raw):
            try:
                out.append(float(row.ien))
            except ValueError:
                continue
        return out
