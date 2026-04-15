"""fm-web broker adapter — XWB NS-mode client, allow-list, fake.

Public surface::

    from fm_web.broker import VistARpcBroker, FakeRPCBroker
    from fm_web.broker import GetsEntry, ListerEntry
    from fm_web.broker.errors import (
        BrokerError, BrokerConnectionError, BrokerTimeout,
        BrokerHandshakeError, RpcDeniedError, AuthenticationError,
        FileManError, BrokerProtocolError,
    )

``VistARpcBroker`` talks to a real VistA over TCP. ``FakeRPCBroker``
is its in-memory twin for unit tests — same interface, no network.
"""

from .client import VistARpcBroker
from .fake import FakeRPCBroker, RecordedCall
from .responses import GetsEntry, ListerEntry

__all__ = [
    "FakeRPCBroker",
    "GetsEntry",
    "ListerEntry",
    "RecordedCall",
    "VistARpcBroker",
]
