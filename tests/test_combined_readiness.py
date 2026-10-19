from meta_analyse.history_progress import Progress, combined_readiness


def test_missing_feed_cannot_be_green():
    result = combined_readiness({"candles": Progress(100, "verified", 10, 10)})
    assert result.percent is None
    assert "trades" in result.status


def test_slowest_required_feed_controls_readiness():
    streams = {
        "candles": Progress(100, "verified", 10, 10),
        "trades": Progress(70, "partial", 7, 10),
        "ticks": Progress(90, "partial", 9, 10),
    }
    assert combined_readiness(streams).percent == 70


def test_complete_requires_all_feeds_verified():
    streams = {kind: Progress(100, "verified", 10, 10)
               for kind in ("candles", "trades", "ticks")}
    result = combined_readiness(streams)
    assert result.percent == 100
    assert result.status == "verified"


def test_source_limited_never_green():
    streams = {kind: Progress(100, "verified", 10, 10)
               for kind in ("candles", "trades", "ticks")}
    streams["ticks"] = Progress(99, "source-limited", 9, 10)
    result = combined_readiness(streams)
    assert result.percent == 99
    assert result.status == "source-limited"
