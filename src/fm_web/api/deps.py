"""FastAPI dependencies — session lookup + per-request services."""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status

from ..services import DataDictionaryService, EntryService, PackageService
from ..settings import Settings, get_settings
from .sessions import Session, SessionStore


def get_session_store(request: Request) -> SessionStore:
    """FastAPI dependency — returns the app-wide SessionStore."""
    return request.app.state.session_store


def get_current_session(
    session_id: Annotated[str | None, Cookie(alias="fm_web_session")] = None,
    store: Annotated[SessionStore, Depends(get_session_store)] = None,  # type: ignore[assignment]
) -> Session:
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="no session cookie — sign on at /api/session/signon",
        )
    session = store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session expired or invalid",
        )
    return session


SessionDep = Annotated[Session, Depends(get_current_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_dd_service(session: SessionDep) -> DataDictionaryService:
    return DataDictionaryService(session.broker)


def get_entry_service(session: SessionDep) -> EntryService:
    return EntryService(session.broker)


def get_package_service(session: SessionDep) -> PackageService:
    return PackageService(session.broker)


DDServiceDep = Annotated[DataDictionaryService, Depends(get_dd_service)]
EntryServiceDep = Annotated[EntryService, Depends(get_entry_service)]
PackageServiceDep = Annotated[PackageService, Depends(get_package_service)]
