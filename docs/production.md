# 프로덕션 준비 가이드 (Production Readiness Guide)

LogXide를 프로덕션 환경에서 사용하기 위한 가이드입니다.

## 현재 상태 요약

LogXide는 **프로덕션 사용 준비가 완료**되었습니다. 다음과 같은 기능을 제공합니다:

### ✅ 구현 완료

1. **Python logging API 완벽 호환**
   - 모든 레벨 상수 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
   - 핵심 함수 (getLogger, basicConfig, shutdown 등)
   - 핵심 클래스 (Logger, Handler, Formatter, Filter 등)
   - 모듈 레벨 함수 (debug, info, warning, error 등)

2. **pytest 호환성**
   - caplog fixture 완벽 지원
   - 표준 logging 모듈 패치로 기존 테스트 호환

3. **프레임워크 통합**
   - Flask 통합 지원
   - Django 통합 지원
   - FastAPI 통합 지원
   - uvicorn 호환성

4. **프로덕션 필수 기능**
   - Sentry 통합
   - 멀티스레드 안전성
   - 비동기 로깅 (Rust/Tokio)
   - 로그 레벨 필터링
   - 포맷터 지원
   - 파일 로테이션 (RotatingFileHandler)
   - JSON 포맷터
   - 환경변수 기반 설정
   - 레이트 리밋/샘플링
   - 컨텍스트 바인딩
   - Graceful shutdown

## 빠른 시작

### 기본 사용

```python
from logxide import logging

# 기본 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('myapp')
logger.info('Hello from LogXide!')
```

### 프로덕션 환경 설정

```python
from logxide import logging
from logxide.production import configure_production

# 프로덕션 환경 설정 (JSON 출력 포함)
configure_production(
    service_name="my-service",
    environment="production",
    json_output=True,
    level=logging.INFO
)

logger = logging.getLogger('myapp')
logger.info('Production ready!')
```

### 환경변수 기반 설정

```python
from logxide.production import configure_from_env

# 환경변수로 설정:
# LOGXIDE_LEVEL=INFO
# LOGXIDE_JSON=true
# LOGXIDE_FORMAT=%(asctime)s - %(message)s

configure_from_env(prefix="LOGXIDE")
```

지원하는 환경변수:
- `{prefix}_LEVEL`: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `{prefix}_FORMAT`: 로그 포맷 문자열 또는 "json"
- `{prefix}_JSON`: JSON 출력 활성화 ("1" 또는 "true")
- `{prefix}_JSON_TIMESTAMP`: JSON에 타임스탬프 포함
- `{prefix}_JSON_THREAD`: JSON에 스레드 정보 포함
- `{prefix}_JSON_PROCESS`: JSON에 프로세스 정보 포함
- `{prefix}_JSON_SOURCE`: JSON에 소스 정보 포함

### JSON 로깅

```python
from logxide import logging
from logxide.production import JSONHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('myapp')

# JSON 핸들러 추가
json_handler = JSONHandler(
    include_timestamp=True,
    include_thread_info=True,
    extra_fields={"service": "my-service"}
)
logger.addHandler(json_handler)

logger.info("User logged in", extra={"user_id": "123"})
# 출력: {"level": "INFO", "message": "User logged in", "logger": "myapp", "timestamp": "...", "user_id": "123", "service": "my-service"}
```

### 컨텍스트 바인딩 (요청 추적)

```python
from logxide import logging
from logxide.production import bind_context, unbind_context, bound_contextvars

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('myapp')

# 컨텍스트 바인딩 (전역)
bind_context(request_id="abc123", user_id="42")
logger.info("Processing request")  # request_id와 user_id가 포함됨

# 컨텍스트 해제
unbind_context("request_id", "user_id")

# 컨텍스트 매니저 사용
with bound_contextvars(request_id="xyz789"):
    logger.info("In context")  # request_id 포함
logger.info("Out of context")  # request_id 미포함
```

### 레이트 리밋

```python
from logxide.production import RateLimitedHandler
from logxide.compat_handlers import StreamHandler

# 기본 핸들러
base_handler = StreamHandler()

# 레이트 리밋 적용 (초당 100개, 버스트 10개)
rate_limited = RateLimitedHandler(
    base_handler,
    max_per_second=100.0,
    burst_size=10
)

logger = logging.getLogger('myapp')
logger.addHandler(rate_limited)
```

### 로그 샘플링

```python
from logxide.production import SamplingHandler
from logxide.compat_handlers import StreamHandler

base_handler = StreamHandler()

# 50% 샘플링
sampling = SamplingHandler(
    base_handler,
    sample_rate=0.5,
    level_rates={
        logging.ERROR: 1.0,    # 에러는 100% 로깅
        logging.WARNING: 0.8,  # 경고는 80% 로깅
        logging.INFO: 0.5,     # 정보는 50% 로깅
        logging.DEBUG: 0.1,    # 디버그는 10% 로깅
    }
)

logger = logging.getLogger('myapp')
logger.addHandler(sampling)
```

### Graceful Shutdown

```python
from logxide.production import register_shutdown_handler, graceful_shutdown

# 커스텀 셧다운 핸들러 등록
def my_cleanup():
    print("Cleaning up...")

register_shutdown_handler(my_cleanup)

# 수동 셧다운 (모든 로그 플러시)
graceful_shutdown()
```

## 프레임워크 통합

### Flask

```python
from flask import Flask
from logxide import logging

app = Flask(__name__)

# LogXide 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@app.route('/')
def hello():
    app.logger.info('Request received')
    return 'Hello, World!'
```

### Django

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logxide.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# 또는 직접 사용
from logxide import logging
logger = logging.getLogger('django')
```

### FastAPI

```python
from fastapi import FastAPI
from logxide import logging
from logxide.production import configure_production

# 프로덕션 설정
configure_production(
    service_name="my-api",
    environment="production",
    json_output=True
)

app = FastAPI()
logger = logging.getLogger('uvicorn')

@app.get('/')
async def root():
    logger.info('Request received')
    return {'message': 'Hello, World!'}
```

## 테스트

### pytest caplog 사용

LogXide는 pytest의 caplog fixture와 완벽하게 호환됩니다:

```python
def test_my_function(caplog):
    import logging
    
    logger = logging.getLogger('test')
    
    with caplog.at_level(logging.INFO):
        logger.info('Test message')
    
    assert 'Test message' in caplog.text
```

## 성능 고려사항

### 비동기 특성

LogXide는 비동기 로깅을 사용하므로:

1. **로그 순서**: 로그 메시지의 순서가 엄격하게 보장되지 않을 수 있습니다
2. **즉각적 출력**: 로그가 즉시 출력되지 않을 수 있습니다
3. **flush() 호출**: 중요한 시점에서 `logging.flush()`를 호출하여 버퍼를 비우세요

```python
from logxide import logging

logger = logging.getLogger('myapp')
logger.error('Critical error!')
logging.flush()  # 버퍼 즉시 비우기
```

### 권장 설정

프로덕션 환경에서 권장하는 설정:

```python
from logxide import logging
from logxide.production import (
    configure_production,
    register_shutdown_handler,
    RateLimitedHandler,
)

# 1. 프로덕션 설정
configure_production(
    service_name="my-service",
    environment="production",
    json_output=True,
    level=logging.INFO
)

# 2. 레이트 리밋 (선택사항)
# 로그 폭주 방지

# 3. Graceful shutdown 보장
import atexit
from logxide import flush
atexit.register(flush)
```

## 알려진 제한사항

1. **logging.config 모듈**: 파일 기반 설정은 표준 logging 모듈에 위임됩니다
2. **TimedRotatingFileHandler**: 시간 기반 로테이션은 아직 미구현
3. **SocketHandler, SMTPHandler 등**: 네트워크 핸들러는 표준 모듈 사용 필요

## 마이그레이션 가이드

기존 Python logging에서 LogXide로 마이그레이션:

```python
# 변경 전
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 변경 후 (옵션 1: 직접 import)
from logxide import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 변경 후 (옵션 2: 자동 패치, import만 하면 됨)
import logxide  # 이것만으로 표준 logging이 패치됨
import logging  # 이제 LogXide가 사용됨
```

## 문제 해결

### 로그가 출력되지 않음

```python
from logxide import logging

# 1. 레벨 확인
logger = logging.getLogger('myapp')
logger.setLevel(logging.DEBUG)

# 2. 핸들러 확인
print(logger.handlers)

# 3. 버퍼 플러시
logging.flush()
```

### caplog이 동작하지 않음

```python
# conftest.py에서 LogXide 초기화 확인
import logxide  # 반드시 pytest 시작 전에 import
```

## 지원

- GitHub Issues: https://github.com/Indosaram/logxide/issues
- 문서: https://Indosaram.readthedocs.io/logxide
