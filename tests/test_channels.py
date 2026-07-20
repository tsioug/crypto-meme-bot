import logging

from src.channels import Channel, load_channels, list_enabled, save_channels, upsert_suggested


def test_missing_file_returns_empty_and_warns(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert load_channels(str(tmp_path / "missing.yaml")) == []

    assert "missing" in caplog.text.lower()


def test_corrupt_yaml_returns_empty_and_warns(tmp_path, caplog):
    path = tmp_path / "channels.yaml"
    path.write_text("{not: valid: yaml: [")

    with caplog.at_level(logging.WARNING):
        assert load_channels(str(path)) == []

    assert "could not load" in caplog.text.lower()


def test_save_channels_round_trips(tmp_path):
    path = tmp_path / "nested" / "channels.yaml"
    channels = [
        Channel(
            id=123,
            username="foo",
            status="enabled",
            score=0.8,
            reason="manual",
            updated_at="2026-01-01T00:00:00+00:00",
        )
    ]

    save_channels(str(path), channels)

    assert load_channels(str(path)) == channels


def test_upsert_suggested_does_not_override_enabled(tmp_path):
    path = tmp_path / "channels.yaml"
    path.write_text(
        "channels:\n"
        "  - username: foo\n"
        "    id: null\n"
        "    status: enabled\n"
        "    score: 0.1\n"
        "    reason: manual\n"
        "    updated_at: '2026-01-01T00:00:00+00:00'\n"
    )

    channel = upsert_suggested(
        str(path), username="foo", channel_id=None, score=0.9, reason="hot"
    )

    assert channel.status == "enabled"
    assert channel.score == 0.9
    assert channel.reason == "hot"
    assert list_enabled(str(path))[0].username == "foo"


def test_upsert_suggested_does_not_override_ignored(tmp_path):
    path = tmp_path / "channels.yaml"
    path.write_text(
        "channels:\n"
        "  - username: bad\n"
        "    id: null\n"
        "    status: ignored\n"
        "    score: 0.1\n"
        "    reason: spam\n"
        "    updated_at: '2026-01-01T00:00:00+00:00'\n"
    )

    channel = upsert_suggested(
        str(path), username="bad", channel_id=None, score=0.99, reason="still"
    )

    assert channel.status == "ignored"
    assert channel.score == 0.99
    assert channel.reason == "still"


def test_new_suggested_is_created(tmp_path):
    path = tmp_path / "channels.yaml"

    channel = upsert_suggested(
        str(path), username="newch", channel_id=1, score=0.5, reason="density"
    )

    assert channel.status == "suggested"
    assert load_channels(str(path)) == [channel]


def test_upsert_matches_existing_channel_by_id(tmp_path):
    path = tmp_path / "channels.yaml"
    existing = Channel(
        id=42,
        username=None,
        status="enabled",
        score=0.1,
        reason="manual",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    save_channels(str(path), [existing])

    channel = upsert_suggested(
        str(path), username="resolved", channel_id=42, score=0.7, reason="active"
    )

    assert channel.id == 42
    assert channel.status == "enabled"
    assert len(load_channels(str(path))) == 1


def test_list_enabled_filters_other_statuses(tmp_path):
    path = tmp_path / "channels.yaml"
    common = {"id": None, "score": 0.1, "reason": "test", "updated_at": "now"}
    save_channels(
        str(path),
        [
            Channel(username="on", status="enabled", **common),
            Channel(username="maybe", status="suggested", **common),
            Channel(username="off", status="ignored", **common),
        ],
    )

    assert [channel.username for channel in list_enabled(str(path))] == ["on"]
