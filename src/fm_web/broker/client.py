"""VistA RPC Broker client — the one that talks to real sockets.

Every call passes through :func:`require_allowed` before any bytes hit
the wire. This is fm-web's read-only security boundary.

The ``_send_recv`` method is an explicit seam: unit tests substitute it
to exercise packet-building and response-handling without opening a
socket.
"""

from __future__ import annotations

import logging
import socket
from typing import Self

from . import crypt
from .allowlist import require_allowed
from .errors import (
    AuthenticationError,
    BrokerConnectionError,
    BrokerHandshakeError,
    BrokerTimeout,
)
from .responses import (
    GetsEntry,
    ListerEntry,
    parse_finder_response,
    parse_gets_response,
    parse_lister_response,
)
from .wire import (
    EOT,
    NUL,
    build_connect_packet,
    build_rpc_packet,
    parse_response,
)

log = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9430
# "OR CPRS GUI CHART" is the standard broker-authorized option that
# ships on every VistA with CPRS. We use it (rather than inventing a
# fm-web-specific context) so no server-side install is required.
# See LESSONS-LEARNED L32.
DEFAULT_APP = "OR CPRS GUI CHART"
DEFAULT_UCI = "VAH"
DEFAULT_TIMEOUT = 10.0
RECV_SIZE = 8192


class VistARpcBroker:
    """Blocking TCP client for the VistA XWB broker (NS mode).

    Lifecycle::

        with VistARpcBroker(host="localhost", port=9430) as broker:
            broker.connect(app="FM BROWSER", uci="VAH")
            broker.call("XUS SIGNON SETUP")
            duz = broker.signon("fakedoc1", "1Doc!@#$")
            entries = broker.list_entries(2, max_entries=5)
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._sock: socket.socket | None = None

    # ---------------- lifecycle ---------------------------------------

    def connect(
        self,
        app: str = DEFAULT_APP,
        uci: str = DEFAULT_UCI,
    ) -> str:
        """Open TCP, perform the NS-mode handshake, return the ack text."""
        try:
            self._sock = socket.create_connection(
                (self._host, self._port), timeout=self._timeout
            )
        except (OSError, socket.timeout) as exc:
            raise BrokerConnectionError(
                f"connect to {self._host}:{self._port} failed: {exc}"
            ) from exc
        pkt = build_connect_packet(app, uci)
        raw = self._send_recv(pkt)
        ack = raw.rstrip(EOT).lstrip(NUL).decode("latin-1", errors="replace")
        log.debug("broker handshake: %r", ack)
        if "accept" not in ack:
            self.close()
            raise BrokerHandshakeError(f"broker rejected connection: {ack!r}")
        return ack

    def close(self) -> None:
        """Send BYE (best-effort) and close the socket."""
        if self._sock is None:
            return
        try:
            self._sock.sendall(build_rpc_packet("#BYE#", []))
        except OSError:
            pass
        finally:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ---------------- RPC execution -----------------------------------

    def call(self, rpc_name: str, *params: str | dict[str, str]) -> str:
        """Execute an allow-listed RPC and return the response text.

        Raises
        ------
        RpcDeniedError
            If the RPC is not in the allow-list. No bytes sent.
        BrokerConnectionError
            If called before :meth:`connect` or after :meth:`close`.
        BrokerProtocolError
            If the response carries an M-error marker.
        """
        require_allowed(rpc_name)
        if self._sock is None:
            raise BrokerConnectionError("not connected — call connect() before call()")
        pkt = build_rpc_packet(rpc_name, list(params))
        raw = self._send_recv(pkt)
        log.debug("rpc %r → %d bytes", rpc_name, len(raw))
        return parse_response(raw)

    # ---------------- high-level helpers ------------------------------

    def signon(
        self,
        access_code: str,
        verify_code: str,
        app_context: str | None = None,
    ) -> str:
        """Run SIGNON SETUP + AV CODE + CREATE CONTEXT; return DUZ.

        Three RPCs in order:

        1. ``XUS SIGNON SETUP`` — reads the sign-on screen text.
        2. ``XUS AV CODE`` — sends XUSRB1-encrypted ``ACCESS;VERIFY``.
           Success means DUZ > 0.
        3. ``XWB CREATE CONTEXT`` — switches the broker's active
           option from the default ``XUS SIGNON`` context to a real
           application context (default ``OR CPRS GUI CHART``).
           Without this step, every subsequent DDR* / ORWU call
           returns ``"Application context has not been created!"``.
           See LESSONS-LEARNED L33 for the discovery trace.

        ``app_context`` overrides the default (``OR CPRS GUI CHART``)
        — useful if a site has a different context set up for
        read-only browser tools.
        """
        self.call("XUS SIGNON SETUP")
        plaintext = f"{access_code};{verify_code}"
        ciphertext = crypt.encrypt(plaintext)
        result = self.call("XUS AV CODE", ciphertext)
        duz_line = result.split("\r\n", 1)[0].strip()
        try:
            duz = int(duz_line)
        except ValueError:
            raise AuthenticationError(
                f"XUS AV CODE returned non-numeric DUZ: {result!r}"
            )
        if duz <= 0:
            raise AuthenticationError(f"authentication failed (DUZ={duz}): {result!r}")
        # Switch broker context. OPTION name is encrypted via the same
        # XUSRB1 cipher the server uses for decryption (DECRYP^XUSRB1).
        ctx = app_context or DEFAULT_APP
        ctx_encrypted = crypt.encrypt(ctx)
        ctx_result = self.call("XWB CREATE CONTEXT", ctx_encrypted)
        if ctx_result and "does not exist" in ctx_result:
            raise AuthenticationError(
                f"app context {ctx!r} not found on server: {ctx_result!r}"
            )
        return duz_line

    def signoff(self) -> None:
        """Call XUS SIGNOFF (best-effort) and close."""
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
        """``DDR GETS ENTRY DATA`` → typed entries. External form by default."""
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
        """``DDR LISTER`` → typed entries."""
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
        """``DDR FIND1`` → a single IEN (``""`` if not found)."""
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
        """``DDR FINDER`` → list of IEN strings."""
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

    # ---------------- test seam ---------------------------------------

    def _send_recv(self, pkt: bytes) -> bytes:
        """Send ``pkt`` and block until EOT arrives. Socket-level I/O.

        Unit tests monkeypatch this to supply canned response bytes
        without opening a socket.
        """
        if self._sock is None:
            raise BrokerConnectionError("socket is not open")
        try:
            self._sock.sendall(pkt)
        except OSError as exc:
            raise BrokerConnectionError(f"send failed: {exc}") from exc
        data = b""
        while not data.endswith(EOT):
            try:
                chunk = self._sock.recv(RECV_SIZE)
            except socket.timeout as exc:
                raise BrokerTimeout(f"no response within {self._timeout}s") from exc
            except OSError as exc:
                raise BrokerConnectionError(f"recv failed: {exc}") from exc
            if not chunk:
                break
            data += chunk
        return data


def _fmt_file_num(n: int | float) -> str:
    """FileMan file numbers: integer → ``"2"``, decimal → ``"50.68"``."""
    return str(int(n)) if n == int(n) else str(n)
