import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import logxide
from logxide import HTTPHandler

logxide._install()
import logging  # noqa: E402

RECEIVED_PAYLOADS = []
ERROR_MESSAGES = []


class MockHTTPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8"))
            RECEIVED_PAYLOADS.append(payload)
        except json.JSONDecodeError:
            RECEIVED_PAYLOADS.append(body.decode("utf-8"))

        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


@pytest.fixture()
def mock_server():
    """Start a mock HTTP server on an OS-assigned port and return the port."""
    server = HTTPServer(("127.0.0.1", 0), MockHTTPHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()


def _wait_for_payloads(count=1, timeout=5.0):
    """Poll RECEIVED_PAYLOADS until we have at least `count` entries."""
    deadline = time.monotonic() + timeout
    while len(RECEIVED_PAYLOADS) < count and time.monotonic() < deadline:
        time.sleep(0.1)


def test_global_context(mock_server):
    RECEIVED_PAYLOADS.clear()

    handler = HTTPHandler(
        url=f"http://127.0.0.1:{mock_server}",
        batch_size=1,
        global_context={
            "application": "test-app",
            "environment": "testing",
            "version": 123,
        },
    )

    logger = logging.getLogger("test_global_context")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info("Test message")
    _wait_for_payloads(1)

    assert len(RECEIVED_PAYLOADS) > 0, "No payloads received"
    payload = RECEIVED_PAYLOADS[0]
    assert isinstance(payload, list), f"Expected list, got {type(payload)}"
    record = payload[0]

    assert record.get("application") == "test-app", f"Missing application: {record}"
    assert record.get("environment") == "testing", f"Missing environment: {record}"
    assert record.get("version") == 123, f"Missing version: {record}"


def test_transform_callback(mock_server):
    RECEIVED_PAYLOADS.clear()

    def transform(records):
        return {
            "logs": [{"message": r["msg"], "level": r["levelname"]} for r in records],
            "meta": {"count": len(records)},
        }

    handler = HTTPHandler(
        url=f"http://127.0.0.1:{mock_server}",
        batch_size=2,
        transform_callback=transform,
    )

    logger = logging.getLogger("test_transform")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info("Message 1")
    logger.warning("Message 2")
    _wait_for_payloads(1)

    assert len(RECEIVED_PAYLOADS) > 0, "No payloads received"
    payload = RECEIVED_PAYLOADS[0]

    assert "logs" in payload, f"Missing 'logs' key: {payload}"
    assert "meta" in payload, f"Missing 'meta' key: {payload}"
    assert payload["meta"]["count"] == 2, f"Wrong count: {payload}"


def test_context_provider(mock_server):
    RECEIVED_PAYLOADS.clear()

    call_count = [0]

    def dynamic_context():
        call_count[0] += 1
        return {"batch_id": call_count[0], "timestamp": "2026-01-13T00:00:00Z"}

    handler = HTTPHandler(
        url=f"http://127.0.0.1:{mock_server}",
        batch_size=1,
        context_provider=dynamic_context,
    )

    logger = logging.getLogger("test_context_provider")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info("First message")
    _wait_for_payloads(1)
    logger.info("Second message")
    _wait_for_payloads(2)

    assert len(RECEIVED_PAYLOADS) >= 2, (
        f"Expected 2+ payloads, got {len(RECEIVED_PAYLOADS)}"
    )

    first_record = RECEIVED_PAYLOADS[0][0]
    second_record = RECEIVED_PAYLOADS[1][0]

    assert first_record.get("batch_id") == 1, f"Wrong batch_id: {first_record}"
    assert second_record.get("batch_id") == 2, f"Wrong batch_id: {second_record}"


def test_manual_flush(mock_server):
    RECEIVED_PAYLOADS.clear()

    handler = HTTPHandler(
        url=f"http://127.0.0.1:{mock_server}",
        batch_size=100,
        flush_interval=3600,
    )

    logger = logging.getLogger("test_flush")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info("Buffered message")

    assert len(RECEIVED_PAYLOADS) == 0, "Should not have sent yet"

    handler.flush()
    _wait_for_payloads(1)

    assert len(RECEIVED_PAYLOADS) > 0, "Flush should have sent the message"


def test_extra_fields_complex_types(mock_server):
    RECEIVED_PAYLOADS.clear()

    handler = HTTPHandler(
        url=f"http://127.0.0.1:{mock_server}",
        batch_size=1,
    )

    logger = logging.getLogger("test_extra_complex")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info(
        "Complex extra",
        extra={
            "user_id": 12345,
            "tags": ["important", "urgent"],
            "metadata": {"key": "value", "nested": {"deep": True}},
        },
    )
    _wait_for_payloads(1)

    assert len(RECEIVED_PAYLOADS) > 0, "No payloads received"
    record = RECEIVED_PAYLOADS[0][0]
    extra = record.get("extra", {})

    assert extra.get("user_id") == 12345, f"Wrong user_id: {extra}"
    assert extra.get("tags") == ["important", "urgent"], f"Wrong tags: {extra}"
    assert extra.get("metadata", {}).get("nested", {}).get("deep") is True, (
        f"Wrong nested: {extra}"
    )


def test_error_callback():
    ERROR_MESSAGES.clear()

    def on_error(msg):
        ERROR_MESSAGES.append(msg)

    handler = HTTPHandler(
        url="http://127.0.0.1:1",  # Port 1 — guaranteed to fail
        batch_size=1,
        error_callback=on_error,
    )

    logger = logging.getLogger("test_error_callback")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info("This will fail")

    deadline = time.monotonic() + 5.0
    while not ERROR_MESSAGES and time.monotonic() < deadline:
        time.sleep(0.1)

    assert len(ERROR_MESSAGES) > 0, "Error callback should have been called"
