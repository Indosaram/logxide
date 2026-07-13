"""
Regression tests locking design §6 criterion 2 (overflow + flush accounting) and
criterion 3 (GIL-free default HTTP delivery), plus worker teardown.

These drive the raw Rust HTTPHandler (logxide.RustHTTPHandler) directly so record
accounting is exact: emit() increments `emitted`, the worker increments
`sink_acknowledged`/`delivery_failed`, and overflow increments `queue_dropped`.

Note on Block + local sinks: Phase 2's Block strategy blocks inside emit() while the
GIL is held (a fully GIL-safe Block is Phase 4's detached path). A local *Python* HTTP
sink needs that same GIL to answer requests, so a small-capacity Block against a local
thread-sink would deadlock by construction. Block tests therefore size capacity so
emit() never blocks, and the GIL-free criterion uses an out-of-process sink whose GIL
is independent of the producer's.
"""

import json
import multiprocessing as mp
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import logxide
from logxide import LogRecord, RustHTTPHandler


def _make_server(delay=0.0):
    received = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_POST(self):
            if delay:
                time.sleep(delay)
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                for rec in json.loads(body.decode("utf-8")):
                    received.append(rec)
            except (json.JSONDecodeError, TypeError):
                pass
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, received


def _subprocess_sink(port_queue):
    """HTTP sink running in a separate process (its own, independent GIL)."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port_queue.put(server.server_address[1])
    server.serve_forever()


def _record(i):
    return LogRecord(
        name="overflow.test",
        levelno=20,
        pathname="test.py",
        lineno=i,
        msg=f"message-{i}",
    )


@pytest.mark.parametrize("overflow", ["drop_newest", "drop_oldest", "block"])
def test_overflow_accounting_identity(overflow):
    server, port, _received = _make_server(delay=0.05)
    try:
        # Block blocks in emit() while holding the GIL (Phase 2); size capacity so it
        # never blocks against the local Python sink. Drop strategies stay small so the
        # slow sink forces real overflow.
        capacity = 100000 if overflow == "block" else 2
        handler = RustHTTPHandler(
            f"http://127.0.0.1:{port}",
            capacity=capacity,
            batch_size=1,
            flush_interval=3600,
            overflow=overflow,
        )
        n = 30
        for i in range(n):
            handler.emit(_record(i))

        handler.flush()
        metrics = handler.get_metrics()

        assert metrics["emitted"] == n, metrics
        assert (
            metrics["sink_acknowledged"]
            + metrics["queue_dropped"]
            + metrics["delivery_failed"]
            == metrics["emitted"]
        ), metrics
        assert metrics["in_flight"] == 0, metrics

        if overflow == "block":
            assert metrics["queue_dropped"] == 0, metrics

        handler.shutdown()
    finally:
        server.shutdown()


def test_flush_drains_all_records():
    server, port, received = _make_server(delay=0.0)
    try:
        handler = RustHTTPHandler(
            f"http://127.0.0.1:{port}",
            capacity=100000,
            batch_size=1,
            flush_interval=3600,
            overflow="block",
        )
        n = 200
        for i in range(n):
            handler.emit(_record(i))

        handler.flush()
        metrics = handler.get_metrics()

        assert metrics["emitted"] == n, metrics
        assert metrics["in_flight"] == 0, metrics
        assert metrics["sink_acknowledged"] == n, metrics
        # Drain guarantees every enqueued record was delivered before flush returned.
        assert len(received) == n, f"sink received {len(received)} of {n}"

        handler.shutdown()
    finally:
        server.shutdown()


def test_default_http_delivery_is_gil_free():
    ctx = mp.get_context("spawn")
    port_queue = ctx.Queue()
    proc = ctx.Process(target=_subprocess_sink, args=(port_queue,), daemon=True)
    proc.start()
    try:
        try:
            # spawn re-imports the module (incl. logxide) in the child; cold CI
            # runners (Windows / older Python) can be slow, so allow ample time.
            port = port_queue.get(timeout=60)
        except queue.Empty:
            pytest.skip("out-of-process HTTP sink did not start on this runner")
        handler = RustHTTPHandler(
            f"http://127.0.0.1:{port}",
            capacity=100000,
            batch_size=1,
            flush_interval=3600,
            overflow="block",
        )
        n = 50
        for i in range(n):
            handler.emit(_record(i))

        # Hold the GIL in a tight pure-Python loop (no sleep => GIL never released).
        # The sink lives in another process with its own GIL, so if the worker's default
        # serialization + POST are GIL-free, deliveries land while this loop runs.
        total = 0
        deadline = time.perf_counter() + 1.0
        while time.perf_counter() < deadline:
            total += 1

        metrics = handler.get_metrics()
        assert metrics["sink_acknowledged"] > 0, (
            f"worker made no progress while the producer GIL was held: {metrics}"
        )

        handler.shutdown()
    finally:
        proc.terminate()
        proc.join(timeout=5)


def test_worker_shutdown_joins_promptly():
    server, port, _received = _make_server(delay=0.0)
    try:
        handler = RustHTTPHandler(
            f"http://127.0.0.1:{port}",
            capacity=100000,
            batch_size=1,
            flush_interval=3600,
            overflow="block",
        )
        for i in range(10):
            handler.emit(_record(i))

        start = time.perf_counter()
        handler.shutdown()  # drains + sets flag + joins the worker thread
        elapsed = time.perf_counter() - start

        # shutdown() returning at all proves the join completed (a live worker would
        # otherwise block forever; Rust worker threads are not visible to
        # threading.active_count()). Bound it well under the pytest timeout.
        assert elapsed < 10.0, f"shutdown took {elapsed:.2f}s"

        metrics = handler.get_metrics()
        assert metrics["in_flight"] == 0, metrics

        # Double shutdown must be safe (idempotent, no hang/panic).
        handler.shutdown()
    finally:
        server.shutdown()


def test_public_wrapper_get_metrics_and_flush():
    server, port, _received = _make_server(delay=0.0)
    try:
        logxide._install()
        import logging

        handler = logxide.HTTPHandler(
            url=f"http://127.0.0.1:{port}",
            batch_size=1,
            flush_interval=3600,
            overflow="block",
        )
        logger = logging.getLogger("overflow.wrapper")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        for i in range(5):
            logger.info("wrapper-%d", i)

        handler.flush()
        metrics = handler.get_metrics()
        assert metrics["emitted"] == 5, metrics
        assert metrics["in_flight"] == 0, metrics
        assert metrics["queue_dropped"] == 0, metrics
        handler.close()
    finally:
        server.shutdown()
