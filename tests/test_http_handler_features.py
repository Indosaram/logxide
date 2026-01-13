import sys
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import logxide
from logxide import HTTPHandler

logxide._install()
import logging

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


def run_server(server):
    server.serve_forever()


def test_global_context():
    RECEIVED_PAYLOADS.clear()

    server = HTTPServer(("localhost", 8082), MockHTTPHandler)
    server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    server_thread.start()

    handler = HTTPHandler(
        url="http://localhost:8082",
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
    time.sleep(0.5)

    server.shutdown()

    assert len(RECEIVED_PAYLOADS) > 0, "No payloads received"
    payload = RECEIVED_PAYLOADS[0]
    assert isinstance(payload, list), f"Expected list, got {type(payload)}"
    record = payload[0]

    assert record.get("application") == "test-app", f"Missing application: {record}"
    assert record.get("environment") == "testing", f"Missing environment: {record}"
    assert record.get("version") == 123, f"Missing version: {record}"
    print("✅ test_global_context PASSED")


def test_transform_callback():
    RECEIVED_PAYLOADS.clear()

    server = HTTPServer(("localhost", 8083), MockHTTPHandler)
    server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    server_thread.start()

    def transform(records):
        return {
            "logs": [{"message": r["msg"], "level": r["levelname"]} for r in records],
            "meta": {"count": len(records)},
        }

    handler = HTTPHandler(
        url="http://localhost:8083",
        batch_size=2,
        transform_callback=transform,
    )

    logger = logging.getLogger("test_transform")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info("Message 1")
    logger.warning("Message 2")
    time.sleep(0.5)

    server.shutdown()

    assert len(RECEIVED_PAYLOADS) > 0, "No payloads received"
    payload = RECEIVED_PAYLOADS[0]

    assert "logs" in payload, f"Missing 'logs' key: {payload}"
    assert "meta" in payload, f"Missing 'meta' key: {payload}"
    assert payload["meta"]["count"] == 2, f"Wrong count: {payload}"
    print("✅ test_transform_callback PASSED")


def test_context_provider():
    RECEIVED_PAYLOADS.clear()

    server = HTTPServer(("localhost", 8084), MockHTTPHandler)
    server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    server_thread.start()

    call_count = [0]

    def dynamic_context():
        call_count[0] += 1
        return {"batch_id": call_count[0], "timestamp": "2026-01-13T00:00:00Z"}

    handler = HTTPHandler(
        url="http://localhost:8084",
        batch_size=1,
        context_provider=dynamic_context,
    )

    logger = logging.getLogger("test_context_provider")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info("First message")
    time.sleep(0.3)
    logger.info("Second message")
    time.sleep(0.3)

    server.shutdown()

    assert len(RECEIVED_PAYLOADS) >= 2, (
        f"Expected 2+ payloads, got {len(RECEIVED_PAYLOADS)}"
    )

    first_record = RECEIVED_PAYLOADS[0][0]
    second_record = RECEIVED_PAYLOADS[1][0]

    assert first_record.get("batch_id") == 1, f"Wrong batch_id: {first_record}"
    assert second_record.get("batch_id") == 2, f"Wrong batch_id: {second_record}"
    print("✅ test_context_provider PASSED")


def test_manual_flush():
    RECEIVED_PAYLOADS.clear()

    server = HTTPServer(("localhost", 8085), MockHTTPHandler)
    server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    server_thread.start()

    handler = HTTPHandler(
        url="http://localhost:8085",
        batch_size=100,
        flush_interval=3600,
    )

    logger = logging.getLogger("test_flush")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info("Buffered message")

    assert len(RECEIVED_PAYLOADS) == 0, "Should not have sent yet"

    handler.flush()
    time.sleep(0.3)

    server.shutdown()

    assert len(RECEIVED_PAYLOADS) > 0, "Flush should have sent the message"
    print("✅ test_manual_flush PASSED")


def test_extra_fields_complex_types():
    RECEIVED_PAYLOADS.clear()

    server = HTTPServer(("localhost", 8086), MockHTTPHandler)
    server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    server_thread.start()

    handler = HTTPHandler(
        url="http://localhost:8086",
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
    time.sleep(0.5)

    server.shutdown()

    assert len(RECEIVED_PAYLOADS) > 0, "No payloads received"
    record = RECEIVED_PAYLOADS[0][0]
    extra = record.get("extra", {})

    assert extra.get("user_id") == 12345, f"Wrong user_id: {extra}"
    assert extra.get("tags") == ["important", "urgent"], f"Wrong tags: {extra}"
    assert extra.get("metadata", {}).get("nested", {}).get("deep") is True, (
        f"Wrong nested: {extra}"
    )
    print("✅ test_extra_fields_complex_types PASSED")


def test_error_callback():
    ERROR_MESSAGES.clear()

    def on_error(msg):
        ERROR_MESSAGES.append(msg)

    handler = HTTPHandler(
        url="http://localhost:9999",
        batch_size=1,
        error_callback=on_error,
    )

    logger = logging.getLogger("test_error_callback")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info("This will fail")
    time.sleep(0.5)

    assert len(ERROR_MESSAGES) > 0, "Error callback should have been called"
    print(f"✅ test_error_callback PASSED (error: {ERROR_MESSAGES[0][:50]}...)")


if __name__ == "__main__":
    test_global_context()
    test_transform_callback()
    test_context_provider()
    test_manual_flush()
    test_extra_fields_complex_types()
    test_error_callback()
    print("\n🎉 All tests passed!")
