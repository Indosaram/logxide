import sys
import os

# AGGRESSIVE REPLACEMENT BEFORE ANY LOGGING IMPORTS
import logxide
import logging

sys.modules["logging"] = logxide.logging
logxide._install()

import time
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# 전역 변수로 핸들러와 로거 유지 (GC 방지)
AUTH_HANDLER = None
AUTH_LOGGER = None
RESULTS = []


class AuthMockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        auth_header = self.headers.get("Authorization")
        api_key = self.headers.get("X-API-KEY")

        sys.stderr.write(
            f"\n[MockServer] Received headers: Auth={auth_header}, API-KEY={api_key}\n"
        )

        success = auth_header == "Bearer my-secret-token" and api_key == "key-123"
        RESULTS.append(success)

        self.send_response(200 if success else 401)
        self.end_headers()


def run_server(server):
    server.serve_forever()


# 불사신 리스트 (GC 방지용 끝판왕)
IMMORTAL_STORAGE = []


def test_http_auth():
    print("Python: Importing logxide and standard logging...")
    import logxide
    import logging
    from logxide import HTTPHandler

    # 0. 강제 설치
    logxide._install()

    print("Python: Starting Mock Server...")
    server = HTTPServer(("localhost", 8081), AuthMockHandler)
    server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    server_thread.start()

    print("Python: Creating HTTPHandler...")
    handler = HTTPHandler(
        url="http://localhost:8081",
        headers={"Authorization": "Bearer my-secret-token", "X-API-KEY": "key-123"},
        batch_size=2,
    )
    IMMORTAL_STORAGE.append(handler)

    print(f"Python: Creating logger via standard logging...")
    logger = logging.getLogger("auth_test")
    IMMORTAL_STORAGE.append(logger)

    # 디버깅: 객체 아이덴티티 확인
    try:
        rust_obj = logger.info.__self__
        print(f"Python DEBUG: logger.info.__self__ id = {id(rust_obj)}")
        print(f"Python DEBUG: rust_obj type = {type(rust_obj)}")
    except Exception as e:
        print(f"Python DEBUG: Failed to get rust_obj: {e}")

    logger.setLevel(logging.DEBUG)

    print("Python: Adding handler to logger...")
    logger.addHandler(handler)

    print("Python: Sending logs...")
    logger.info("Authenticated message 1")
    logger.info("Authenticated message 2")

    print("Python: Flushing logxide...")
    import logxide as logxide_mod

    logxide_mod.flush()

    print("Python: Waiting for logs to be processed (10s)...")
    for i in range(10):
        time.sleep(1)
        if RESULTS:
            break

    server.shutdown()

    if RESULTS and all(RESULTS):
        print("\n✅ SUCCESS: Authentication headers correctly received!")
    else:
        print(f"\n❌ FAILURE: Results={RESULTS}")
        sys.exit(1)


if __name__ == "__main__":
    test_http_auth()
