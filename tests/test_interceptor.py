import logging as _std_logging

from logxide import intercept_stdlib
from logxide import logging as lx_logging
from logxide.logger_wrapper import getLogger as get_logxide_logger


def test_intercept_stdlib_helper_function(caplog):
    # 1. Setup Rust Capture
    # We must explicitly add the caplog handler directly to the Rust PyLogger
    # because LogXide routes intercepted logs fully out of the Python domain.
    lx_logger = get_logxide_logger()
    lx_logger.setLevel(lx_logging.DEBUG)
    lx_logger.addHandler(caplog.handler)

    # Enable standard Python root to propagate all levels
    _std_logging.getLogger().setLevel(_std_logging.DEBUG)

    # 2. Simulate Third-Party Early Import
    # We use standard getLogger here. In real environments where early-binding
    # occurs, the logger will just be a standard python logger.
    pure_python_logger = _std_logging.getLogger("early_bird_library")
    pure_python_logger.setLevel(_std_logging.DEBUG)

    # 3. Apply Interceptor Hook
    # The interceptor attaches to the standard python root logger to catch
    # these rogue unpatched logs propagating upwards.
    intercept_stdlib()

    # 4. Fire Logs
    # This pure python log will bubble up to the python root logger,
    # hit the InterceptHandler, get forwarded to Rust, and arrive in our caplog.
    pure_python_logger.error("Rogue component failure!")

    # Assertions
    records = caplog.records
    assert len(records) >= 1

    comp_record = next(r for r in records if "Rogue component failure" in r.msg)
    assert comp_record.name == "early_bird_library"
    assert comp_record.levelno == lx_logging.ERROR
