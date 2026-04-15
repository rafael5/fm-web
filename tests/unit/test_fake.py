"""FakeRPCBroker behavior — the fake we use everywhere else in unit tests."""

import pytest

from fm_web.broker import FakeRPCBroker
from fm_web.broker.errors import (
    AuthenticationError,
    BrokerConnectionError,
    BrokerHandshakeError,
    RpcDeniedError,
)


def test_connect_accepts_by_default():
    broker = FakeRPCBroker()
    ack = broker.connect(app="FM BROWSER", uci="VAH")
    assert ack == "accept"


def test_connect_can_reject():
    broker = FakeRPCBroker(accept_handshake=False)
    with pytest.raises(BrokerHandshakeError):
        broker.connect()


def test_call_before_connect_raises():
    broker = FakeRPCBroker(responses={"XUS SIGNON SETUP": "ok"})
    with pytest.raises(BrokerConnectionError):
        broker.call("XUS SIGNON SETUP")


def test_call_enforces_allowlist():
    broker = FakeRPCBroker()
    broker.connect()
    with pytest.raises(RpcDeniedError):
        broker.call("DDR FILER")  # writing RPC — always denied


def test_call_records_invocation():
    broker = FakeRPCBroker(responses={"XUS SIGNON SETUP": "hi"})
    broker.connect()
    broker.call("XUS SIGNON SETUP")
    broker.call("DDR LISTER", "2", "", "", "25", "", "0", "", "B", "", "")
    names = [c.rpc_name for c in broker.calls]
    assert names == ["XUS SIGNON SETUP", "DDR LISTER"]


def test_list_param_key_distinguishes_calls():
    broker = FakeRPCBroker(
        responses={
            (
                "DDR GETS ENTRY DATA",
                (
                    ("FIELDS", ".01"),
                    ("FILE", "2"),
                    ("FLAGS", "E"),
                    ("IENS", "1,"),
                ),
            ): "2^1,^.01^ALICE\r\n",
        }
    )
    broker.connect()
    entries = broker.gets_entry_data(2, "1", fields=".01", flags="E")
    assert len(entries) == 1
    assert entries[0].value == "ALICE"


def test_signon_success_returns_duz():
    broker = FakeRPCBroker(
        responses={"XUS SIGNON SETUP": "hello"},
        signon_duz="2001",
    )
    broker.connect()
    assert broker.signon("fakedoc1", "1Doc!@#$") == "2001"


def test_signon_zero_duz_raises():
    broker = FakeRPCBroker(signon_duz="0")
    broker.connect()
    with pytest.raises(AuthenticationError):
        broker.signon("bad", "bad")


def test_signon_enforces_av_code_allowlist():
    # Meta-invariant: the fake's signon still runs require_allowed,
    # so tampering with the allow-list (removing XUS AV CODE) would
    # break tests — defensive.
    broker = FakeRPCBroker(signon_duz="1")
    broker.connect()
    # Sanity: this must succeed today.
    broker.signon("u", "v")
    # The second .call() in .signon is accounted for via _calls below.
    names = [c.rpc_name for c in broker.calls]
    assert "XUS SIGNON SETUP" in names
    assert "XUS AV CODE" in names


def test_signon_redacts_verify_in_call_log():
    broker = FakeRPCBroker(signon_duz="1")
    broker.connect()
    broker.signon("fakedoc1", "SECRET")
    av = next(c for c in broker.calls if c.rpc_name == "XUS AV CODE")
    # access code is retained for audit; verify is replaced with ****
    assert av.params == ("fakedoc1/****",)


def test_context_manager_closes():
    broker = FakeRPCBroker()
    with broker as b:
        b.connect()
    # After context exit, connection closed — further calls raise.
    with pytest.raises(BrokerConnectionError):
        broker.call("DDR LISTER", "2", "", "", "1", "", "0", "", "B", "", "")


def test_empty_response_for_unregistered_rpc():
    # Tests the fallback — not an error; services layer decides what to do
    # with an empty string.
    broker = FakeRPCBroker()
    broker.connect()
    assert broker.call("ORWU DT") == ""
