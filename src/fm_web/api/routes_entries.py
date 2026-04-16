"""Entry routes — paginated list + single get."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..models import Entry, EntryPage
from .deps import EntryServiceDep

router = APIRouter(prefix="/api/files", tags=["entries"])


@router.get("/{file_number}/entries", response_model=EntryPage)
def list_entries(
    file_number: float,
    svc: EntryServiceDep,
    limit: int = 25,
    cursor: str = "",
) -> EntryPage:
    return svc.list_entries(file_number, limit=limit, cursor=cursor)


@router.get("/{file_number}/entries/{ien}", response_model=Entry)
def get_entry(
    file_number: float,
    ien: str,
    svc: EntryServiceDep,
    fields: str = "*",
) -> Entry:
    e = svc.get_entry(file_number, ien, fields=fields)
    if e is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"entry {ien} not found in file {file_number}",
        )
    return e
