from pathlib import Path

from src.config import SOURCE_PACKAGE
from src.quality import inspect_bytes


def _read(name: str) -> bytes:
    return (SOURCE_PACKAGE / name).read_bytes()


def test_03_hourly_input():
    report = inspect_bytes("03.csv", _read("03_小时级源荷气象电价数据.csv"))
    assert report["rows"] == 5832
    assert report["time"]["interval_minutes"] == 60
    assert report["time"]["coverage"] == 1.0
    assert report["status"] == "usable_with_warnings"
    assert any(w["code"] == "PARTIAL_PERIOD" for w in report["warnings"])
    assert report["mapping"]["load_mw"] == "有功负荷(MW)"


def test_05_dispatch_balance():
    report = inspect_bytes("05.csv", _read("05_风光负荷同步出力数据.csv"))
    assert report["rows"] == 5832
    assert report["time"]["interval_minutes"] == 60
    assert not any(w["code"] == "BALANCE_MISMATCH" for w in report["warnings"])


def test_04_time_only_typical_day():
    report = inspect_bytes("04.csv", _read("04_典型日15分钟运行曲线.csv"))
    assert report["rows"] == 96
    assert report["time"]["time_only"] is True
    assert report["time"]["interval_minutes"] == 15
    assert any(w["code"] == "TIME_ONLY" for w in report["warnings"])


def test_unsupported_file():
    try:
        inspect_bytes("bad.txt", b"a,b\n1,2")
    except ValueError as exc:
        assert "csv" in str(exc).lower() or "xlsx" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")
