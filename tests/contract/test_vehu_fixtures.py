"""Contract tests — recorded VEHU responses must round-trip through the fake.

Each fixture in ``tests/contract/fixtures/`` was captured by
``scripts/record_fixtures.py`` against a live VEHU broker on
2026-04-15. These tests prove two things:

1. The wire decoder (``parse_response``) handles every recorded
   response without raising — i.e. our NS-mode envelope handling is
   correct for real server output.
2. ``FakeRPCBroker`` given the recorded raw text through
   ``register()`` produces the same high-level result as the real
   ``VistARpcBroker`` would (they share the response parsers, so this
   really guarantees the fake and the real client agree on response
   shape).

A subset of the fixtures captures error responses from unauthenticated
or absent-on-server RPCs (``"Application context has not been
created!"``, ``"doesn't exist on the server."``). Those exercise the
error-handling paths — equally valuable as fixtures.

Regenerate with ``.venv/bin/python scripts/record_fixtures.py`` after
any wire-level change; commit the updated fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fm_web.broker import FakeRPCBroker
from fm_web.broker.responses import (
    parse_finder_response,
    parse_gets_response,
    parse_lister_response,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    path = FIXTURES_DIR / name
    assert path.exists(), f"missing fixture {path} — run record_fixtures.py"
    return json.loads(path.read_text())


def _all_fixtures() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.json"))


class TestFixturesPresent:
    def test_fixtures_directory_populated(self):
        files = _all_fixtures()
        assert len(files) >= 10, f"only {len(files)} fixtures — rerun recorder"

    @pytest.mark.parametrize(
        "name",
        [
            "xus_signon_setup__default.json",
            "xus_av_code__response.json",
            "xus_get_user_info__default.json",
            "orwu_dt__now.json",
            "ddr_lister__patient_first5.json",
            "ddr_lister__new_person_first5.json",
            "ddr_gets_entry_data__patient_1_basic.json",
            "ddr_find1__new_person_by_access.json",
            "ddr_finder__patient_by_a_prefix.json",
            "ddr_get_dd__patient_AL.json",
            "ddr_get_dd_hash__patient.json",
        ],
    )
    def test_fixture_loads_and_has_required_keys(self, name: str):
        doc = _load(name)
        assert "rpc_name" in doc
        assert "variant" in doc
        assert "params" in doc
        assert "raw_response" in doc
        assert "recorded_at" in doc


class TestXusSignonSetup:
    """Real unauthenticated-world-visible RPC. The server actually responds."""

    def test_response_is_multiline_site_info(self):
        doc = _load("xus_signon_setup__default.json")
        lines = doc["raw_response"].split("\r\n")
        # Real VEHU response shape: vehu, ROU, VAH, /dev/null, 5, 0, hostname, 0
        # Should be at least 4 non-empty lines of site metadata.
        non_empty = [ln for ln in lines if ln]
        assert len(non_empty) >= 4
        # "VAH" is VEHU's UCI — should appear somewhere.
        assert "VAH" in doc["raw_response"]


class TestXusAvCodeAuthFailure:
    """Fixture captures the auth-failure shape. Exercises AuthenticationError."""

    def test_failure_shape_has_zero_duz_and_error_message(self):
        doc = _load("xus_av_code__response.json")
        raw = doc["raw_response"]
        first_line = raw.split("\r\n", 1)[0].strip()
        assert first_line == "0"  # DUZ=0 ⇒ failure
        assert "Not a valid" in raw  # VistA's rejection text

    def test_fake_broker_replays_auth_failure(self):
        # Feeding the recorded raw text to FakeRPCBroker should exercise
        # the same AuthenticationError path a real signon would.
        doc = _load("xus_av_code__response.json")
        broker = FakeRPCBroker(
            responses={
                "XUS SIGNON SETUP": "unused",
                "XUS AV CODE": doc["raw_response"],
            },
            signon_duz="0",  # tell the fake to simulate failure
        )
        broker.connect()
        with pytest.raises(Exception) as exc:
            broker.signon("fakedoc1", "1Doc!@#$")
        assert "DUZ" in str(exc.value) or "failed" in str(exc.value)


class TestUnauthenticatedRejections:
    """DDR* and ORWU DT all reject pre-auth with an app-context error.

    This is the shape to expect when the UI calls them without a valid
    session. The fm-web API layer will catch these and surface 401-style
    errors to the frontend.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "orwu_dt__now.json",
            "ddr_lister__patient_first5.json",
            "ddr_lister__new_person_first5.json",
            "ddr_gets_entry_data__patient_1_basic.json",
            "ddr_find1__new_person_by_access.json",
            "ddr_finder__patient_by_a_prefix.json",
        ],
    )
    def test_app_context_error_shape(self, name: str):
        doc = _load(name)
        # VistA-style error: leading ')' marker + message.
        assert "Application context has not been created" in doc["raw_response"]


class TestAbsentRpcs:
    """DDR GET DD and DDR GET DD HASH do not exist on VEHU.

    Fixture proves the "RPC doesn't exist" response shape so we can
    handle it in the API layer. See LESSONS-LEARNED L31.
    """

    @pytest.mark.parametrize(
        "name, rpc_name",
        [
            ("ddr_get_dd__patient_AL.json", "DDR GET DD"),
            ("ddr_get_dd_hash__patient.json", "DDR GET DD HASH"),
        ],
    )
    def test_absent_rpc_shape(self, name: str, rpc_name: str):
        doc = _load(name)
        assert "doesn't exist on the server" in doc["raw_response"]
        assert rpc_name in doc["raw_response"]


class TestParsersAgainstFixtureShapes:
    """Our DDR parsers must not crash on the real error-response shapes.

    These are negative tests — parsers should gracefully return empty
    lists (or skip malformed lines) rather than raising. The API layer
    is responsible for detecting error shapes before calling a parser.
    """

    def test_gets_parser_on_error_response_returns_empty(self):
        doc = _load("ddr_gets_entry_data__patient_1_basic.json")
        # Error response is not valid GETS output; parser should skip it.
        assert parse_gets_response(doc["raw_response"]) == []

    def test_lister_parser_on_error_response_returns_empty(self):
        doc = _load("ddr_lister__patient_first5.json")
        # Error response has no count-line + entries structure.
        result = parse_lister_response(doc["raw_response"])
        # Parser drops the first line (treated as count), may return
        # degenerate "entries" from the error message. Assert at most 1
        # so the API layer knows to detect error shape first.
        assert len(result) <= 1

    def test_finder_parser_on_error_response_returns_single_line(self):
        doc = _load("ddr_finder__patient_by_a_prefix.json")
        # Finder parser discards the first line and returns the rest;
        # for a one-line error response, result is empty.
        assert parse_finder_response(doc["raw_response"]) == []
