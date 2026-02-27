"""실제 caplog fixture 타입 확인 테스트"""

def test_caplog_is_logxide_type(caplog):
    """caplog이 logxide의 LogCaptureFixture인지 확인"""
    from logxide.testing import LogCaptureFixture
    
    print(f"\ncaplog type: {type(caplog)}")
    print(f"expected type: {LogCaptureFixture}")
    
    # 실제 타입 체크
    assert isinstance(caplog, LogCaptureFixture), f"caplog is {type(caplog)}, not LogCaptureFixture"
    
def test_caplog_not_pytest_type(caplog):
    """caplog이 pytest 기본 타입이 아닌지 확인"""
    from _pytest.logging import LogCaptureFixture as PytestLogCaptureFixture
    
    print(f"\ncaplog type: {type(caplog)}")
    print(f"pytest type: {PytestLogCaptureFixture}")
    
    # pytest 기본 caplog이 아님을 확인
    assert not isinstance(caplog, PytestLogCaptureFixture), "caplog should NOT be pytest's LogCaptureFixture"
