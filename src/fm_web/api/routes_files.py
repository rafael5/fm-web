"""File routes — list files, get file, get field, list cross-refs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..models import CrossRefInfo, FieldDef, FileDef
from .deps import DDServiceDep

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("", response_model=list[FileDef])
def list_files(svc: DDServiceDep, limit: int = 200) -> list[FileDef]:
    return svc.list_files(limit=limit)


@router.get("/{file_number}", response_model=FileDef)
def get_file(file_number: float, svc: DDServiceDep) -> FileDef:
    f = svc.get_file(file_number)
    if f is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"file {file_number} not found",
        )
    return f


@router.get("/{file_number}/fields/{field_number}", response_model=FieldDef)
def get_field(file_number: float, field_number: float, svc: DDServiceDep) -> FieldDef:
    fd = svc.get_field(file_number, field_number)
    if fd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"field {field_number} not on file {file_number}",
        )
    return fd


@router.get("/{file_number}/xrefs", response_model=list[CrossRefInfo])
def list_cross_refs(file_number: float, svc: DDServiceDep) -> list[CrossRefInfo]:
    return svc.list_cross_refs(file_number)
