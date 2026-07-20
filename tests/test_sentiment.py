from src.sentiment import score_text


def test_positive_text():
    compound, is_pos = score_text("This is great, amazing, excellent moon!")
    assert compound > 0.05
    assert is_pos is True


def test_negative_text():
    compound, is_pos = score_text("This is terrible, awful, scam rug horrible")
    assert compound < 0
    assert is_pos is False


def test_threshold_gates_positive_flag():
    compound, is_pos = score_text("ok fine", positive_threshold=0.99)
    assert is_pos is False
    assert isinstance(compound, float)
