"""XWB NS-mode wire codec.

The wire protocol is a specification inherited from VistA's XWBPRS.m /
XWBTCPMT.m. These tests lock the specification: given a set of inputs,
the bytes on the wire are exactly X. Changes to wire.py that break
these tests break interop with real VistA.
"""

import pytest

from fm_web.broker.errors import BrokerProtocolError
from fm_web.broker.wire import (
    EOT,
    build_connect_packet,
    build_list_param,
    build_rpc_packet,
    lread,
    parse_response,
    sread,
)


class TestSread:
    def test_simple(self):
        assert sread("ABC") == b"\x03ABC"

    def test_empty(self):
        assert sread("") == b"\x00"

    def test_rpc_name(self):
        assert sread("XUS SIGNON SETUP") == b"\x10XUS SIGNON SETUP"

    def test_255_bytes(self):
        s = "x" * 255
        assert sread(s) == b"\xff" + b"x" * 255

    def test_256_bytes_raises(self):
        with pytest.raises(AssertionError):
            sread("x" * 256)


class TestLread:
    def test_simple(self):
        assert lread("ABC") == b"003ABC"

    def test_empty(self):
        assert lread("") == b"000"

    def test_seven_chars(self):
        assert lread("PATIENT") == b"007PATIENT"

    def test_large(self):
        s = "x" * 123
        assert lread(s) == b"123" + b"x" * 123


class TestBuildConnectPacket:
    """NS-mode handshake: [XWB]1030 chunk4(TCPConnect) chunk5(ip+port+app+uci)."""

    def test_starts_with_magic_and_prsp(self):
        pkt = build_connect_packet(app="FM BROWSER", uci="VAH")
        assert pkt.startswith(b"[XWB]1030")

    def test_has_tcpconnect_command(self):
        pkt = build_connect_packet(app="FM BROWSER", uci="VAH")
        # chunk 4 is b"4" followed by sread("TCPConnect")
        assert b"4\x0aTCPConnect" in pkt

    def test_ends_with_eot(self):
        pkt = build_connect_packet(app="FM BROWSER", uci="VAH")
        assert pkt.endswith(EOT)

    def test_carries_app_and_uci(self):
        pkt = build_connect_packet(app="FM BROWSER", uci="VAH")
        # app and uci arrive as lread'd strings, prefixed by TY="0"
        assert b"0" + lread("FM BROWSER") + b"f" in pkt
        assert b"0" + lread("VAH") + b"f" in pkt

    def test_default_ip_port_included(self):
        pkt = build_connect_packet(app="A", uci="B")
        assert b"0" + lread("127.0.0.1") + b"f" in pkt
        assert b"0" + lread("0") + b"f" in pkt


class TestBuildRpcPacket:
    def test_empty_params(self):
        pkt = build_rpc_packet("XUS SIGNON SETUP", [])
        assert pkt.startswith(b"[XWB]1030")
        assert pkt.endswith(EOT)
        assert b"2" + sread("0") + sread("XUS SIGNON SETUP") in pkt

    def test_literal_params(self):
        pkt = build_rpc_packet("FOO", ["bar", "baz"])
        assert b"0" + lread("bar") + b"f" in pkt
        assert b"0" + lread("baz") + b"f" in pkt

    def test_list_param_wraps_subscripts_in_quotes(self):
        # DDR* RPCs pass local M arrays; subscripts must be wrapped in
        # M string quotes so LINST^XWBPRS builds valid indirect refs.
        pkt = build_rpc_packet(
            "DDR GETS ENTRY DATA",
            [{"FILE": "2", "IENS": "1,", "FIELDS": "*", "FLAGS": ""}],
        )
        assert lread('"FILE"') in pkt
        assert lread('"IENS"') in pkt
        # First three pairs end in "t" (more), last in "f" (end of list)
        pairs = pkt.count(b"t") + pkt.count(b"f")
        assert pairs >= 4

    def test_rpc_name_is_sread(self):
        pkt = build_rpc_packet("DDR LISTER", [])
        assert sread("DDR LISTER") in pkt


class TestBuildListParam:
    def test_single_pair(self):
        # TY=2, one pair, cont="f" (end of list)
        out = build_list_param({"FILE": "2"})
        assert out == b"2" + lread('"FILE"') + lread("2") + b"f"

    def test_multi_pair_continuations(self):
        out = build_list_param({"FILE": "2", "IENS": "1,"})
        assert out == (
            b"2"
            + lread('"FILE"')
            + lread("2")
            + b"t"
            + lread('"IENS"')
            + lread("1,")
            + b"f"
        )

    def test_empty_dict_sends_terminator(self):
        out = build_list_param({})
        # Spec: empty pair + end-of-list so PRS5 still reads a valid TY=2 param.
        assert out == b"2" + lread("") + lread("") + b"f"


class TestParseResponse:
    def test_strips_nul_prefix_and_eot_suffix(self):
        assert parse_response(b"\x00\x00hello\x04") == "hello"

    def test_single_nul_prefix(self):
        assert parse_response(b"\x00hi\x04") == "hi"

    def test_no_prefix(self):
        assert parse_response(b"world\x04") == "world"

    def test_empty(self):
        assert parse_response(b"\x04") == ""

    def test_m_error_raises_protocol_error(self):
        # M errors arrive as \x18 + "M  ERROR=..."
        raw = b"\x00\x00\x18M  ERROR=%GTM-E-FOO\x04"
        with pytest.raises(BrokerProtocolError) as exc:
            parse_response(raw)
        assert "M  ERROR" in str(exc.value)

    def test_multi_line_preserved(self):
        assert parse_response(b"\x00\x00a\r\nb\r\nc\x04") == "a\r\nb\r\nc"
