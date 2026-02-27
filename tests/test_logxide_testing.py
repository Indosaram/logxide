"""
Test logxide.testing pytest plugin

Tests that caplog fixture is automatically available
via pytest plugin registration in pyproject.toml.
"""
import pytest
from logxide import logging


# NOTE: caplog fixture is provided automatically by logxide.testing plugin
# registered in pyproject.toml [project.entry-points.pytest11]


class TestCaplogLogxideFixture:
    """caplog fixture 자동 제공 테스트"""

    def test_fixture_available(self, caplog):
        """fixture가 존재하고 기본 속성이 있는지 확인"""
        assert hasattr(caplog, 'records')
        assert hasattr(caplog, 'text')
        assert hasattr(caplog, 'record_tuples')
        assert hasattr(caplog, 'messages')
        assert hasattr(caplog, 'handler')
        assert hasattr(caplog, 'clear')
        assert hasattr(caplog, 'set_level')

    def test_captures_info(self, caplog):
        """INFO 레벨 로그 캡처"""
        logger = logging.getLogger("test.plugin.info")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(caplog.handler)

        logger.info("hello from plugin test")

        assert "hello from plugin test" in caplog.text
        assert len(caplog.records) >= 1

    def test_captures_multiple_levels(self, caplog):
        """여러 레벨 로그 캡처"""
        logger = logging.getLogger("test.plugin.multi")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(caplog.handler)

        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warning msg")
        logger.error("error msg")

        assert "debug msg" in caplog.text
        assert "info msg" in caplog.text
        assert "warning msg" in caplog.text
        assert "error msg" in caplog.text

    def test_record_tuples_format(self, caplog):
        """record_tuples가 (name, level, msg) 형식인지 확인"""
        logger = logging.getLogger("test.plugin.tuples")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(caplog.handler)

        logger.error("tuple test")

        found = False
        for name, level, msg in caplog.record_tuples:
            if msg == "tuple test":
                assert name == "test.plugin.tuples"
                assert level == logging.ERROR
                found = True
                break

        assert found, f"Record not found. Got: {caplog.record_tuples}"

    def test_clear(self, caplog):
        """clear() 동작 확인"""
        logger = logging.getLogger("test.plugin.clear")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(caplog.handler)

        logger.info("before clear")
        assert len(caplog.records) >= 1

        caplog.clear()

        assert len(caplog.records) == 0
        assert caplog.text == ""

    def test_isolation_1(self, caplog):
        """테스트 격리 (1/2) - test_2의 메시지가 없어야 함"""
        logger = logging.getLogger("test.plugin.isolation")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(caplog.handler)

        logger.info("isolation message 1")

        assert "isolation message 1" in caplog.text
        assert "isolation message 2" not in caplog.text

    def test_isolation_2(self, caplog):
        """테스트 격리 (2/2) - test_1의 메시지가 없어야 함"""
        logger = logging.getLogger("test.plugin.isolation")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(caplog.handler)

        logger.info("isolation message 2")

        assert "isolation message 2" in caplog.text
        assert "isolation message 1" not in caplog.text

    def test_messages_property(self, caplog):
        """messages 속성 확인"""
        logger = logging.getLogger("test.plugin.messages")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(caplog.handler)

        logger.info("msg1")
        logger.info("msg2")

        assert "msg1" in caplog.messages
        assert "msg2" in caplog.messages

    def test_set_level(self, caplog):
        """set_level() 동작 확인"""
        logger = logging.getLogger("test.plugin.setlevel")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(caplog.handler)

        # WARNING 이상만 캡처하도록 설정
        caplog.set_level(logging.WARNING)

        logger.debug("should not appear")
        logger.info("should not appear")
        logger.warning("should appear")

        assert "should not appear" not in caplog.text
        assert "should appear" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
