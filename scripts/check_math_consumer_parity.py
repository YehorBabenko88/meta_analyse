"""Exact-source parity gate for Meta -> Math market-profile migration.

This is an offline source-contract check, not a production package adapter or
evidence of real market data. Never silently substitute a synthetic Math module.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import subprocess
import sys

MATH_SHA = "c637500f857b95b2db731eb05dcdf26f52c7a06f"
MATH_BLOB = "430ee36dfe0f71872e4f2ed35d4eaac918989fa4"


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


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_math_consumer_parity.py MATH_CHECKOUT")
    check(load_math(Path(sys.argv[1])))
    print("META_MATH_SOURCE_PARITY=PASS checks=price_bucket,minute_poc,footprint_poc,delta,refusal")
    print("MATH_RUNTIME_IMPORT=NOT_ESTABLISHED")
    print("REAL_MARKET_DATA=NOT_TESTED")


if __name__ == "__main__":
    main()
