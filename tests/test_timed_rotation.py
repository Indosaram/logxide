"""
Tests for TimedRotatingFileHandler with time-based rotation, retention, and compression.
"""

import glob
import gzip
import os
import time

from logxide import logging
from logxide.handlers import TimedRotatingFileHandler


class TestTimedRotatingFileHandler:
    """Tests for timed file rotation."""

    def test_basic_creation_and_logging(self, tmp_path):
        """Handler can be created and logs messages to a file."""
        log_file = str(tmp_path / "test.log")
        handler = TimedRotatingFileHandler(log_file, when="S", interval=1)
        logger = logging.getLogger("test.timed.basic")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.info("hello timed handler")
        handler.flush()
        assert os.path.exists(log_file)

    def test_rotation_on_second(self, tmp_path):
        """Handler rotates when crossing a second boundary."""
        log_file = str(tmp_path / "test.log")
        handler = TimedRotatingFileHandler(
            log_file, when="S", interval=1, backupCount=5
        )
        logger = logging.getLogger("test.timed.rotation")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Write first batch
        logger.info("batch 1")
        handler.flush()

        # Wait past the 1-second rotation interval
        time.sleep(1.5)

        # Write second batch — this should trigger rotation
        logger.info("batch 2")
        handler.flush()

        # The main file should exist
        assert os.path.exists(log_file)

        # At least one backup file should exist
        backup_files = glob.glob(f"{log_file}.*")
        assert len(backup_files) >= 1, (
            f"Expected backup files but found: {backup_files}"
        )

    def test_retention_limits_backup_count(self, tmp_path):
        """Handler enforces backup_count retention policy."""
        log_file = str(tmp_path / "test.log")
        handler = TimedRotatingFileHandler(
            log_file, when="S", interval=1, backupCount=2
        )
        logger = logging.getLogger("test.timed.retention")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Create multiple rotations
        for i in range(4):
            logger.info(f"message {i}")
            handler.flush()
            time.sleep(1.2)

        # Final write to trigger last rotation
        logger.info("final")
        handler.flush()

        # Count backup files (excluding the active log)
        backup_files = [f for f in glob.glob(f"{log_file}.*") if not f.endswith("~")]
        # Backup count should be at most 2
        assert len(backup_files) <= 2, (
            f"Expected at most 2 backups but found {len(backup_files)}: {backup_files}"
        )

    def test_compression_creates_gz_files(self, tmp_path):
        """Handler compresses rotated files when compress=True."""
        log_file = str(tmp_path / "test.log")
        handler = TimedRotatingFileHandler(
            log_file, when="S", interval=1, backupCount=5, compress=True
        )
        logger = logging.getLogger("test.timed.compress")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        logger.info("before rotation")
        handler.flush()

        time.sleep(1.5)

        logger.info("after rotation")
        handler.flush()

        # Wait a bit for the background compression thread
        time.sleep(0.5)

        # Check for .gz files
        gz_files = glob.glob(f"{log_file}.*.gz")
        assert len(gz_files) >= 1, f"Expected .gz files but found: {gz_files}"

        # Verify the .gz file is valid gzip
        with gzip.open(gz_files[0], "rt") as f:
            content = f.read()
            assert "before rotation" in content

    def test_when_midnight(self, tmp_path):
        """Handler can be created with when='midnight' without error."""
        log_file = str(tmp_path / "test.log")
        handler = TimedRotatingFileHandler(log_file, when="midnight")
        logger = logging.getLogger("test.timed.midnight")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.info("midnight test")
        handler.flush()
        assert os.path.exists(log_file)

    def test_when_hour(self, tmp_path):
        """Handler can be created with when='H' without error."""
        log_file = str(tmp_path / "test.log")
        handler = TimedRotatingFileHandler(log_file, when="H", interval=1)
        logger = logging.getLogger("test.timed.hour")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.info("hourly test")
        handler.flush()
        assert os.path.exists(log_file)

    def test_set_formatter(self, tmp_path):
        """Formatter can be set on TimedRotatingFileHandler."""
        log_file = str(tmp_path / "test.log")
        handler = TimedRotatingFileHandler(log_file, when="S")
        import logging as stdlib_logging

        formatter = stdlib_logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        # Should not raise
