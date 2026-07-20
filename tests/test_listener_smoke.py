from pathlib import Path

from src.channels import upsert_suggested
from src.listener import alerts_allowed, enabled_channel_keys


def test_alerts_allowed_respects_stop(tmp_path):
    stop = tmp_path / "STOP"
    assert alerts_allowed(str(stop)) is True
    stop.write_text("")
    assert alerts_allowed(str(stop)) is False


def test_enabled_channel_keys(tmp_path):
    path = tmp_path / "channels.yaml"
    upsert_suggested(
        str(path),
        username="a",
        channel_id=1,
        score=0.5,
        reason="x",
    )
    text = Path(path).read_text().replace("suggested", "enabled")
    Path(path).write_text(text)

    keys = enabled_channel_keys(str(path))

    assert "a" in keys or 1 in keys
