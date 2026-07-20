from src.filter import extract_targets


def test_extracts_cashtag_and_ca():
    text = "ape $PEPE now So11111111111111111111111111111111111111112"
    r = extract_targets(text)
    assert "PEPE" in r.symbols
    assert any(len(c) >= 32 for c in r.cas)
    assert r.is_spam is False


def test_duplicate_text_is_spam():
    text = "buy $DOGE"
    first = extract_targets(text)
    second = extract_targets(text, recent_hashes={first.text_hash})
    assert second.is_spam is True
    assert second.spam_reason == "duplicate_text"


def test_too_many_cas_is_spam():
    cas = " ".join(
        [
            "11111111111111111111111111111111",
            "22222222222222222222222222222222",
            "33333333333333333333333333333333",
            "44444444444444444444444444444444",
        ]
    )
    r = extract_targets(f"rugs {cas}", max_cas_per_message=3)
    assert r.is_spam is True
    assert r.spam_reason == "too_many_cas"


def test_new_account_is_spam():
    r = extract_targets("moon $WIF", account_age_days=0.5)
    assert r.is_spam is True
    assert r.spam_reason == "new_account"


def test_no_targets_empty_lists():
    r = extract_targets("hello world")
    assert r.symbols == []
    assert r.cas == []
    assert r.is_spam is False
