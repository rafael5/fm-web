"""XWB NS-mode wire codec — pure functions, no socket, no state.

Spec derived from VistA's XWBPRS.m / XWBTCPMT.m. Everything in this
module is a side-effect-free transformation between Python values and
bytes on the wire. Network I/O lives in :mod:`fm_web.broker.client`;
high-level sign-on flow lives there too.

Protocol summary
----------------
Every packet starts with ``[XWB]`` followed by a 4-byte ``PRSP`` header
describing the framing parameters. The header fm-web uses is
``1030`` — ``ver=1 type=0 lenv=3 rt=0``.

Two length encodings share the wire:

``SREAD`` (``S`` = short)
    1-byte ASCII length prefix + value. Used for chunk-type bytes,
    RPC names, etc. Max value length 255.

``LREAD`` (``L`` = long)
    ``lenv``-digit decimal length prefix + value. With ``lenv=3`` as in
    the PRSP we use, max length is 999.

Chunks are keyed by a single ASCII digit:

    ``1`` (PRS1): version + return_type — both SREAD.
    ``2`` (PRS2): rpc_version + rpc_name — both SREAD.
    ``4`` (PRS4): a command string — SREAD.
    ``5`` (PRS5): a parameter list, terminated by EOT (``\\x04``). Each
         parameter begins with a TY byte:
           ``"0"`` — literal string, then LREAD(value), then a CONT byte
                    (``"f"`` means "end of this param").
           ``"2"`` — list-type (a local M array). Pairs of LREAD(subscript)
                    + LREAD(value), each followed by ``"t"`` (more pairs)
                    or ``"f"`` (last pair in this list).
           ``"4"`` — empty parameter.
           ``\\x04`` — end of all parameters.

The TY byte is an ASCII digit character, **not** ``chr(0)``. PRS5's
check ``IF TY=0`` is an M string comparison, which MUMPS evaluates by
coercing both sides to numbers — only the literal string ``"0"``
matches.

Response envelope
-----------------
The server sends ``\\x00\\x00 {content} \\x04``. Two leading NUL bytes
are stripped; trailing EOT is stripped. M errors arrive as
``\\x18M  ERROR=...`` and are raised as :class:`BrokerProtocolError`.
"""

from __future__ import annotations

from .errors import BrokerProtocolError

EOT: bytes = b"\x04"
NUL: bytes = b"\x00"

# PRSP header: ver=1, type=0, lenv=3, rt=0
PRSP: bytes = b"1030"
MAGIC: bytes = b"[XWB]"


# ---------------------------------------------------------------------
# Length-prefix encoders
# ---------------------------------------------------------------------


def sread(s: str) -> bytes:
    """Encode ``s`` with a 1-byte ASCII length prefix (SREAD).

    >>> sread("ABC")
    b'\\x03ABC'
    """
    b = s.encode("latin-1")
    assert len(b) < 256, f"sread value too long ({len(b)} bytes): {s!r}"
    return bytes([len(b)]) + b


def lread(s: str) -> bytes:
    """Encode ``s`` with a 3-digit decimal length prefix (LREAD, lenv=3).

    >>> lread("PATIENT")
    b'007PATIENT'
    """
    b = s.encode("latin-1")
    return f"{len(b):03d}".encode("ascii") + b


# ---------------------------------------------------------------------
# Packet builders
# ---------------------------------------------------------------------


def build_connect_packet(
    app: str,
    uci: str,
    ip: str = "127.0.0.1",
    port: str = "0",
) -> bytes:
    """Build the NS-mode TCP connection handshake packet.

    Layout: ``[XWB]1030 chunk4(TCPConnect) chunk5(ip port app uci) EOT``
    """
    return (
        MAGIC
        + PRSP
        + b"4"
        + sread("TCPConnect")
        + b"5"
        + b"0"
        + lread(ip)
        + b"f"
        + b"0"
        + lread(port)
        + b"f"
        + b"0"
        + lread(app)
        + b"f"
        + b"0"
        + lread(uci)
        + b"f"
        + EOT
    )


def build_list_param(items: dict[str, str]) -> bytes:
    """Build a TY=2 (list-type) parameter for PRS5 chunk5.

    Used by DDR RPCs that pass a local M array (e.g. ``DDR GETS ENTRY
    DATA`` passes ``DDR("FILE")``, ``DDR("IENS")``, …).

    Subscripts are wrapped in M string quotes so ``LINST^XWBPRS`` can
    resolve the indirect reference ``@(array_name_"("_sub_")")``. An
    empty dict emits a single empty-pair terminator so PRS5 still sees
    a valid TY=2 param.
    """
    if not items:
        return b"2" + lread("") + lread("") + b"f"
    pairs = list(items.items())
    out = b"2"
    for i, (sub, val) in enumerate(pairs):
        cont = b"f" if i == len(pairs) - 1 else b"t"
        out += lread(f'"{sub}"') + lread(val) + cont
    return out


def build_rpc_packet(rpc_name: str, params: list[str | dict[str, str]]) -> bytes:
    """Build an RPC call packet.

    ``params`` elements are either ``str`` (TY=0 literal) or
    ``dict[str, str]`` (TY=2 list-type M array).
    """
    chunk1 = b"1" + sread("") + sread("")  # empty ver + return_type
    chunk2 = b"2" + sread("0") + sread(rpc_name)  # rpc_ver + rpc_name
    if not params:
        chunk5 = b"5" + EOT
    else:
        body = b""
        for p in params:
            if isinstance(p, dict):
                body += build_list_param(p)
            else:
                body += b"0" + lread(p) + b"f"
        chunk5 = b"5" + body + EOT
    return MAGIC + PRSP + chunk1 + chunk2 + chunk5


# ---------------------------------------------------------------------
# Response decoder
# ---------------------------------------------------------------------


def parse_response(raw: bytes) -> str:
    """Strip envelope bytes and return the response text.

    Raises :class:`BrokerProtocolError` if the response carries an M
    error marker (leading ``\\x18`` or embedded ``M  ERROR=``).
    """
    data = raw.rstrip(EOT)
    text = data.lstrip(NUL).decode("latin-1", errors="replace")
    if text.startswith("\x18") or "M  ERROR=" in text:
        raise BrokerProtocolError(f"VistA M error: {text!r}")
    return text
