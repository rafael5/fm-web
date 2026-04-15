"""VistARpcBroker — real client, tested via the ``_send_recv`` seam.

These tests do not open a socket. They substitute ``_send_recv`` with
a callable that returns canned envelope bytes, letting us verify that:

1. Allow-list enforcement blocks denied RPCs before the seam fires.
2. Handshake success/failure paths work.
3. Packet construction is correct (the bytes sent into ``_send_recv``
   are the bytes the wire spec demands).
4. Response parsing feeds the right typed result back.

Live socket behavior is covered separately by integration tests against
VEHU (``pytest -m integration``).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from fm_web.broker.client import VistARpcBroker
from fm_web.broker.errors import (
    BrokerConnectionError,
    BrokerHandshakeError,
    RpcDeniedError,
)
from fm_web.broker.wire import EOT


def _seam(responses: list[bytes]) -> Callable[[bytes], bytes]:
    """Build a _send_recv replacement that returns queued responses in order.

    Records the packets sent via the closure's ``sent`` list attribute.
    """
    sent: list[bytes] = []
    it = iter(responses)

    def send_recv(pkt: bytes) -> bytes:
        sent.append(pkt)
        try:
            return next(it)
        except StopIteration:
            raise AssertionError("more RPC calls than canned responses")

    send_recv.sent = sent  # type: ignore[attr-defined]
    return send_recv


def _wrap(text: str) -> bytes:
    """Envelope: \\x00\\x00 + text + EOT — what a real server returns."""
    return b"\x00\x00" + text.encode("latin-1") + EOT


def _attach(broker: VistARpcBroker, sendrecv: Callable[[bytes], bytes]) -> None:
    """Put the broker into a 'connected' state with a fake seam.

    We bypass socket.create_connection by setting _sock to a sentinel
    truthy object and replacing _send_recv. The sentinel just has to be
    non-None for the connection guard.
    """
    broker._sock = object()  # type: ignore[assignment]
    broker._send_recv = sendrecv  # type: ignore[method-assign]


class TestConnect:
    def test_accepts_handshake(self):
        broker = VistARpcBroker()
        seam = _seam([_wrap("accept")])
        # Short-circuit socket.create_connection via monkey
        import socket as _socket

        class _FakeSock:
            def close(self):
                pass

            def sendall(self, _):
                pass

        orig = _socket.create_connection
        _socket.create_connection = lambda *a, **kw: _FakeSock()  # type: ignore[assignment]
        try:
            broker._send_recv = seam  # type: ignore[method-assign]
            ack = broker.connect(app="FM BROWSER", uci="VAH")
            assert "accept" in ack
            # One packet sent — the handshake.
            assert len(seam.sent) == 1  # type: ignore[attr-defined]
            assert seam.sent[0].startswith(b"[XWB]1030")  # type: ignore[attr-defined]
        finally:
            _socket.create_connection = orig  # type: ignore[assignment]

    def test_rejects_handshake(self):
        broker = VistARpcBroker()
        seam = _seam([_wrap("reject: bad UCI")])
        import socket as _socket

        class _FakeSock:
            def close(self):
                pass

            def sendall(self, _):
                pass

        orig = _socket.create_connection
        _socket.create_connection = lambda *a, **kw: _FakeSock()  # type: ignore[assignment]
        try:
            broker._send_recv = seam  # type: ignore[method-assign]
            with pytest.raises(BrokerHandshakeError) as exc:
                broker.connect()
            assert "reject" in str(exc.value)
        finally:
            _socket.create_connection = orig  # type: ignore[assignment]


class TestCallAllowlist:
    def test_denied_rpc_raises_before_seam(self):
        broker = VistARpcBroker()
        # No seam attached — if allow-list fails open, we'd hit it.
        with pytest.raises(RpcDeniedError):
            broker.call("DDR FILER", "anything")

    def test_call_without_connect_raises(self):
        broker = VistARpcBroker()
        with pytest.raises(BrokerConnectionError):
            broker.call("DDR LISTER", "2", "", "", "1", "", "0", "", "B", "", "")


class TestCallPacketConstruction:
    def test_literal_params_encoded(self):
        broker = VistARpcBroker()
        seam = _seam([_wrap("1\r\n1^ALICE\r\n")])
        _attach(broker, seam)
        broker.list_entries(2, max_entries=25)
        sent = seam.sent[0]  # type: ignore[attr-defined]
        assert sent.startswith(b"[XWB]1030")
        assert b"DDR LISTER" in sent
        assert b"00225" in sent  # lread("25") = b"002" + b"25"

    def test_gets_entry_data_uses_list_param(self):
        broker = VistARpcBroker()
        seam = _seam([_wrap("2^1,^.01^ALICE\r\n")])
        _attach(broker, seam)
        broker.gets_entry_data(2, "1", fields=".01", flags="E")
        sent = seam.sent[0]  # type: ignore[attr-defined]
        # List-type param subscript strings are M-quoted
        assert b'"FILE"' in sent
        assert b'"IENS"' in sent
        assert b"1," in sent  # IENS value has trailing comma


class TestResponseParsing:
    def test_list_entries_parses_lister_response(self):
        broker = VistARpcBroker()
        seam = _seam([_wrap("2\r\n1^ALICE\r\n2^BOB\r\n")])
        _attach(broker, seam)
        entries = broker.list_entries(2, max_entries=2)
        assert [e.ien for e in entries] == ["1", "2"]
        assert [e.external_value for e in entries] == ["ALICE", "BOB"]

    def test_gets_entry_data_parses_response(self):
        broker = VistARpcBroker()
        seam = _seam([_wrap("2^1,^.01^ALICE\r\n2^1,^.02^M\r\n")])
        _attach(broker, seam)
        entries = broker.gets_entry_data(2, "1")
        assert {e.field_number for e in entries} == {0.01, 0.02}

    def test_find1_returns_ien_string(self):
        broker = VistARpcBroker()
        seam = _seam([_wrap("42\r\n")])
        _attach(broker, seam)
        assert broker.find1(2, "WASHINGTON,GEORGE") == "42"

    def test_finder_parses_ien_list(self):
        broker = VistARpcBroker()
        seam = _seam([_wrap("3\r\n1\r\n2\r\n3\r\n")])
        _attach(broker, seam)
        assert broker.finder(2, "ALI", flags="M") == ["1", "2", "3"]
