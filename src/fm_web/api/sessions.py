"""Server-side session store: session_id → BrokerConnection.

fm-web sessions are stateful: each signed-on user has an open broker
TCP connection held on the server. The client carries only a signed
cookie with an opaque session_id. This keeps ACCESS/VERIFY secrets
off the wire after the initial signon.

The store is process-local (a dict). For single-process deployment
that's sufficient. Multi-process scaling (e.g. multiple uvicorn
workers behind a proxy) would need sticky sessions or a shared
external store; both are deferred to phase 7 hardening.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from threading import RLock


@dataclass
class Session:
    """One signed-on broker session.

    ``broker`` is the live :class:`VistARpcBroker` (or
    :class:`FakeRPCBroker` in tests). ``duz`` / ``user_name`` /
    ``uci`` / ``app_context`` are captured at signon for display.
    """

    session_id: str
    duz: str
    user_name: str
    site_id: str
    uci: str
    app_context: str
    broker: object
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active_at = time.time()


class SessionStore:
    """In-memory session registry."""

    def __init__(self, max_age_seconds: int = 900) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = RLock()
        self._max_age = max_age_seconds

    def new(
        self,
        *,
        duz: str,
        user_name: str,
        site_id: str,
        uci: str,
        app_context: str,
        broker: object,
    ) -> Session:
        sid = secrets.token_urlsafe(32)
        session = Session(
            session_id=sid,
            duz=duz,
            user_name=user_name,
            site_id=site_id,
            uci=uci,
            app_context=app_context,
            broker=broker,
        )
        with self._lock:
            self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Return a session if it exists and is not expired; else None.

        Side-effect: refreshes ``last_active_at`` on successful lookup
        (idle-timeout semantics).
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if time.time() - session.last_active_at > self._max_age:
                self._sessions.pop(session_id, None)
                return None
            session.touch()
            return session

    def drop(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.pop(session_id, None)

    def reap_expired(self) -> int:
        """Drop expired sessions. Returns count reaped.

        Called on a timer by the app lifespan; also safe to call ad-hoc.
        """
        now = time.time()
        with self._lock:
            stale = [
                sid
                for sid, s in self._sessions.items()
                if now - s.last_active_at > self._max_age
            ]
            for sid in stale:
                self._sessions.pop(sid, None)
            return len(stale)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)
