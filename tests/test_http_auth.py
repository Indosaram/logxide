import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import logxide

sys.modules["logging"] = logxide.logging
logxide._install()

import logging  # noqa: E402

import pytest  # noqa: E402

RESULTS = []


class AuthMockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def do_POST(self):
        auth_header = self.headers.get("Authorization")
        api_key = self.headers.get("X-API-KEY")

        success = auth_header == "Bearer my-secret-token" and api_key == "key-123"
        RESULTS.append(success)

        self.send_response(200 if success else 401)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress server logs during tests


@pytest.fixture()
def mock_server():
    """Start a mock HTTP server on an OS-assigned port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), AuthMockHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()


def test_http_auth(mock_server):
    RESULTS.clear()
    port = mock_server

    from logxide import HTTPHandler

    handler = HTTPHandler(
        url=f"http://127.0.0.1:{port}",
        headers={"Authorization": "Bearer my-secret-token", "X-API-KEY": "key-123"},
        batch_size=2,
    )

    logger = logging.getLogger("auth_test")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info("Authenticated message 1")
    logger.info("Authenticated message 2")

    logxide.flush()

    # Poll for results with timeout
    deadline = time.monotonic() + 10
    while not RESULTS and time.monotonic() < deadline:
        time.sleep(0.2)

    assert RESULTS, "No authentication results received from mock server"
    assert all(RESULTS), f"Authentication header verification failed: {RESULTS}"
