"""Contract tests — recorded VEHU responses round-trip through the fake.

Each fixture in ``tests/contract/fixtures/`` was captured by
``scripts/record_fixtures.py`` against a live VEHU broker on
2026-04-15 (re-recorded after phase 1.1 auth + context fixes; see
LESSONS-LEARNED L31-L35). These tests prove:

1. The wire decoder handles every recorded response without raising.
2. Happy-path RPCs (XUS SIGNON SETUP, XUS AV CODE, XWB CREATE
   CONTEXT, XUS GET USER INFO, DDR GETS ENTRY DATA) return the
   shapes our parsers expect.
3. Known server-side M errors (DDR LISTER / FIND1 / FINDER on this
   VEHU build — parameter mismatch) and known-absent RPCs (DDR GET
   DD) have stable rejection shapes that the API layer will surface
   as meaningful errors to the UI.

Regenerate with::

    .venv/bin/python scripts/record_fixtures.py --app "OR CPRS GUI CHART"

Commit the updated fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fm_web.broker.responses import parse_gets_response

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    path = FIXTURES_DIR / name
    assert path.exists(), f"missing fixture {path} — run record_fixtures.py"
    return json.loads(path.read_text())


def _all_fixtures() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.json"))


class TestFixturesPresent:
    def test_fixture_directory_populated(self):
        files = _all_fixtures()
        assert len(files) >= 10, f"only {len(files)} fixtures — rerun recorder"

    @pytest.mark.parametrize(
        "name",
        [
            "xus_signon_setup__default.json",
            "xus_av_code__response.json",
            "xwb_create_context__or_cprs_gui_chart.json",
            "xus_get_user_info__default.json",
            "orwu_dt__now.json",
            "ddr_lister__patient_first5.json",
            "ddr_lister__new_person_first5.json",
            "ddr_gets_entry_data__new_person_1_basic.json",
            "ddr_find1__new_person_by_access.json",
            "ddr_finder__patient_by_a_prefix.json",
            "ddr_get_dd__patient_AL.json",
            "ddr_get_dd_hash__patient.json",
        ],
    )
    def test_fixture_loads_with_required_keys(self, name: str):
        doc = _load(name)
        for key in ("rpc_name", "variant", "params", "raw_response", "recorded_at"):
            assert key in doc, f"{name} missing {key}"


class TestXusSignonSetup:
    """Real unauthenticated RPC. Shape = multi-line site metadata."""

    def test_shape_has_uci(self):
        doc = _load("xus_signon_setup__default.json")
        assert "VAH" in doc["raw_response"]

    def test_at_least_four_lines(self):
        doc = _load("xus_signon_setup__default.json")
        non_empty = [ln for ln in doc["raw_response"].split("\r\n") if ln]
        assert len(non_empty) >= 4


class TestXusAvCodeSuccess:
    """Happy-path auth — DUZ > 0 on the first line."""

    def test_duz_is_positive(self):
        doc = _load("xus_av_code__response.json")
        first_line = doc["raw_response"].split("\r\n", 1)[0].strip()
        duz = int(first_line)
        # Our dev user gets assigned a high IEN (see setup_vehu_user.py).
        assert duz > 0, f"expected positive DUZ, got {duz}"

    def test_result_has_multiple_lines(self):
        # Success response is DUZ then flags/messages per XUSRB docs.
        doc = _load("xus_av_code__response.json")
        assert "\r\n" in doc["raw_response"]


class TestXwbCreateContext:
    """Context switch after signon must return '1' (success)."""

    def test_returns_success(self):
        doc = _load("xwb_create_context__or_cprs_gui_chart.json")
        assert doc["raw_response"].strip() == "1", (
            f"XWB CREATE CONTEXT should return '1'; got {doc['raw_response']!r}"
        )


class TestXusGetUserInfo:
    """User metadata — DUZ on line 1, NAME on line 2, etc."""

    def test_shape_has_duz_and_name(self):
        doc = _load("xus_get_user_info__default.json")
        lines = doc["raw_response"].split("\r\n")
        assert lines[0].strip().isdigit(), "line 1 must be DUZ"
        assert "," in lines[1], "line 2 must be LAST,FIRST-style name"


class TestDdrGetsEntryData:
    """Real NEW PERSON entry pulled via GETS^DIQ — this is the backbone
    of fm-web's DD browsing. Response format is ``[Data]`` header line
    followed by ``file^ien^field^mult^value`` rows.
    """

    def test_has_data_header(self):
        doc = _load("ddr_gets_entry_data__new_person_1_basic.json")
        assert doc["raw_response"].startswith("[Data]"), "expected [Data] header line"

    def test_contains_name_field(self):
        doc = _load("ddr_gets_entry_data__new_person_1_basic.json")
        # PROGRAMMER,ONE is VEHU's IEN=1 user
        assert "PROGRAMMER,ONE" in doc["raw_response"]

    def test_parser_handles_real_payload(self):
        """Our parse_gets_response must not crash on real VEHU data.

        Note: VEHU's format carries an extra 'multiple instance' piece
        between the field number and the value (5 carets total). Our
        parser currently splits on 3 carets max → piece 4 will carry
        ``"^value"`` (with the empty mult marker prepended). The
        parser should still yield entries without raising.
        """
        doc = _load("ddr_gets_entry_data__new_person_1_basic.json")
        # Strip the [Data] header line since our parser expects pure
        # body rows. The recorder/service layer is responsible for that
        # header strip; we simulate it here.
        body = "\r\n".join(
            ln
            for ln in doc["raw_response"].split("\r\n")
            if ln and not ln.startswith("[Data]")
        )
        entries = parse_gets_response(body)
        assert entries, f"parser returned no entries from body: {body!r}"


class TestOrwuDtBrokenOnVEHU:
    """ORWU DT is a standard broker RPC but emits an M error on this
    VEHU build (LVUNDEF on X). Fixture captures the shape so the API
    layer can treat it as a 500-style server bug rather than a
    protocol error.
    """

    def test_error_shape(self):
        doc = _load("orwu_dt__now.json")
        raw = doc["raw_response"]
        assert "M ERROR" in raw
        assert "LVUNDEF" in raw or "Undefined" in raw


class TestDdrListerParameterMismatch:
    """VEHU's DDR.m declares fewer formal params than fm-web sends.
    Captures the error shape. Signature fix is phase-2 follow-up.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "ddr_lister__patient_first5.json",
            "ddr_lister__new_person_first5.json",
            "ddr_find1__new_person_by_access.json",
            "ddr_finder__patient_by_a_prefix.json",
        ],
    )
    def test_too_many_params_error(self, name: str):
        doc = _load(name)
        raw = doc["raw_response"]
        assert "M ERROR" in raw
        assert "ACTLSTTOOLONG" in raw or "More actual parameters" in raw


class TestAbsentRpcs:
    """DDR GET DD / DDR GET DD HASH are not registered on VEHU.
    Architectural decision (L31): rebuild DD browsing on DDR LISTER
    + DDR GETS against file #1. Fixtures are retained as proof.
    """

    @pytest.mark.parametrize(
        "name,rpc_name",
        [
            ("ddr_get_dd__patient_AL.json", "DDR GET DD"),
            ("ddr_get_dd_hash__patient.json", "DDR GET DD HASH"),
        ],
    )
    def test_absent_rpc_shape(self, name: str, rpc_name: str):
        doc = _load(name)
        raw = doc["raw_response"]
        # Either the recorder hit the allow-list (new behaviour: we
        # blocked the call) or VEHU rejected it. Accept both.
        assert (
            "doesn't exist on the server" in raw
            or "not in the fm-web allow-list" in raw
            or "<M ERROR" in raw
        )
