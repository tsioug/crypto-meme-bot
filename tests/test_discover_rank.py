from src.discover_rank import ChannelSample, rank_channel


def test_dense_channel_outranks_empty():
    hot = ChannelSample("hot", 1, 50_000, 30.0, ["moon $PEPE", "buy $WIF now"])
    cold = ChannelSample("cold", 2, 50_000, 30.0, ["gm", "hello"])
    assert rank_channel(hot)[0] > rank_channel(cold)[0]


def test_spam_samples_penalized():
    clean = ChannelSample("c", 1, 10_000, 10.0, ["nice $PEPE"])
    spammy = ChannelSample(
        "s",
        2,
        10_000,
        10.0,
        [
            "x " + " ".join(["11111111111111111111111111111111"] * 4),
        ],
    )
    assert rank_channel(clean)[0] > rank_channel(spammy)[0]


def test_score_is_clamped_to_unit_interval():
    saturated = ChannelSample("max", 3, 1_000_000, 600.0, ["$PEPE"])
    empty = ChannelSample("min", 4, -1, -1.0, [])

    assert rank_channel(saturated)[0] == 1.0
    assert rank_channel(empty)[0] == 0.0


def test_reason_summarizes_strongest_factor():
    active = ChannelSample("active", 5, 0, 60.0, [])

    assert "activity" in rank_channel(active)[1]
