"""PackageService — list + detail for file 9.4 (PACKAGE)."""

from __future__ import annotations

from fm_web.broker import FakeRPCBroker
from fm_web.models import PackageDef
from fm_web.services.packages import PackageService


def _lister_rows(rows: list[tuple[str, str]]) -> str:
    lines = [str(len(rows))] + [f"{ien}^{ext}" for ien, ext in rows]
    return "\r\n".join(lines) + "\r\n"


def _gets_rows(pairs: list[tuple[str, str, str, str]]) -> str:
    body = [f"{f}^{i}^{fn}^^{v}" for f, i, fn, v in pairs]
    return "[Data]\r\n" + "\r\n".join(body) + "\r\n"


class TestListPackages:
    def test_enumerates_file_9_4(self):
        broker = FakeRPCBroker(
            responses={
                "DDR LISTER": _lister_rows(
                    [
                        ("1", "KERNEL"),
                        ("2", "VA FILEMAN"),
                        ("3", "MAILMAN"),
                    ]
                ),
            },
        )
        broker.connect()
        svc = PackageService(broker)
        packages = svc.list_packages()
        assert [p.ien for p in packages] == ["1", "2", "3"]
        assert [p.name for p in packages] == ["KERNEL", "VA FILEMAN", "MAILMAN"]

    def test_uses_file_9_4(self):
        broker = FakeRPCBroker(responses={"DDR LISTER": _lister_rows([])})
        broker.connect()
        svc = PackageService(broker)
        svc.list_packages()
        call = next(c for c in broker.calls if c.rpc_name == "DDR LISTER")
        assert call.params[0] == "9.4"


class TestGetPackage:
    def test_returns_package_with_prefix(self):
        broker = FakeRPCBroker(
            responses={
                "DDR GETS ENTRY DATA": _gets_rows(
                    [
                        ("9.4", "1", ".01", "KERNEL"),
                        ("9.4", "1", "1", "XU"),  # prefix
                        ("9.4", "1", "3.4", "Kernel short desc"),
                    ]
                ),
            },
        )
        broker.connect()
        svc = PackageService(broker)
        p = svc.get_package("1")
        assert isinstance(p, PackageDef)
        assert p.name == "KERNEL"
        assert p.prefix == "XU"

    def test_returns_none_when_not_found(self):
        broker = FakeRPCBroker(
            responses={"DDR GETS ENTRY DATA": "[Data]\r\n"},
        )
        broker.connect()
        svc = PackageService(broker)
        assert svc.get_package("999") is None


class TestFilesByPackage:
    def test_lists_files_from_file_subfile(self):
        # Subfile #9.4,4 — FILE multiple on a package. Each entry's
        # .01 is a pointer-to-FILE so its external value renders as
        # the file name; the IEN of the subfile row is the file number.
        broker = FakeRPCBroker(
            responses={
                "DDR LISTER": _lister_rows(
                    [
                        ("2", "PATIENT"),
                        ("44", "HOSPITAL LOCATION"),
                    ]
                ),
            },
        )
        broker.connect()
        svc = PackageService(broker)
        files = svc.files_by_package("1")
        assert files == [2.0, 44.0]

    def test_walks_subfile_of_9_4(self):
        broker = FakeRPCBroker(responses={"DDR LISTER": _lister_rows([])})
        broker.connect()
        svc = PackageService(broker)
        svc.files_by_package("1")
        # Expected: DDR LISTER FILE=9.4 IENS=",1," — the FILE subfile
        # scoped to package IEN=1.
        call = next(c for c in broker.calls if c.rpc_name == "DDR LISTER")
        assert call.params[0] == "9.4"
        assert call.params[1] == ",1,"
