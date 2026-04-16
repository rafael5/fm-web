"""Session routes — signon, signoff, me."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from ..broker import VistARpcBroker
from ..broker.errors import (
    AuthenticationError,
    BrokerConnectionError,
    BrokerHandshakeError,
)
from .deps import SessionDep, SettingsDep, get_session_store
from .sessions import SessionStore

router = APIRouter(prefix="/api/session", tags=["session"])


class SignonRequest(BaseModel):
    access: str
    verify: str
    site_id: str = "vehu"  # phase-2 per-site lookup; VEHU hard-coded for v1


class SessionInfo(BaseModel):
    duz: str
    user_name: str
    site_id: str
    uci: str
    app_context: str


def _make_broker(settings) -> VistARpcBroker:
    """Factory seam — overridden in tests via app.state.broker_factory."""
    return VistARpcBroker(
        host=settings.broker_host,
        port=settings.broker_port,
        timeout=settings.broker_timeout_seconds,
    )


@router.post(
    "/signon",
    response_model=SessionInfo,
    status_code=status.HTTP_200_OK,
)
def signon(
    request: Request,
    body: SignonRequest,
    response: Response,
    settings: SettingsDep,
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> SessionInfo:
    # Broker factory lives on app.state so tests can swap in FakeRPCBroker.
    factory = getattr(request.app.state, "broker_factory", None) or _make_broker
    broker = factory(settings)
    try:
        broker.connect(
            app=settings.broker_app_context,
            uci=settings.broker_uci,
        )
        duz = broker.signon(
            body.access,
            body.verify,
            app_context=settings.broker_app_context,
        )
    except (
        BrokerConnectionError,
        BrokerHandshakeError,
        AuthenticationError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    # Best-effort: pull user name from XUS GET USER INFO.
    user_name = ""
    try:
        info = broker.call("XUS GET USER INFO")
        lines = [ln for ln in info.split("\r\n") if ln]
        if len(lines) > 1:
            user_name = lines[1]
    except Exception:
        pass

    session = store.new(
        duz=duz,
        user_name=user_name,
        site_id=body.site_id,
        uci=settings.broker_uci,
        app_context=settings.broker_app_context,
        broker=broker,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session.session_id,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age_seconds,
    )
    return SessionInfo(
        duz=session.duz,
        user_name=session.user_name,
        site_id=session.site_id,
        uci=session.uci,
        app_context=session.app_context,
    )


@router.get("/me", response_model=SessionInfo)
def me(session: SessionDep) -> SessionInfo:
    return SessionInfo(
        duz=session.duz,
        user_name=session.user_name,
        site_id=session.site_id,
        uci=session.uci,
        app_context=session.app_context,
    )


@router.post("/signoff", status_code=status.HTTP_204_NO_CONTENT)
def signoff(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> Response:
    try:
        session.broker.signoff()
    except Exception:
        pass
    store.drop(session.session_id)
    response.delete_cookie(settings.session_cookie_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
