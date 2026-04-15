"""Read-only RPC allow-list.

The security boundary of fm-web. Every RPC call that leaves the process
passes through :func:`require_allowed` first. Attempts to call an RPC
not on the list raise :class:`RpcDeniedError` without ever touching the
socket.

The list is hand-curated: each entry has an RPC name, the underlying
FileMan/Kernel entry point it wraps, and a short purpose. Adding a new
RPC requires a code change — this is deliberate.

See ARCHITECTURE.md §4.1 for the full rationale.
"""

from dataclasses import dataclass

from .errors import RpcDeniedError


@dataclass(frozen=True, slots=True)
class AllowedRpc:
    """One allow-listed RPC.

    Attributes
    ----------
    name:
        The RPC name as registered in VistA (e.g. ``"DDR LISTER"``).
    wraps:
        The underlying M entry point or subroutine, for documentation.
    purpose:
        One-line description of what fm-web uses it for.
    """

    name: str
    wraps: str
    purpose: str


# The v1 allow-list. Add to this list only with review. Every name must
# correspond to an RPC that already ships with VistA — do not invent
# new RPCs; doing so would require a KIDS build and break the project's
# non-invasive guarantee.
ALLOWED_RPCS: tuple[AllowedRpc, ...] = (
    AllowedRpc(
        "XUS SIGNON SETUP",
        "SIGNON^XUSRB",
        "Pre-auth intro; returns sign-on screen text.",
    ),
    AllowedRpc(
        "XUS AV CODE",
        "AVCODE^XUSRB",
        "Authenticate ACCESS/VERIFY; returns DUZ.",
    ),
    AllowedRpc(
        "XUS GET USER INFO",
        "GETUSRINFO^XUSRB4",
        "Post-auth metadata: DUZ, name, division, title.",
    ),
    AllowedRpc(
        "XUS SIGNOFF",
        "SIGNOFF^XUSRB",
        "Clean session termination.",
    ),
    AllowedRpc(
        "DDR LISTER",
        "LIST^DIC",
        "List entries from a FileMan file with selected fields.",
    ),
    AllowedRpc(
        "DDR FINDER",
        "FIND^DIC",
        "Search by cross-reference; returns matching IENs.",
    ),
    AllowedRpc(
        "DDR FIND1",
        "FIND1^DIC",
        "Single-match lookup by exact cross-reference value.",
    ),
    AllowedRpc(
        "DDR GETS ENTRY DATA",
        "GETS^DIQ",
        "Fetch field values by IEN in external or internal format.",
    ),
    # NOTE: DDR GET DD and DDR GET DD HASH were initially included but
    # empirically DO NOT EXIST on the VEHU (yottadb/octo-vehu) broker —
    # the server replies "Remote Procedure 'DDR GET DD' doesn't exist on
    # the server." They are not universal across VistA distributions. DD
    # browsing is instead implemented via DDR LISTER + DDR GETS ENTRY
    # DATA against file #1 (the FILE registry) and its FIELD subfile.
    # See tests/contract/fixtures/ddr_get_dd__patient_AL.json for the
    # rejection response shape, and LESSONS-LEARNED L31. Do not re-add
    # without verifying availability on each target site.
    AllowedRpc(
        "ORWU DT",
        "$$DT^DICRW",
        "Current FileMan date on the server — environment probe.",
    ),
    AllowedRpc(
        "XWB IM HERE",
        "(Kernel broker keepalive)",
        "Session keepalive; prevents idle timeout on long reads.",
    ),
)


# O(1) lookup set
_ALLOWED_NAMES: frozenset[str] = frozenset(a.name for a in ALLOWED_RPCS)


def is_allowed(rpc_name: str) -> bool:
    """True iff ``rpc_name`` is in the allow-list. Case-sensitive."""
    return rpc_name in _ALLOWED_NAMES


def require_allowed(rpc_name: str) -> None:
    """Raise :class:`RpcDeniedError` if ``rpc_name`` is not allow-listed.

    This is the single point of enforcement. Every code path that builds
    an RPC packet must call this first.
    """
    if rpc_name not in _ALLOWED_NAMES:
        raise RpcDeniedError(
            f"RPC {rpc_name!r} is not in the fm-web allow-list. "
            f"The allow-list is the read-only boundary — add with review only."
        )
