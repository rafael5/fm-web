"""Package routes — list, get, files-by-package."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..models import PackageDef
from .deps import PackageServiceDep

router = APIRouter(prefix="/api/packages", tags=["packages"])


@router.get("", response_model=list[PackageDef])
def list_packages(svc: PackageServiceDep, limit: int = 500) -> list[PackageDef]:
    return svc.list_packages(limit=limit)


@router.get("/{ien}", response_model=PackageDef)
def get_package(ien: str, svc: PackageServiceDep) -> PackageDef:
    p = svc.get_package(ien)
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"package {ien} not found",
        )
    return p


@router.get("/{ien}/files", response_model=list[float])
def files_by_package(ien: str, svc: PackageServiceDep) -> list[float]:
    return svc.files_by_package(ien)
