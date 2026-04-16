"""End-to-end route tests via TestClient with a FakeRPCBroker factory.

Every test here exercises the full stack (FastAPI → dep → service →
broker → response parser) without touching a real socket. The
``broker_factory`` seam on ``app.state`` lets us inject a
pre-populated :class:`FakeRPCBroker` at signon.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from fm_web.api.app import create_app
from fm_web.broker import FakeRPCBroker

# ---- builders ------------------------------------------------------


def _lister(rows: list[tuple[str, str]]) -> str:
    lines = [str(len(rows))] + [f"{ien}^{ext}" for ien, ext in rows]
    return "\r\n".join(lines) + "\r\n"


def _gets(pairs: list[tuple[str, str, str, str]]) -> str:
    body = [f"{f}^{i}^{fn}^^{v}" for f, i, fn, v in pairs]
    return "[Data]\r\n" + "\r\n".join(body) + "\r\n"


def _make_client(responses: dict | None = None) -> TestClient:
    """App + TestClient wired to a FakeRPCBroker on signon."""
    app = create_app()

    def _factory(settings):
        broker = FakeRPCBroker(
            responses=responses or {},
            signon_duz="1497",
        )
        return broker

    app.state.broker_factory = _factory
    return TestClient(app)


def _signon(client: TestClient) -> None:
    r = client.post(
        "/api/session/signon",
        json={"access": "fakedoc1", "verify": "1Doc!@#$"},
    )
    assert r.status_code == 200, r.text


# ---- health --------------------------------------------------------


class TestHealth:
    def test_no_auth_required(self):
        client = _make_client()
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ---- session -------------------------------------------------------


class TestSession:
    def test_signon_sets_cookie_and_returns_info(self):
        client = _make_client()
        r = client.post(
            "/api/session/signon",
            json={"access": "fakedoc1", "verify": "1Doc!@#$"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["duz"] == "1497"
        assert body["uci"] == "VAH"
        # Cookie set
        assert "fm_web_session" in client.cookies

    def test_me_requires_session_cookie(self):
        client = _make_client()
        r = client.get("/api/session/me")
        assert r.status_code == 401

    def test_me_returns_session_after_signon(self):
        client = _make_client()
        _signon(client)
        r = client.get("/api/session/me")
        assert r.status_code == 200
        assert r.json()["duz"] == "1497"

    def test_signoff_clears_session(self):
        client = _make_client()
        _signon(client)
        r = client.post("/api/session/signoff")
        assert r.status_code == 204
        # Subsequent /me → 401
        r = client.get("/api/session/me")
        assert r.status_code == 401


# ---- files ---------------------------------------------------------


class TestFilesRoutes:
    def test_list_files(self):
        client = _make_client(
            {
                "DDR LISTER": _lister([("2", "PATIENT"), ("200", "NEW PERSON")]),
            }
        )
        _signon(client)
        r = client.get("/api/files")
        assert r.status_code == 200
        data = r.json()
        assert [f["label"] for f in data] == ["PATIENT", "NEW PERSON"]

    def test_get_file_detail(self):
        client = _make_client(
            {
                # File header via GETS on file 1
                (
                    "DDR GETS ENTRY DATA",
                    (
                        ("FIELDS", ".01;.1"),
                        ("FILE", "1"),
                        ("FLAGS", "E"),
                        ("IENS", "200,"),
                    ),
                ): _gets(
                    [
                        ("1", "200", ".01", "NEW PERSON"),
                        ("1", "200", ".1", "^VA(200,"),
                    ]
                ),
                # Field subfile
                (
                    "DDR LISTER",
                    ("1", ",200,", "P", "200", "", "0", "", "B", "", ""),
                ): _lister([(".01", "NAME"), ("2", "ACCESS CODE")]),
            }
        )
        _signon(client)
        r = client.get("/api/files/200")
        assert r.status_code == 200
        body = r.json()
        assert body["label"] == "NEW PERSON"
        assert body["global_root"] == "^VA(200,"
        assert set(body["fields"].keys()) == {"0.01", "2.0"}

    def test_get_file_404(self):
        client = _make_client({"DDR GETS ENTRY DATA": "[Data]\r\n"})
        _signon(client)
        r = client.get("/api/files/99999")
        assert r.status_code == 404


# ---- entries -------------------------------------------------------


class TestEntryRoutes:
    def test_list_entries(self):
        client = _make_client(
            {
                "DDR LISTER": _lister([("1", "ALICE"), ("2", "BOB"), ("3", "CAROL")]),
            }
        )
        _signon(client)
        r = client.get("/api/files/2/entries?limit=3")
        assert r.status_code == 200
        body = r.json()
        assert body["file_number"] == 2.0
        assert len(body["entries"]) == 3
        assert body["entries"][0]["ien"] == "1"
        # 3 entries returned with limit=3 → expect cursor
        assert body["next_cursor"] == "CAROL"

    def test_get_entry(self):
        client = _make_client(
            {
                "DDR GETS ENTRY DATA": _gets(
                    [
                        ("2", "1", ".01", "PATIENT,TEST"),
                        ("2", "1", ".02", "MALE"),
                    ]
                ),
            }
        )
        _signon(client)
        r = client.get("/api/files/2/entries/1")
        assert r.status_code == 200
        body = r.json()
        assert body["ien"] == "1"
        assert body["fields"]["0.01"]["value"] == "PATIENT,TEST"


# ---- packages ------------------------------------------------------


class TestPackageRoutes:
    def test_list_packages(self):
        client = _make_client(
            {
                "DDR LISTER": _lister([("1", "KERNEL"), ("2", "VA FILEMAN")]),
            }
        )
        _signon(client)
        r = client.get("/api/packages")
        assert r.status_code == 200
        assert [p["name"] for p in r.json()] == ["KERNEL", "VA FILEMAN"]

    def test_get_package(self):
        client = _make_client(
            {
                "DDR GETS ENTRY DATA": _gets(
                    [
                        ("9.4", "1", ".01", "KERNEL"),
                        ("9.4", "1", "1", "XU"),
                    ]
                ),
            }
        )
        _signon(client)
        r = client.get("/api/packages/1")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "KERNEL"
        assert body["prefix"] == "XU"

    def test_files_by_package(self):
        client = _make_client(
            {
                "DDR LISTER": _lister([("2", "PATIENT"), ("44", "HOSPITAL LOCATION")]),
            }
        )
        _signon(client)
        r = client.get("/api/packages/1/files")
        assert r.status_code == 200
        assert r.json() == [2.0, 44.0]


# ---- allow-list enforcement still works end-to-end ------------------


class TestAllowlistBoundary:
    def test_services_cannot_escape_allowlist(self):
        """If a service tried a denied RPC, the 401 → 500 would bubble.
        Sanity: no route path invokes a non-allow-listed RPC."""
        client = _make_client({"DDR LISTER": _lister([])})
        _signon(client)
        # Typical healthy paths — all should complete.
        for path in [
            "/api/files",
            "/api/files/2/entries",
            "/api/packages",
        ]:
            assert client.get(path).status_code == 200, path
