import httpx
import pytest

from src.aggregator import AggregateDecision
from src.notifier import NotifierError, format_aggregate_alert, send_telegram_message


def test_format_aggregate_alert_includes_key():
    d = AggregateDecision(True, "PEPE", 5, 0.8, ["1"], ["moon $PEPE"], "ok")
    text = format_aggregate_alert(d, window_minutes=5)
    assert "PEPE" in text
    assert "5" in text


def test_send_telegram_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/sendMessage")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    send_telegram_message("tok", "1", "hi", client=client)


def test_send_telegram_error():
    transport = httpx.MockTransport(lambda r: httpx.Response(400, json={"ok": False}))
    client = httpx.Client(transport=transport)
    with pytest.raises(NotifierError):
        send_telegram_message("tok", "1", "hi", client=client)
