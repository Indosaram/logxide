"""
Python 3.15 compatibility tests for LogXide.

Tests for PEP 810 (Lazy Imports) and PEP 686 (UTF-8 Default Encoding)
compatibility. These tests run on all supported Python versions but
test forward-compatibility behaviors.
"""

import importlib
import time

from logxide import logging

# ============================================================
# PEP 810: Lazy Import Compatibility Tests
# ============================================================


class TestLazyImportCompat:
    """Tests ensuring logxide works correctly in lazy import scenarios."""

    def test_sys_modules_replacement_present(self):
        """Verify logxide replaces sys.modules['logging'] when not in pytest."""
        from logxide import module_system

        assert hasattr(module_system, "logging")
        assert isinstance(module_system.logging, module_system._LoggingModule)

    def test_logxide_module_is_proper_module_type(self):
        """Verify the logxide logging module is a proper types.ModuleType subclass."""
        import types

        from logxide import module_system

        assert isinstance(module_system.logging, types.ModuleType)
        assert module_system.logging.__name__ == "logging"

    def test_logging_module_has_required_attributes(self):
        """Verify the replacement logging module has all standard attributes."""
        required_attrs = [
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
            "NOTSET",
            "WARN",
            "FATAL",
            "getLogger",
            "basicConfig",
            "NullHandler",
            "Formatter",
            "Handler",
            "StreamHandler",
            "Logger",
            "LogRecord",
            "Filter",
            "LoggerAdapter",
            "root",
            "lastResort",
            "raiseExceptions",
        ]
        for attr in required_attrs:
            assert hasattr(logging, attr), f"Missing attribute: {attr}"

    def test_import_after_module_replacement(self):
        """Test that re-importing logging after module replacement works."""
        mod = importlib.import_module("logxide.module_system")
        assert hasattr(mod, "logging")
        assert hasattr(mod.logging, "getLogger")

    def test_getLogger_works_after_fresh_import(self):
        """Test getLogger works correctly (simulating post-lazy-import access)."""
        logger = logging.getLogger("test_lazy_compat")
        assert logger is not None
        logger.setLevel(logging.DEBUG)
        logger.info("Lazy import compatibility test message")

    def test_basicConfig_works_after_fresh_import(self):
        """Test basicConfig works correctly after import."""
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger("test_lazy_basicConfig")
        logger.info("basicConfig after lazy import test")

    def test_module_replacement_preserves_submodules(self):
        """Test that logging.config and logging.handlers are accessible."""
        from logxide import module_system

        mod = module_system.logging
        assert hasattr(mod, "config"), "logging.config should be accessible"
        assert hasattr(mod, "handlers"), "logging.handlers should be accessible"

    def test_install_is_idempotent(self):
        """Test that calling _install() multiple times is safe."""
        from logxide.module_system import _install

        _install()
        _install()
        logger = logging.getLogger("test_idempotent")
        logger.info("Idempotent install test")


# ============================================================
# PEP 686: UTF-8 Default Encoding Compatibility Tests
# ============================================================


class TestUTF8EncodingCompat:
    """Tests ensuring logxide file handlers work correctly with UTF-8 encoding."""

    def test_file_handler_writes_utf8(self, tmp_path):
        """Test that FileHandler correctly writes UTF-8 content."""
        from logxide import RustFileHandler

        log_file = str(tmp_path / "utf8_test.log")
        handler = RustFileHandler(log_file)

        logger = logging.getLogger("test_utf8_write")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        test_messages = [
            "Hello, World!",
            "Korean: \ud55c\uad6d\uc5b4",
            "Japanese: \u3053\u3093\u306b\u3061\u306f",
            "Accented: caf\u00e9 r\u00e9sum\u00e9",
        ]

        for msg in test_messages:
            logger.info(msg)

        handler.flush()
        logging.flush()
        time.sleep(0.1)

        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        for msg in test_messages:
            assert msg in content, f"Message not found in log: {msg}"

    def test_rotating_file_handler_writes_utf8(self, tmp_path):
        """Test that RotatingFileHandler correctly writes UTF-8 content."""
        from logxide import RustRotatingFileHandler

        log_file = str(tmp_path / "utf8_rotating_test.log")
        handler = RustRotatingFileHandler(log_file, 1024 * 1024, 3)

        logger = logging.getLogger("test_utf8_rotating")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        logger.info("UTF-8 rotating: \ud55c\uad6d\uc5b4 \ub85c\uadf8")
        handler.flush()
        logging.flush()
        time.sleep(0.1)

        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "UTF-8 rotating: \ud55c\uad6d\uc5b4 \ub85c\uadf8" in content

    def test_file_handler_with_explicit_encoding_param(self, tmp_path):
        """Test Python wrapper FileHandler accepts encoding parameter."""
        from logxide.handlers import FileHandler

        log_file = str(tmp_path / "encoding_param_test.log")
        handler = FileHandler(log_file, encoding="utf-8")

        logger = logging.getLogger("test_encoding_param")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        logger.info("Encoding parameter test: caf\u00e9 r\u00e9sum\u00e9")
        handler.flush()
        logging.flush()
        time.sleep(0.1)

        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "caf\u00e9 r\u00e9sum\u00e9" in content

    def test_default_encoding_behavior(self, tmp_path):
        """Test that default encoding works regardless of Python version.

        In Python 3.15+, the default encoding for open() is UTF-8 (PEP 686).
        In Python 3.12-3.14, it depends on locale.
        LogXide's Rust handlers always use UTF-8 internally,
        so this should work consistently across all versions.
        """
        from logxide import RustFileHandler

        log_file = str(tmp_path / "default_encoding.log")
        handler = RustFileHandler(log_file)

        logger = logging.getLogger("test_default_encoding")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        logger.info(
            "Unicode: \u00dc\u00f1\u00ef\u00e7\u00f6d\u00e9 \u65e5\u672c\u8a9e\u30c6\u30b9\u30c8"
        )
        handler.flush()
        logging.flush()
        time.sleep(0.1)

        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert (
            "Unicode: \u00dc\u00f1\u00ef\u00e7\u00f6d\u00e9 \u65e5\u672c\u8a9e\u30c6\u30b9\u30c8"
            in content
        )
