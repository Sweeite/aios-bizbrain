"""
Slice 8: Chat endpoint — SSE streaming from AccountAgent via HTTP.
Tests exercise the HTTP interface only; Anthropic client is injected per test.
"""
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_streaming_client(chunks: tuple[str, ...] = ("Hello world",)):
    """Mock that simulates Anthropic streaming API context manager."""
    client = MagicMock()
    stream_ctx = MagicMock()
    stream_ctx.__enter__ = MagicMock(return_value=stream_ctx)
    stream_ctx.__exit__ = MagicMock(return_value=False)
    stream_ctx.text_stream = iter(chunks)
    client.messages.stream.return_value = stream_ctx
    return client


def _client(anthropic_mock) -> TestClient:
    from app.main import app
    from app.chat import get_anthropic_client
    app.dependency_overrides[get_anthropic_client] = lambda: anthropic_mock
    return TestClient(app)


def _parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


# ---------------------------------------------------------------------------
# Cycle A: POST /chat returns 200 with text/event-stream content-type
# ---------------------------------------------------------------------------

class TestChatEndpointExists:
    def test_post_chat_returns_200_and_event_stream_content_type(self):
        http = _client(_mock_streaming_client())
        resp = http.post("/chat", json={"message": "hi", "client_id": "c-001"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Cycle B: SSE body contains text chunk events
# ---------------------------------------------------------------------------

class TestChatSSEChunks:
    def test_response_contains_text_events(self):
        http = _client(_mock_streaming_client(chunks=("Hello ", "world")))
        resp = http.post("/chat", json={"message": "hi", "client_id": "c-001"})

        events = _parse_sse(resp.text)
        text_events = [e for e in events if "text" in e]
        assert len(text_events) >= 1
        full_text = "".join(e["text"] for e in text_events)
        assert "Hello" in full_text

    def test_chunks_are_concatenated_in_order(self):
        http = _client(_mock_streaming_client(chunks=("alpha", " beta", " gamma")))
        resp = http.post("/chat", json={"message": "hi", "client_id": "c-001"})

        events = _parse_sse(resp.text)
        texts = [e["text"] for e in events if "text" in e]
        assert texts == ["alpha", " beta", " gamma"]


# ---------------------------------------------------------------------------
# Cycle C: SSE stream ends with {"done": true}
# ---------------------------------------------------------------------------

class TestChatSSEDone:
    def test_last_event_is_done(self):
        http = _client(_mock_streaming_client(chunks=("Some text",)))
        resp = http.post("/chat", json={"message": "hi", "client_id": "c-001"})

        events = _parse_sse(resp.text)
        assert events[-1] == {"done": True}

    def test_done_event_comes_after_text_events(self):
        http = _client(_mock_streaming_client(chunks=("chunk",)))
        resp = http.post("/chat", json={"message": "hi", "client_id": "c-001"})

        events = _parse_sse(resp.text)
        text_indices = [i for i, e in enumerate(events) if "text" in e]
        done_index = next(i for i, e in enumerate(events) if e.get("done"))
        assert text_indices[-1] < done_index


# ---------------------------------------------------------------------------
# Cycle D: Validation
# ---------------------------------------------------------------------------

class TestChatValidation:
    def test_missing_message_returns_422(self):
        http = _client(_mock_streaming_client())
        resp = http.post("/chat", json={"client_id": "c-001"})
        assert resp.status_code == 422

    def test_client_id_defaults_to_northpath(self):
        http = _client(_mock_streaming_client(chunks=("ok",)))
        resp = http.post("/chat", json={"message": "hello"})
        assert resp.status_code == 200
