"""Allow-list enforcement — fm-web's read-only security boundary."""

import pytest

from fm_web.broker.allowlist import (
    ALLOWED_RPCS,
    is_allowed,
    require_allowed,
)
from fm_web.broker.errors import RpcDeniedError


class TestIsAllowed:
    def test_signon_setup_is_allowed(self):
        assert is_allowed("XUS SIGNON SETUP")

    def test_ddr_lister_is_allowed(self):
        assert is_allowed("DDR LISTER")

    def test_writing_rpc_is_denied(self):
        # ``DDR FILER`` wraps FILE^DIE — mutates data. Explicitly not allowed.
        assert not is_allowed("DDR FILER")

    def test_case_sensitive(self):
        assert not is_allowed("ddr lister")

    def test_unknown_rpc_is_denied(self):
        assert not is_allowed("NOT A REAL RPC")


class TestRequireAllowed:
    def test_allowed_returns_none(self):
        # Must not raise.
        assert require_allowed("DDR LISTER") is None

    def test_denied_raises_RpcDeniedError(self):
        with pytest.raises(RpcDeniedError) as exc:
            require_allowed("DDR FILER")
        assert "DDR FILER" in str(exc.value)
        assert "allow-list" in str(exc.value)

    def test_empty_string_denied(self):
        with pytest.raises(RpcDeniedError):
            require_allowed("")


class TestAllowListCoverage:
    """Claims about the shape of the allow-list — anchors for reviewers."""

    def test_has_readonly_ddr_quartet(self):
        names = {a.name for a in ALLOWED_RPCS}
        assert {
            "DDR LISTER",
            "DDR FINDER",
            "DDR FIND1",
            "DDR GETS ENTRY DATA",
        } <= names

    def test_has_signon_trio(self):
        names = {a.name for a in ALLOWED_RPCS}
        assert {"XUS SIGNON SETUP", "XUS AV CODE", "XUS SIGNOFF"} <= names

    def test_no_writing_rpcs(self):
        # Sanity — these are the FileMan mutation wrappers. Any appearance
        # means the allow-list was tampered with.
        forbidden = {"DDR FILER", "DDR FILE ENTRY", "DDR DELETE ENTRY"}
        names = {a.name for a in ALLOWED_RPCS}
        assert forbidden.isdisjoint(names)

    def test_every_entry_has_purpose(self):
        for a in ALLOWED_RPCS:
            assert a.purpose, f"{a.name} has no purpose string"
            assert a.wraps, f"{a.name} has no wraps string"
