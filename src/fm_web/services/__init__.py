"""fm-web service layer — pure Python, broker-agnostic.

Services are stateless classes that take a connected broker
(``VistARpcBroker`` or ``FakeRPCBroker``) at construction and expose
typed, domain-model returns. They never touch HTTP, never open
sockets themselves; all I/O goes through the broker.

The API layer (``fm_web.api``) wires sessions → brokers → services
per request.
"""

from .data_dictionary import DataDictionaryService
from .entries import EntryService
from .packages import PackageService

__all__ = ["DataDictionaryService", "EntryService", "PackageService"]
