"""Sanity tests for the typed broker exceptions."""

import pytest

from fm_web.broker.errors import (
    AuthenticationError,
    BrokerConnectionError,
    BrokerError,
    BrokerHandshakeError,
    BrokerProtocolError,
    BrokerTimeout,
    FileManError,
    RpcDeniedError,
)


def test_all_derive_from_BrokerError():
    for cls in (
        BrokerConnectionError,
        BrokerTimeout,
        BrokerHandshakeError,
        RpcDeniedError,
        AuthenticationError,
        FileManError,
        BrokerProtocolError,
    ):
        assert issubclass(cls, BrokerError)


def test_fileman_error_carries_parsed_errors():
    err = FileManError("bad", errors=[("202", "missing required field"), ("305", "x")])
    assert err.errors == [("202", "missing required field"), ("305", "x")]


def test_fileman_error_default_errors_is_empty():
    err = FileManError("no details")
    assert err.errors == []


def test_rpc_denied_is_distinct_from_handshake():
    with pytest.raises(RpcDeniedError):
        raise RpcDeniedError("denied")
    # Must NOT be caught as a handshake error — they are different failures.
    try:
        raise RpcDeniedError("denied")
    except BrokerHandshakeError:
        pytest.fail("RpcDeniedError caught as BrokerHandshakeError")
    except RpcDeniedError:
        pass
