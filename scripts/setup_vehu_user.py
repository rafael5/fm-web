"""Idempotent dev-user setup for VEHU (yottadb/octo-vehu).

Why this exists
---------------
The VEHU image does not ship with fm-web's documented dev credentials
(``fakedoc1 / 1Doc!@#$``) and does not register a ``FM BROWSER`` broker
application context. Contract + integration tests need a known-good
signon target, so we create one.

What it does
------------
Runs inside the VEHU container against the live YottaDB globals.
Empirically VEHU stores ACCESS + VERIFY codes as plaintext in
``^VA(200,IEN,0)`` pieces 3 and 4 (confirmed via inspection of
``PROGRAMMER,ONE``: piece 3 = ``PRO1234``). We write directly to the
globals + cross-reference nodes instead of going through ``^DIE`` —
simpler and avoids input-transform loader issues inside containers.

Idempotent: re-running updates the existing record in place.

Usage
-----
    docker cp scripts/setup_vehu_user.py vehu:/tmp/
    docker compose exec vehu bash -lc \\
        "source /home/vehu/etc/env && /opt/venv/bin/python /tmp/setup_vehu_user.py"

Prints a summary with the working signon triple (app, access, verify).
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("ydb_gbldir", "/home/vehu/g/vehu.gld")

import yottadb as y  # noqa: E402

# ---- configuration --------------------------------------------------

NAME = "FAKEDOC,ONE"
INITIAL = "FD"
ACCESS = "fakedoc1"
VERIFY = "1Doc!@#$"
APP_CONTEXT = "OR CPRS GUI CHART"

# NEW PERSON file number is 200; OPTION file number is 19.
# Globals: ^VA(200,...) and ^DIC(19,...).


# ---- ydb helpers (str/bytes boundary) -------------------------------


def _dec(x):
    return x.decode() if isinstance(x, bytes) else x


def _subs(*parts):
    return [str(p).encode() for p in parts]


def gget(gname, *subs, default=""):
    try:
        return _dec(y.get(gname, _subs(*subs)))
    except Exception:
        return default


def gset(gname, *subs, value=""):
    y.set(gname, _subs(*subs), str(value).encode())


def gnext(gname, *subs, start=""):
    try:
        r = y.subscript_next(gname, _subs(*subs, start))
        return _dec(r)
    except Exception:
        return ""


# ---- core logic -----------------------------------------------------


def find_user_by_name(name: str) -> str:
    """Return the IEN string for a user by .01 name via the "B" xref.

    ``^VA(200,"B",NAME,IEN)=""`` is the standard FileMan name index.
    """
    ien = ""
    while True:
        ien = gnext("^VA", 200, "B", name, start=ien)
        if not ien:
            return ""
        return ien


def next_available_ien() -> str:
    """Return the next free numeric IEN in NEW PERSON.

    Walks ``^VA(200,0)`` — FileMan header node — if present; else uses
    a reasonable starting point and finds the first hole.
    """
    zero = gget("^VA", 200, 0)
    parts = zero.split("^") if zero else []
    # Piece 4 of the header is "last IEN used" in many FM files.
    if len(parts) >= 4 and parts[3].isdigit():
        return str(int(parts[3]) + 1)
    # Fallback: scan from 20000 upward (above the seeded users)
    candidate = 20000
    while True:
        if not gget("^VA", 200, candidate, 0):
            return str(candidate)
        candidate += 1


def lookup_option_ien(option_name: str) -> str:
    """Return IEN of an OPTION file entry by name via its "B" xref."""
    return gnext("^DIC", 19, "B", option_name, start="")


def upsert_user(ien: str) -> None:
    """Write the zero node + VERIFY subnode + xrefs for the dev user.

    Storage paths derived from reading ``XUS.m::CHECKAV`` directly:
      - ACCESS lookup via ``^VA(200,"A", EN^XUSHSH($$UP(ACCESS)), IEN)``
      - VERIFY compared against piece 2 of ``^VA(200, IEN, 1)``
        (NOT subnode ".1" — the DD declares ``.1;2`` but the live
        code paths keep it on subnode ``1``)

    VEHU's ``EN^XUSHSH`` is an identity function (no hashing), so the
    "hashed" xref key is simply the uppercased access code. Other
    VistA distributions may apply real hashing; in that case this
    script would need to call into the container's M to compute the
    hash. For VEHU this works as-is.

    Seed-node example used for piece layout (PROGRAMMER,ONE):
      ``^VA(200,1,0)="PROGRAMMER,ONE^EC^PRO1234^@^^^^1^2^^^^^^^35"``
    Piece 3 = ACCESS plaintext; piece 4 is a legacy "@" marker, NOT
    verify. Pieces 8/9 = ``1^2`` kept to match seed.
    """
    up_access = ACCESS.upper()
    up_verify = VERIFY.upper()

    # Zero node — ACCESS plaintext on piece 3
    zero_parts = [
        NAME,  # 1 NAME
        INITIAL,  # 2 INITIAL
        up_access,  # 3 ACCESS CODE (uppercased — matches UP^XUS lookup)
        "@",  # 4 legacy marker
        "",
        "",
        "",  # 5-7 unused
        "1",  # 8 (match seed)
        "2",  # 9 (match seed)
        "",
        "",
        "",
        "",
        "",
        "",
        "",  # 10-16 unused
    ]
    gset("^VA", 200, ien, 0, value="^".join(zero_parts))

    # Subnode .1 — VERIFY on piece 2.
    # Confirmed by reading ``USER^XUS`` directly:
    #     XUSER(1) = ^VA(200,IEN,.1)
    # and ``CHECKAV^XUS`` then compares $P(XUSER(1),"^",2) to the
    # hashed verify. Leading "^" makes piece 1 empty and piece 2 the
    # stored verify value.
    gset("^VA", 200, ien, ".1", value="^" + up_verify)

    # Also clear any stale subnode 1 from an earlier buggy pass.
    try:
        y.delete_node("^VA", _subs(200, ien, 1))
    except Exception:
        pass

    # Cross-references — keys use ``$$UP($$EN^XUSHSH(X))`` which in
    # VEHU collapses to just the uppercased access code (EN^XUSHSH
    # is identity). Other VistA distributions may hash; fm-web's
    # integration tests target VEHU only.
    gset("^VA", 200, "B", NAME, ien, value="")
    gset("^VA", 200, "A", up_access, ien, value="")


def attach_broker_context(ien: str, option_ien: str) -> None:
    """Ensure the user's primary menu is the broker app context.

    FileMan field 201 (PRIMARY MENU OPTION) lives on the zero node of
    subnode 201 (or directly on piece 11 of the header zero node in
    some schemas). Easiest: set subnode 201 = option_ien, which is
    what VistA reads in XUP/XQ.
    """
    gset("^VA", 200, ien, 201, value=option_ien)
    # Also add to secondary menu options (subfile #19 in #200)
    # Head node 203,0: "^200.03PA^last_ien^count"
    # First IEN 1 by convention for primary-equivalent entry.
    gset("^VA", 200, ien, 203, 0, value="^200.03PA^1^1")
    gset("^VA", 200, ien, 203, 1, 0, value=option_ien)


# ---- entry point ----------------------------------------------------


def main() -> int:
    print("=== fm-web dev-user setup ===")
    print(f"target:        {NAME}")
    print(f"access/verify: {ACCESS} / {VERIFY}")
    print(f"app_context:   {APP_CONTEXT}")
    print()

    existing = find_user_by_name(NAME)
    if existing:
        ien = existing
        print(f"found existing user at IEN={ien} — will overwrite")
    else:
        ien = next_available_ien()
        print(f"no existing user — assigning IEN={ien}")

    upsert_user(ien)
    print(f"wrote ^VA(200,{ien},0) and xrefs (B, A)")

    opt_ien = lookup_option_ien(APP_CONTEXT)
    if not opt_ien:
        print(
            f"!! option {APP_CONTEXT!r} not found in ^DIC(19) — "
            f"broker TCPConnect will still fail. Skipping menu attach."
        )
        return 1
    attach_broker_context(ien, opt_ien)
    print(f"attached broker context {APP_CONTEXT} (option IEN={opt_ien})")

    print()
    print("Setup complete. Signon with:")
    print(f"  app={APP_CONTEXT}  uci=VAH  access={ACCESS}  verify={VERIFY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
