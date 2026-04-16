"""Record live RPC responses from a VistA broker into contract fixtures.

Each fixture is a JSON document containing:
    - rpc_name: the RPC called
    - params: the literal / list params (dicts are rendered as sorted items)
    - raw_response: the server's decoded payload string (post envelope strip)
    - variant: short label so tests can pick the fixture they want
    - recorded_at: ISO timestamp for provenance

Fixtures go under ``tests/contract/fixtures/<rpc_slug>__<variant>.json``.

Usage
-----
Run against a live VEHU broker (must already be up on :9430)::

    .venv/bin/python scripts/record_fixtures.py \\
        --host localhost --port 9430 \\
        --access fakedoc1 --verify '1Doc!@#$'

All fixtures are regenerated each run; no partial updates. The file this
script writes are the contract-test ground truth — commit them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Make src/ importable without installing the package — mirrors conftest.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm_web.broker import VistARpcBroker  # noqa: E402
from fm_web.broker.wire import build_rpc_packet, parse_response  # noqa: E402

log = logging.getLogger("record_fixtures")

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "contract" / "fixtures"


def _slug(rpc_name: str) -> str:
    return rpc_name.lower().replace(" ", "_")


def _save(
    rpc_name: str,
    variant: str,
    params: list[Any],
    raw: str,
) -> Path:
    """Write one fixture JSON. Returns the file path."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    # Normalize dict params to a sorted list-of-pairs for stable JSON.
    norm_params: list[Any] = []
    for p in params:
        if isinstance(p, dict):
            norm_params.append({"_dict": sorted(p.items())})
        else:
            norm_params.append(p)
    doc = {
        "rpc_name": rpc_name,
        "variant": variant,
        "params": norm_params,
        "raw_response": raw,
        "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    path = FIXTURES_DIR / f"{_slug(rpc_name)}__{variant}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    log.info("wrote %s (%d bytes of response)", path.name, len(raw))
    return path


def _raw_call(
    broker: VistARpcBroker, rpc_name: str, *params: str | dict[str, str]
) -> str:
    """Execute an RPC and return the *raw* response text (post envelope).

    We bypass the typed high-level helpers so the fixture captures what
    the server actually said, not a parsed interpretation of it.
    """
    from fm_web.broker.allowlist import require_allowed

    require_allowed(rpc_name)
    pkt = build_rpc_packet(rpc_name, list(params))
    raw_bytes = broker._send_recv(pkt)  # type: ignore[attr-defined]
    return parse_response(raw_bytes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=9430)
    ap.add_argument("--app", default="FM BROWSER")
    ap.add_argument("--uci", default="VAH")
    ap.add_argument(
        "--access",
        default=os.environ.get("VEHU_ACCESS", "fakedoc1"),
        help="ACCESS code (env: VEHU_ACCESS)",
    )
    ap.add_argument(
        "--verify",
        default=os.environ.get("VEHU_VERIFY", "1Doc!@#$"),
        help="VERIFY code (env: VEHU_VERIFY)",
    )
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    broker = VistARpcBroker(host=args.host, port=args.port)
    ack = broker.connect(app=args.app, uci=args.uci)
    log.info("handshake: %r", ack)

    # ---- XUS SIGNON SETUP ------------------------------------------------
    raw = _raw_call(broker, "XUS SIGNON SETUP")
    _save("XUS SIGNON SETUP", "default", [], raw)

    # ---- Authenticate — capture both success and failure shapes ---------
    # Even an auth failure response is a valid fixture: it exercises the
    # AuthenticationError path end-to-end.
    from fm_web.broker.crypt import encrypt as _encrypt

    ciphertext = _encrypt(f"{args.access};{args.verify}")
    av_raw = _raw_call(broker, "XUS AV CODE", ciphertext)
    _save("XUS AV CODE", "response", ["<redacted ciphertext>"], av_raw)

    duz_line = av_raw.split("\r\n", 1)[0].strip()
    try:
        duz = int(duz_line)
    except ValueError:
        duz = 0
    authenticated = duz > 0
    log.info("DUZ=%s (authenticated=%s)", duz_line, authenticated)
    if not authenticated:
        log.warning(
            "VEHU rejected %r — account may be locked or creds rotated; "
            "recording only unauthenticated fixtures",
            args.access,
        )
    else:
        # Switch broker context so downstream DDR* calls are accepted.
        ctx_encrypted = _encrypt(args.app)
        ctx_raw = _raw_call(broker, "XWB CREATE CONTEXT", ctx_encrypted)
        _save("XWB CREATE CONTEXT", "or_cprs_gui_chart", [args.app], ctx_raw)

    # Everything below typically requires DUZ > 0. We still attempt each
    # call and capture the server's response — whether it's a real payload
    # or an auth-required rejection, the raw text is a valid fixture.

    def _try(label: str, rpc_name: str, *params: str | dict[str, str]) -> None:
        """Record one RPC; capture server-side errors as fixtures too."""
        try:
            raw = _raw_call(broker, rpc_name, *params)
        except Exception as exc:
            # BrokerProtocolError / M errors — capture the message verbatim
            # so we can assert shapes on the error path too.
            raw = f"<M ERROR: {exc}>"
        _save(rpc_name, label, list(params), raw)

    # ---- ORWU DT ---------------------------------------------------------
    _try("now", "ORWU DT")

    # ---- XUS GET USER INFO ----------------------------------------------
    _try("default", "XUS GET USER INFO")

    # ---- DDR LISTER — small page of PATIENT file -----------------------
    _try(
        "patient_first5",
        "DDR LISTER",
        "2",
        "",
        "P",
        "5",
        "",
        "0",
        "",
        "B",
        "",
        "",
    )

    # ---- DDR LISTER — NEW PERSON, first 5 -------------------------------
    _try(
        "new_person_first5",
        "DDR LISTER",
        "200",
        "",
        "P",
        "5",
        "",
        "0",
        "",
        "B",
        "",
        "",
    )

    # ---- DDR GETS ENTRY DATA — NEW PERSON IEN=1 (POSTMASTER) ------------
    _try(
        "new_person_1_basic",
        "DDR GETS ENTRY DATA",
        {"FILE": "200", "IENS": "1,", "FIELDS": ".01;1;2", "FLAGS": "E"},
    )

    # ---- DDR FIND1 — search NEW PERSON by access code ------------------
    _try("new_person_by_access", "DDR FIND1", "200", args.access, "A", "")

    # ---- DDR FINDER — partial name search on PATIENT file --------------
    _try(
        "patient_by_a_prefix",
        "DDR FINDER",
        "2",
        "B",
        "",
        "1",
        "A",
        "5",
        "",
        "",
    )

    # ---- DDR GET DD — file 2 header + field list -----------------------
    try:
        raw = _raw_call(broker, "DDR GET DD", "2", "AL")
        _save("DDR GET DD", "patient_AL", ["2", "AL"], raw)
    except Exception as exc:
        log.warning("DDR GET DD failed: %s", exc)

    # ---- DDR GET DD HASH — file 2 ---------------------------------------
    try:
        raw = _raw_call(broker, "DDR GET DD HASH", "2")
        _save("DDR GET DD HASH", "patient", ["2"], raw)
    except Exception as exc:
        log.warning("DDR GET DD HASH failed: %s", exc)

    # ---- Signoff ---------------------------------------------------------
    try:
        broker.signoff()
        log.info("signed off cleanly")
    except Exception as exc:
        log.warning("signoff failed (ignorable): %s", exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
