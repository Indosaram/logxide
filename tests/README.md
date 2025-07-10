# LogXide Test Suite

이 디렉토리는 LogXide의 포괄적인 테스트 스위트를 포함합니다.

## 테스트 구조

### `test_basic_logging.py`
- **TestBasicLoggingSimple**: 기본 로깅 기능 테스트
  - 로거 생성, 계층 구조, 레벨 설정
  - 기본 설정, flush 기능
  - 여러 로거 동시 사용
  - 스레드 이름 기능

- **TestBasicFormats**: 기본 포맷팅 테스트
  - 모든 포맷 지정자 테스트
  - 패딩 포맷 테스트
  - 복잡한 포맷 조합 테스트

- **TestThreadingSimple**: 스레딩 기능 테스트
  - 멀티스레드 로깅
  - 스레드 격리 테스트

### `test_integration.py`
- **TestDropInReplacement**: Python logging 호환성 테스트
- **TestRealWorldScenarios**: 실제 응용프로그램 시뮬레이션
- **TestFormatReconfiguration**: 런타임 포맷 변경 테스트
- **TestThreadSafety**: 스레드 안전성 및 동시성 테스트
- **TestEdgeCases**: 경계 조건 및 엣지 케이스 테스트

## 테스트 실행 방법

### 전체 테스트 실행
```bash
pytest tests/
```

### 상세한 출력으로 테스트 실행
```bash
pytest tests/ -v
```

### 특정 카테고리 테스트만 실행
```bash
# 유닛 테스트만
pytest tests/ -m unit

# 통합 테스트만
pytest tests/ -m integration

# 포맷팅 테스트만
pytest tests/ -m formatting

# 스레딩 테스트만
pytest tests/ -m threading

# 느린 테스트 제외
pytest tests/ -m "not slow"
```

### 테스트 커버리지 확인
```bash
pytest tests/ --cov=logxide --cov-report=term-missing
```

### HTML 커버리지 리포트 생성
```bash
pytest tests/ --cov=logxide --cov-report=html
```

### 병렬 테스트 실행 (속도 향상)
```bash
pytest tests/ -n auto
```

## 테스트 마커

테스트는 다음 마커로 분류됩니다:

- `@pytest.mark.unit`: 단위 테스트
- `@pytest.mark.integration`: 통합 테스트
- `@pytest.mark.formatting`: 포맷팅 관련 테스트
- `@pytest.mark.threading`: 스레딩 관련 테스트
- `@pytest.mark.slow`: 느린 테스트 (고성능 테스트, 스트레스 테스트)

## 테스트 설계 원칙

### 기능 중심 테스트
복잡한 출력 캡처 대신 로깅 시스템의 핵심 기능에 집중:
- 로거 생성 및 설정이 올바르게 작동하는가
- 다양한 포맷이 오류 없이 적용되는가
- 멀티스레딩 환경에서 안전하게 작동하는가
- 실제 사용 시나리오에서 문제없이 동작하는가

### 실용적 접근
- 실제 출력 문자열을 검증하는 대신 기능적 정확성에 집중
- 예외 발생 여부와 설정 상태 검증
- 실제 사용 패턴과 유사한 테스트 시나리오

### 포괄적 커버리지
- 모든 주요 API 엔드포인트 테스트
- 다양한 포맷 조합 테스트
- 멀티스레딩 및 동시성 시나리오
- 엣지 케이스 및 오류 조건

## 기여하기

새로운 테스트를 추가할 때:

1. 적절한 마커 사용
2. 명확한 테스트 이름과 docstring
3. `clean_logging_state` fixture 사용으로 테스트 격리 보장
4. 가능한 한 간단하고 집중된 테스트 작성
5. 복잡한 출력 캡처보다는 기능 검증에 집중

## 성능 고려사항

- 스트레스 테스트는 `@pytest.mark.slow`로 마킹
- 기본 테스트 실행에서는 빠른 피드백을 위해 가벼운 테스트 우선
- 병렬 실행을 고려한 테스트 설계 (상태 공유 최소화)
