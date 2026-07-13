"""
Regression tests locking design §6 criterion 1 (handler registry routing).

These exercise the Rust PyLogger dispatch directly (via ``logxide.logxide.logging.getLogger``)
so that the routing-by-backend-kind model is verified at the layer it lives in:

* A public wrapper attached to logger A must deliver an owner emit exactly once and
  must not receive records from an unrelated logger B (no double-emit, no cross-delivery).
* Handlers accumulated on unrelated loggers must never receive an unrelated no-handler
  logger's records.
* After removeHandler()/clear_handlers(), a subsequent emit must reach zero handlers.
"""

import time

import logxide
from logxide import handlers
from logxide import logxide as _ext


def _rust_logger(name):
    logger = _ext.logging.getLogger(name)
    logger.setLevel(10)  # DEBUG
    return logger


def _settle():
    logxide.flush()
    time.sleep(0.1)


def test_file_wrapper_owner_gets_one_unrelated_gets_zero(tmp_path):
    logxide.clear_handlers()
    log_file = tmp_path / "owner.log"

    handler = handlers.FileHandler(str(log_file))
    owner = _rust_logger("routing.file.owner")
    unrelated = _rust_logger("routing.file.unrelated")

    owner.addHandler(handler)

    unrelated.info("from-unrelated")
    owner.info("from-owner")

    handler.flush()
    _settle()

    lines = log_file.read_text().splitlines()
    assert lines == ["from-owner"], (
        f"owner must receive exactly its own emit, got {lines}"
    )


def test_memory_wrapper_owner_gets_one_unrelated_gets_zero():
    logxide.clear_handlers()

    handler = handlers.MemoryHandler()
    owner = _rust_logger("routing.mem.owner")
    unrelated = _rust_logger("routing.mem.unrelated")

    owner.addHandler(handler)

    unrelated.info("from-unrelated")
    owner.info("from-owner")
    _settle()

    messages = [r.getMessage() for r in handler.records]
    assert messages == ["from-owner"], (
        f"owner must receive exactly one record and no cross-delivery, got {messages}"
    )


def test_accumulated_handlers_do_not_receive_unrelated_logger_records():
    logxide.clear_handlers()

    accumulated = []
    for i in range(50):
        mh = handlers.MemoryHandler()
        other = _rust_logger(f"routing.accum.other.{i}")
        other.addHandler(mh)
        accumulated.append(mh)

    no_handler_logger = _rust_logger("routing.accum.bystander")
    no_handler_logger.info("nobody-should-see-this")
    _settle()

    total = sum(len(mh.records) for mh in accumulated)
    assert total == 0, (
        f"unrelated no-handler logger must deliver 0 records to accumulated handlers, got {total}"
    )


def test_remove_handler_teardown_reaches_zero():
    logxide.clear_handlers()

    handler = handlers.MemoryHandler()
    logger = _rust_logger("routing.teardown.remove")
    logger.addHandler(handler)

    logger.info("before-remove")
    _settle()
    assert len(handler.records) == 1

    logger.removeHandler(handler)
    handler.clear()

    logger.info("after-remove")
    _settle()
    assert len(handler.records) == 0, "removeHandler must stop delivery to the handler"


def test_clear_handlers_teardown_reaches_zero(tmp_path):
    logxide.clear_handlers()
    log_file = tmp_path / "clear.log"

    # Root-attached handlers live in the global lists that clear_handlers() tears down.
    root = _rust_logger("root")
    handler = handlers.FileHandler(str(log_file))
    root.addHandler(handler)

    root.info("before-clear")
    handler.flush()
    _settle()
    assert log_file.read_text().splitlines() == ["before-clear"]

    logxide.clear_handlers()

    root.info("after-clear")
    handler.flush()
    _settle()

    # No new line should be appended once the global registry is torn down.
    assert log_file.read_text().splitlines() == ["before-clear"], (
        "clear_handlers must stop global delivery"
    )
