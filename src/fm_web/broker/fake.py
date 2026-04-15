"""FakeRPCBroker — in-memory substitute for :class:`VistARpcBroker`.

Real fake, not a mock: same public interface, no socket, deterministic
responses from a registry. Unit tests and service-layer tests consume
it exactly like the real broker. Contract tests assert that recorded
responses from a real VEHU broker produce the same high-level results
through the fake as through the live client.

Usage::

    responses = {
        "XUS SIGNON SETUP": "Welcome to VEHU\\r\\n",
        ("DDR GETS ENTRY DATA", (("FILE", "2"), ("IENS", "1,"))):
            "2^1,^.01^WASHINGTON,GEORGE\\r\\n",
    }
    broker = FakeRPCBroker(responses=responses)
    broker.connect(app="FM BROWSER", uci="VAH")
    broker.signon("fakedoc1", "1Doc!@#$")
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self

from .allowlist import require_allowed
from .errors import (
    AuthenticationError,
    BrokerConnectionError,
    BrokerHandshakeError,
)
from .responses import (
    GetsEntry,
    ListerEntry,
    parse_finder_response,
    parse_gets_response,
    parse_lister_response,
)

ResponseKey = str | tuple[str, tuple[tuple[str, str], ...]]


@dataclass(slots=True)
class RecordedCall:
    """One invocation observed by :class:`FakeRPCBroker`.

    Tests inspect the call history to assert allow-list compliance,
    parameter shape, ordering, etc.
    """

    rpc_name: str
    params: tuple[str | dict[str, str], ...]


class FakeRPCBroker:
    """Drop-in replacement for :class:`VistARpcBroker` in unit tests.

    Responses are looked up by the RPC name alone, or — for DDR RPCs
    that pass a list param — by ``(rpc_name, frozen_items)`` tuple so a
    test can distinguish ``DDR GETS ENTRY DATA`` calls for different
    files/IENs.

    The allow-list is enforced exactly as in :class:`VistARpcBroker`.
    Attempting to call a denied RPC raises :class:`RpcDeniedError`
    before the response map is consulted.
    """

    def __init__(
        self,
        responses: dict[ResponseKey, str] | None = None,
        *,
        accept_handshake: bool = True,
        signon_duz: str = "42",
    ) -> None:
        self._responses: dict[ResponseKey, str] = dict(responses or {})
        self._calls: list[RecordedCall] = []
        self._connected: bool = False
        self._accept_handshake: bool = accept_handshake
        self._signon_duz: str = signon_duz

    # ---------------- introspection -----------------------------------

    @property
    def calls(self) -> list[RecordedCall]:
        return list(self._calls)

    def register(self, key: ResponseKey, response: str) -> None:
        """Add or overwrite a canned response."""
        self._responses[key] = response

    # ---------------- lifecycle ---------------------------------------

    def connect(self, app: str = "FM BROWSER", uci: str = "VAH") -> str:
        if not self._accept_handshake:
            raise BrokerHandshakeError(f"handshake rejected (app={app}, uci={uci})")
        self._connected = True
        return "accept"

    def close(self) -> None:
        self._connected = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ---------------- RPC execution -----------------------------------

    def call(self, rpc_name: str, *params: str | dict[str, str]) -> str:
        require_allowed(rpc_name)
        if not self._connected:
            raise BrokerConnectionError("not connected — call connect() first")
        self._calls.append(RecordedCall(rpc_name=rpc_name, params=tuple(params)))
        key = _make_key(rpc_name, params)
        if key in self._responses:
            return self._responses[key]
        if rpc_name in self._responses:
            return self._responses[rpc_name]
        return ""

    # ---------------- high-level helpers (parallel to real client) ----

    def signon(self, access_code: str, verify_code: str) -> str:
        self.call("XUS SIGNON SETUP")
        # Enforce allow-list on AV CODE even though we don't hit the wire.
        require_allowed("XUS AV CODE")
        if not self._connected:
            raise BrokerConnectionError("not connected — call connect() first")
        # Obscure the verify code in the call record — access is fine for logs.
        self._calls.append(
            RecordedCall(rpc_name="XUS AV CODE", params=(f"{access_code}/****",))
        )
        if self._signon_duz == "" or self._signon_duz == "0":
            raise AuthenticationError(
                f"authentication failed (DUZ={self._signon_duz!r})"
            )
        try:
            duz = int(self._signon_duz)
        except ValueError:
            raise AuthenticationError(f"non-numeric DUZ: {self._signon_duz!r}")
        if duz <= 0:
            raise AuthenticationError(f"non-positive DUZ: {duz}")
        return self._signon_duz

    def signoff(self) -> None:
        try:
            self.call("XUS SIGNOFF")
        finally:
            self.close()

    def gets_entry_data(
        self,
        file_number: int | float,
        ien: str,
        *,
        fields: str = "*",
        flags: str = "E",
    ) -> list[GetsEntry]:
        fn = _fmt_file_num(file_number)
        iens = ien if ien.endswith(",") else f"{ien},"
        raw = self.call(
            "DDR GETS ENTRY DATA",
            {"FILE": fn, "IENS": iens, "FIELDS": fields, "FLAGS": flags},
        )
        return parse_gets_response(raw)

    def list_entries(
        self,
        file_number: int | float,
        *,
        xref: str = "B",
        value: str = "",
        from_value: str = "",
        part: bool = False,
        max_entries: int = 44,
        screen: str = "",
        identifier: str = "",
        fields: str = "",
        flags: str = "P",
    ) -> list[ListerEntry]:
        fn = _fmt_file_num(file_number)
        raw = self.call(
            "DDR LISTER",
            fn,
            fields,
            flags,
            str(max_entries),
            from_value,
            "1" if part else "0",
            value,
            xref,
            screen,
            identifier,
        )
        return parse_lister_response(raw)

    def find1(
        self,
        file_number: int | float,
        value: str,
        *,
        xref: str = "B",
        screen: str = "",
    ) -> str:
        fn = _fmt_file_num(file_number)
        return self.call("DDR FIND1", fn, value, xref, screen).strip()

    def finder(
        self,
        file_number: int | float,
        value: str,
        *,
        xref: str = "B",
        screen: str = "",
        flags: str = "",
        max_entries: int = 44,
    ) -> list[str]:
        fn = _fmt_file_num(file_number)
        raw = self.call(
            "DDR FINDER",
            fn,
            xref,
            "",
            "1",
            value,
            str(max_entries),
            screen,
            flags,
        )
        return parse_finder_response(raw)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _make_key(rpc_name: str, params: Iterable[str | dict[str, str]]) -> ResponseKey:
    """Build a lookup key that distinguishes DDR list-param calls.

    For RPCs called with a dict param (the list-type array pattern),
    the key is ``(rpc_name, tuple of sorted items)``. For simple
    literal params the key is just the RPC name.
    """
    for p in params:
        if isinstance(p, dict):
            return (rpc_name, tuple(sorted(p.items())))
    return rpc_name


def _fmt_file_num(n: int | float) -> str:
    return str(int(n)) if n == int(n) else str(n)
