from src.database import (
    fetch_mentions_since,
    init_db,
    insert_mention,
    last_alert_at,
    record_alert,
)


def test_insert_and_fetch_excludes_spam(tmp_path):
    db = str(tmp_path / "meme.db")
    init_db(db)
    insert_mention(
        db,
        created_at="2026-07-20T12:00:00+00:00",
        channel_id="1",
        user_id="u1",
        text_hash="a",
        text="buy $PEPE",
        symbols=["PEPE"],
        cas=[],
        sentiment_compound=0.8,
        is_positive=True,
        is_spam=False,
    )
    insert_mention(
        db,
        created_at="2026-07-20T12:01:00+00:00",
        channel_id="1",
        user_id="u2",
        text_hash="b",
        text="spam $PEPE",
        symbols=["PEPE"],
        cas=[],
        sentiment_compound=0.8,
        is_positive=True,
        is_spam=True,
    )
    rows = fetch_mentions_since(db, key="PEPE", since_iso="2026-07-20T00:00:00+00:00")
    assert len(rows) == 1
    assert rows[0]["is_positive"] is True


def test_fetch_mentions_since_matches_ca_key(tmp_path):
    db = str(tmp_path / "meme.db")
    init_db(db)
    ca = "7GCihgDB8fe6KNjn2MYTKz1c2J4q8Z4Um8cb8a8Sn2nd"
    insert_mention(
        db,
        created_at="2026-07-20T12:00:00+00:00",
        channel_id="1",
        user_id="u1",
        text_hash="c",
        text="check this CA",
        symbols=[],
        cas=[ca],
        sentiment_compound=0.5,
        is_positive=True,
        is_spam=False,
    )
    rows = fetch_mentions_since(db, key=ca, since_iso="2026-07-20T00:00:00+00:00")
    assert len(rows) == 1
    assert rows[0]["cas"] == [ca]
    wrong = fetch_mentions_since(
        db, key="wrong-ca-key", since_iso="2026-07-20T00:00:00+00:00"
    )
    assert wrong == []


def test_alert_cooldown_helpers(tmp_path):
    db = str(tmp_path / "meme.db")
    init_db(db)
    assert last_alert_at(db, key="PEPE") is None
    record_alert(db, key="PEPE", sent_at="2026-07-20T12:00:00+00:00", payload_summary="x")
    assert last_alert_at(db, key="PEPE") == "2026-07-20T12:00:00+00:00"
