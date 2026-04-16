"""FastAPI app factory.

Creates a fresh FastAPI instance per call — tests use this to build
isolated apps with swapped-in ``broker_factory``. Production runs
``fm_web.api.app:app`` (the module-level default instance below).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..settings import get_settings
from .routes_entries import router as entries_router
from .routes_files import router as files_router
from .routes_packages import router as packages_router
from .routes_session import router as session_router
from .sessions import SessionStore


def create_app(settings=None) -> FastAPI:
    s = settings or get_settings()
    app = FastAPI(
        title="fm-web",
        description=(
            "Read-only React/FastAPI browser for VistA FileMan data "
            "dictionary and contents, via ship-with-VistA DDR* RPCs."
        ),
        version="0.1.0",
    )

    # CORS — Vite dev server on :5173 by default
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    # Session store lives on app.state; tests can pre-populate it.
    app.state.session_store = SessionStore(max_age_seconds=s.session_max_age_seconds)

    # Broker factory seam — tests swap in FakeRPCBroker-returning factory.
    app.state.broker_factory = None

    @app.get("/api/health", tags=["health"])
    def health():
        return {"status": "ok", "sessions": len(app.state.session_store)}

    app.include_router(session_router)
    app.include_router(files_router)
    app.include_router(entries_router)
    app.include_router(packages_router)

    return app


# Module-level default — what uvicorn loads in production.
app = create_app()
