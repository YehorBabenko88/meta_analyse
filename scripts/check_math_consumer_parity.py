"""Exact-source parity gate for Meta -> Math market-profile migration.

This is an offline source-contract check, not a production package adapter or
evidence of real market data. Never silently substitute a synthetic Math module.
"""
from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import subprocess
import sys

MATH_SHA = "ed4339a30e4a97bf29f70b45627bf988bc1338b1"
MATH_BLOB = "1c7d46e92df966a6eebfd1311370b01ab5bbee1d"
MATH_API_BLOB = "ebe6b1ae286ba07dd9728d656780ddf8a5871853"
MATH_PROJECT_BLOB = "82876b8a6fe14cc6ddfddc6b2f3785206c82d895"


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "--no-replace-objects", "-C", str(root), *args],
        text=True, stderr=subprocess.DEVNULL,
    ).strip()


def load_math(root: Path):
    root = root.resolve(strict=True)
    source = (root / "python" / "market_profile_math.py").resolve(strict=True)
    if not source.is_relative_to(root):
        raise ValueError("Math source escapes its pinned checkout")
    if git(root, "rev-parse", "HEAD") != MATH_SHA:
        raise ValueError("unexpected Math commit")
    if git(root, "rev-parse", "HEAD:python/market_profile_math.py") != MATH_BLOB:
        raise ValueError("unexpected Math source object")
    committed = subprocess.check_output(
        ["git", "--no-replace-objects", "-C", str(root),
         "show", "HEAD:python/market_profile_math.py"],
        stderr=subprocess.DEVNULL,
    )
    working = source.read_bytes()
    # Windows checkout can expand only LF -> CRLF. Verify actual raw Git
    # object bytes before allowing that single transport transformation.
    normalized = working.replace(b"\r\n", b"\n")
    if working != committed and (
        normalized != committed or b"\r" in working.replace(b"\r\n", b"")
    ):
        raise ValueError("unexpected Math working file bytes")
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("modified Math source checkout")
    spec = importlib.util.spec_from_file_location("_pinned_market_profile_math", source)
    if spec is None or spec.loader is None:
        raise ValueError("unable to load pinned Math")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(math_module) -> None:
    from meta_analyse.core import Minute, price_bucket
    from meta_analyse.footprint import Footprint, FootprintCell

    D = Decimal
    zero = D(0)
    for i in range(1, 251):
        price, tick = D(i) / D(7), D("0.01")
        assert price_bucket(price, tick) == math_module.price_bucket(price, tick)
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    for i in range(1, 201):
        close = D(100 + i % 7)
        profile = {
            D("99"): D(i % 5),
            D("100"): D((i + 1) % 5),
            D("101"): D((i + 2) % 5),
        }
        minute = Minute(start, D("1"), close, close, close, close, profile=profile)
        assert minute.poc == math_module.volume_profile_poc(profile, close=close)
        cells = {
            price: FootprintCell(volume, D("0"), 1)
            for price, volume in profile.items()
        }
        footprint = Footprint("BTCUSDT", 0, 60000, D("1"), cells=cells)
        assert footprint.poc == math_module.volume_profile_poc(profile)
        for cell in cells.values():
            assert cell.delta == math_module.executed_volume_delta(
                cell.buy, cell.sell
            )
        assert footprint.delta == sum(
            (math_module.executed_volume_delta(c.buy, c.sell)
             for c in cells.values()), zero
        )

    empty_minute = Minute(start, D("1"), D("1"), D("1"), D("1"), D("1"))
    try:
        empty_minute.poc
    except ValueError:
        pass
    else:
        raise AssertionError("Meta empty minute POC must reject")
    try:
        math_module.volume_profile_poc({}, close=D("1"))
    except ValueError:
        pass
    else:
        raise AssertionError("Math empty minute POC must reject")
    assert Footprint("BTCUSDT", 0, 60000, D("1")).poc is None
    assert math_module.volume_profile_poc({}) is None

    # Explicit known divergence: legacy Meta accepted zero, Math refuses it.
    assert price_bucket(zero, D("1")) == zero
    try:
        math_module.price_bucket(zero, D("1"))
    except ValueError:
        pass
    else:
        raise AssertionError("Math must refuse zero-priced market input")



def check_installed_api(root: Path) -> None:
    """Prove installed v1 API resolves to exact owned Math checkout bytes."""
    root = root.resolve(strict=True)
    checks = (
        ("python/market_compute_api.py", MATH_API_BLOB),
        ("python/market_profile_math.py", MATH_BLOB),
        ("pyproject.toml", MATH_PROJECT_BLOB),
    )
    for relative, expected_oid in checks:
        source = (root / relative).resolve(strict=True)
        if not source.is_relative_to(root):
            raise ValueError("Math source escapes checkout")
        if git(root, "rev-parse", "HEAD:" + relative) != expected_oid:
            raise ValueError("unexpected Math API source object")
        committed = subprocess.check_output(
            ["git", "--no-replace-objects", "-C", str(root), "show", "HEAD:" + relative],
            stderr=subprocess.DEVNULL,
        )
        working = source.read_bytes()
        if working != committed and (
            working.replace(b"\r\n", b"\n") != committed
            or b"\r" in working.replace(b"\r\n", b"")
        ):
            raise ValueError("unexpected Math API working bytes")
    if git(root, "rev-parse", "HEAD") != MATH_SHA:
        raise ValueError("wrong installed Math release")
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("dirty Math source")
    api = importlib.import_module("market_compute_api")
    kernel = importlib.import_module("market_profile_math")
    if Path(api.__file__).resolve(strict=True) != (root / "python/market_compute_api.py").resolve():
        raise ValueError("Math API imported from unapproved distribution")
    if Path(kernel.__file__).resolve(strict=True) != (root / "python/market_profile_math.py").resolve():
        raise ValueError("Math kernel imported from unapproved distribution")
    if importlib.metadata.version("unified-math-kernels") != "0.1.0":
        raise ValueError("unexpected Math package version")

    # Expanded Math-owned market algorithms are checked at pinned source,
    # without introducing another Meta implementation or synthetic live data.
    for name in (
        "tape_velocity_metrics", "wall_notional", "flow_window_metrics",
        "wall_turnover_ratios", "untouched_decimal_levels",
    ):
        if not callable(getattr(kernel, name, None)):
            raise ValueError("missing Math-owned migration symbol")
    tape = kernel.tape_velocity_metrics(
        ((1000, Decimal("100"), Decimal("2"), "Buy"),
         (1500, Decimal("101"), Decimal("1"), "Sell")),
        Decimal("100"), Decimal("1"), 5000, Decimal("2"), 1500,
        observed_price=Decimal("101"),
    )
    assert tape == (
        Decimal("0.4"), Decimal("60.2"), Decimal("200"), Decimal("101"),
        Decimal("1"),
    )
    assert kernel.wall_notional(Decimal("100"), Decimal("2")) == Decimal("200")
    assert kernel.flow_window_metrics(
        ((1000, Decimal("200"), "buy"), (1500, Decimal("101"), "sell")),
        1500, 5,
    ) == {
        "turnover_usd": Decimal("301"), "trades": 2,
        "buy_usd": Decimal("200"), "sell_usd": Decimal("101"),
        "trades_per_second": Decimal("0.4"),
    }
    assert kernel.wall_turnover_ratios(
        Decimal("100"), Decimal("2"), {60: Decimal("100")}
    )["ratios"][60] == Decimal("2")
    assert kernel.untouched_decimal_levels(
        ((1000, Decimal("102"), Decimal("99")),
         (2000, Decimal("103"), Decimal("99"))),
    ) == (("high", Decimal("103"), 2000), ("low", Decimal("99"), 2000))

    request = {
        "schema": "math.market.compute.v1",
        "execution_authority": False,
        "source": {
            "snapshot_sha256": "a" * 64,
            "as_of_ms": 1792200000000,
            "units": {"price": "quote/base", "volume": "base"},
        },
        "operations": [
            {"operation": "price_bucket", "input": {"price": "1.235", "tick": "0.01"}},
            {"operation": "volume_profile_poc", "input": {
                "profile": [{"price": "99", "volume": "3"},
                            {"price": "101", "volume": "3"}], "close": "101"}},
            {"operation": "volume_profile_poc", "input": {
                "profile": [{"price": "99", "volume": "3"},
                            {"price": "101", "volume": "3"}], "close": None}},
            {"operation": "executed_volume_delta", "input": {"buy": "3", "sell": "2"}},
        ],
    }
    receipt = api.compute_batch(request)
    assert receipt["schema"] == "math.market.result.v1"
    assert receipt["algorithm_version"] == "math.market.v1"
    assert receipt["execution_authority"] is False
    assert receipt["trading_authorized"] is False
    assert receipt["provenance"] == "CALLER_SUPPLIED_UNATTESTED"
    assert [r["value"] for r in receipt["results"]] == ["1.24", "101", "99", "1"]
    expected = hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                   allow_nan=False).encode()
    ).hexdigest()
    assert receipt["request_sha256"] == expected
    assert api.compute_batch(request) == receipt
    invalid = dict(request, execution_authority=True)
    try:
        api.compute_batch(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("Math execution authorization must be refused")

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_math_consumer_parity.py MATH_CHECKOUT")
    root = Path(sys.argv[1])
    check(load_math(root))
    check_installed_api(root)
    print("META_MATH_SOURCE_PARITY=PASS checks=price_bucket,minute_poc,footprint_poc,delta,refusal")
    print("MATH_INSTALLED_COMPUTE_API_V1=PASS source-pinned,call-contract-only")
    print("META_PRODUCTION_CONSUMER_CUTOVER=NOT_ESTABLISHED")
    print("REAL_MARKET_DATA=NOT_TESTED")


if __name__ == "__main__":
    main()
