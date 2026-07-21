"""Smoke tests for FastAPI dashboard."""

from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.app import app


def test_index_and_overview_endpoints():
    client = TestClient(app)
    index = client.get("/")
    assert index.status_code == 200
    assert "crypto-meme-bot" in index.text

    styles = client.get("/styles.css")
    assert styles.status_code == 200
    assert "var(--bg)" in styles.text

    overview = client.get("/api/overview")
    assert overview.status_code == 200
    data = overview.json()
    assert "channels" in data
    assert "hot_keys" in data
    assert "stop_active" in data
