"""Typed broker exceptions.

Every failure in the broker adapter raises one of these. The FastAPI
error handler middleware maps them to HTTP status codes and user-safe
messages — callers at the service layer can distinguish "the network
went away" from "the RPC wasn't in the allow-list" without string
sniffing.
"""


class BrokerError(Exception):
    """Base class — never raise this directly."""


class BrokerConnectionError(BrokerError):
    """TCP connect failed, socket died, or recv returned empty."""


class BrokerTimeout(BrokerError):
    """Server did not respond within the configured timeout."""


class BrokerHandshakeError(BrokerError):
    """NS-mode handshake was rejected (bad app context, bad UCI, etc.)."""


class RpcDeniedError(BrokerError):
    """A caller attempted an RPC outside the read-only allow-list.

    This is the security boundary for fm-web. Raising this means the
    allow-list did its job — the attempt should be logged and the call
    never reaches the wire.
    """


class AuthenticationError(BrokerError):
    """``XUS AV CODE`` returned a non-positive DUZ."""


class FileManError(BrokerError):
    """FileMan returned an error structure in ``^TMP("DIERR", …)``.

    ``errors`` is a list of ``(code, message)`` tuples parsed from the
    DIERR payload.
    """

    def __init__(self, message: str, errors: list[tuple[str, str]] | None = None):
        super().__init__(message)
        self.errors = errors or []


class BrokerProtocolError(BrokerError):
    """Wire-level decoding failed — the response was not a valid NS-mode
    envelope. Usually indicates a server-side M error the server itself
    did not wrap."""
