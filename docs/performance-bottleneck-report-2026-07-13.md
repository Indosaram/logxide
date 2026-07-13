# logxide 성능 병목 분석 보고서

- 작성일: 2026-07-13
- 분석 대상: Git HEAD `89afeaa`, manifest 버전 `0.1.22`
- 범위: Python 공개 로깅 경로, Rust 핸들러/포매터, 비동기 전송, 기존 벤치마크 하네스
- 원칙: 프로덕션 코드와 테스트 코드는 수정하지 않음

## 1. 요약

현재 가장 큰 병목은 Rust 연산 자체가 아니라 **핸들러 분류 오류로 인한 Python 재진입**, **bounded queue 포화 시 대기와 유실**, **로그 레코드의 매 호출 고정 비용**이다.

| 우선순위 | 병목 | 관측 영향 | 판정 |
|---|---|---:|---|
| P0 | Rust 핸들러 수명 유지 목록을 Python 핸들러 dispatch 목록으로도 사용 | 공개 handler가 owner 로그를 2번 출력하고 unrelated logger 로그도 수집. 핸들러 100개 누적 시 비용 107.58배 | 확정 |
| P0 | Stream/HTTP/OTLP bounded queue 포화 및 불완전한 flush/shutdown | 느린 Stream sink에서 54.10% 유실. HTTP 50건 중 3건 도달. 직접 `flush()`는 5.007초 timeout 뒤 반환 후 전달 | 확정 |
| P1 | Python handler가 caller 정보를 process-global로 활성화; Sentry auto-detect가 이를 import 시 유발 | no-handler 경로 159.92ns → 337.63ns, 약 2.11배 | 확정 |
| P1 | enabled 로그의 레코드 생성·PyO3 변환·락 고정비 | 필터된 로그 31.50ns 대비 enabled/no-handler 168.26ns, 5.34배 | 확정 |
| P1 | `%` 인자·extra·시간 포맷의 변환/할당 | `%` 인자 2.12배, extra 2.59배, `asctime` 전체 포맷 2.60배 | 확정 |
| P2 | GIL을 유지한 producer hot path | 1/2/4/8스레드 처리량이 6.27/6.17/6.17/6.10M ops/s로 확장되지 않음 | CPython GIL 빌드에서 확정 |

가장 먼저 고칠 곳은 `src/globals.rs`와 `src/py_logger.rs`의 핸들러 레지스트리 경계다. 직접 Rust wrapper에는 Python 객체 생성과 실패한 메서드 호출 비용이 붙고, 공개 wrapper에는 실제 두 번째 emit과 다른 logger의 오배송까지 발생한다. 어느 쪽도 `clear_handlers()`로 해소되지 않는다.

## 2. 측정 환경과 방법

### 환경

- macOS 26.5 arm64
- Apple M4 Max, 논리 CPU 16개, 메모리 48GiB
- CPython 3.14.2, GIL 활성화
- Rust/Cargo 1.88.0
- 현재 HEAD를 `/tmp`에 `release` + debuginfo로 별도 빌드
- 빌드 wheel: `logxide-0.1.22-cp314-cp314-macosx_11_0_arm64.whl`
- Python 최소 의존성 격리 환경에서 기본 측정, Sentry 영향은 동일 wheel에 `sentry-sdk`를 추가해 별도 측정

저장소의 기존 `.so`가 아니라 현재 소스를 다시 빌드한 wheel을 기준으로 결과를 확정했다. `pyproject.toml`과 `Cargo.toml`은 `0.1.22`지만 런타임 `logxide.__version__`은 `0.1.19`이므로, 결과의 식별자는 패키지 문자열보다 HEAD `89afeaa`가 정확하다.

### 방법

- 단일 호출: `timeit.repeat`, 5~7회 중앙값, GC 비활성화
- 파일 핸들러: `/dev/null`을 사용해 producer-side CPU 비용 측정
- 스레드: 총 1,000,000호출을 1/2/4/8개 스레드에 균등 배분
- Stream 포화: 실제 파이프로 전달된 행 수를 발행 수와 비교
- HTTP 포화: 100ms 지연 로컬 HTTP 서버, `capacity=1`, `batch_size=1`
- 프로파일: debuginfo가 포함된 격리 wheel을 macOS `sample`로 1ms 간격 샘플링

절대 처리량은 이 장비와 빌드에 한정된다. 병목 판정은 같은 빌드에서 원인만 바꾼 대조 실험과 소스 호출 경로를 함께 사용했다.

## 3. 핵심 측정 결과

### 3.1 기본 hot path

| 시나리오 | 중앙값 | 처리량 | 상대 비용 |
|---|---:|---:|---:|
| 필터된 `debug()` | 31.50ns | 31.74M ops/s | 1.00배 |
| enabled `info()`, 핸들러 없음 | 168.26ns | 5.94M ops/s | 5.34배 |
| 전역 FileHandler, raw, `/dev/null` | 224.68ns | 4.45M ops/s | 7.13배 |
| 로컬 `addHandler(RustFileHandler)` | 1,383.68ns | 0.72M ops/s | 43.92배 |

### 3.2 핸들러 누적

대상 logger에는 핸들러를 달지 않고, 다른 logger에 Rust `MemoryHandler`를 누적한 뒤 대상 logger의 `info()`를 측정했다.

| 누적 핸들러 | 로그 1건 비용 | 처리량 | 0개 대비 |
|---:|---:|---:|---:|
| 0 | 165.32ns | 6.05M ops/s | 1.00배 |
| 1 | 1,297.19ns | 0.77M ops/s | 7.85배 |
| 10 | 2,862.41ns | 0.35M ops/s | 17.31배 |
| 50 | 9,590.72ns | 0.10M ops/s | 58.01배 |
| 100 | 17,784.93ns | 0.056M ops/s | 107.58배 |

50개를 누적한 뒤 `clear_handlers()`와 GC를 실행해도 9,532.24ns에서 9,600.51ns로 비용이 유지됐다. 전역 핸들러 삭제 API가 수명 유지/실행 목록을 비우지 않는다는 런타임 증거다.

동일한 격리 wheel에서 공개 wrapper와 직접 Rust wrapper의 전달 건수도 확인했다.

| 정확성 probe | 관측 결과 |
|---|---|
| 공개 `logxide.FileHandler`, owner logger가 1건 발행 | 동일 행 2건 기록 |
| 직접 `logxide.RustFileHandler`, owner logger가 1건 발행 | 1건 기록 |
| 공개 `logxide.MemoryHandler`를 logger A에만 연결 후 B 1건, A 1건 발행 | `B` 1건과 `A` 2건, 총 3건 수집 |

즉 이 경로는 CPU 병목에 그치지 않고 공개 handler에서 중복 출력과 logger 간 오배송을 일으킨다.

### 3.3 포맷과 payload

| 시나리오 | 중앙값 | raw/literal 대비 |
|---|---:|---:|
| raw message | 192.15ns | 1.00배 |
| `%(message)s` | 227.07ns | 1.18배 |
| `%(levelname)s %(message)s` | 239.49ns | 1.25배 |
| `%(asctime)s - %(name)s - %(levelname)s - %(message)s` | 499.47ns | 2.60배 |
| literal payload | 219.50ns | 1.00배 |
| `logger.info("%s", value)` | 465.46ns | 2.12배 |
| `extra` 2개 필드 | 569.27ns | 2.59배 |

### 3.4 스레드 확장성

| 스레드 | 총 처리량 |
|---:|---:|
| 1 | 6.27M ops/s |
| 2 | 6.17M ops/s |
| 4 | 6.17M ops/s |
| 8 | 6.10M ops/s |

8스레드는 1스레드보다 오히려 약 2.7% 낮았다. thread-safe이지만 이 CPython 빌드에서는 producer 경로가 병렬로 확장되지 않는다.

### 3.5 비동기 queue 포화

| 경로 | 발행 | 도달 | 유실 | producer 관측 |
|---|---:|---:|---:|---:|
| Stream, 빠른 파이프 1차 | 100,000 | 100,000 | 0% | 49.83ms 발행, flush 0.39ms |
| Stream, 빠른 파이프 2차 | 100,000 | 100,000 | 0% | 51.86ms 발행, flush 51.44ms |
| Stream, 100µs/행 sink | 50,000 | 22,949 | 54.10% | 24.96ms 발행, flush 1.25s |
| HTTP, 100ms sink, 실행 1 | 50 | 3 | 94.00% | 총 276ms, 중앙값 6.05ms |
| HTTP, 100ms sink, 실행 2 | 50 | 3 | 94.00% | 총 282ms, 중앙값 6.28ms |

Stream의 높은 producer 처리량 일부는 실제 출력이 아니라 queue 거부 후 즉시 반환한 호출이다. 처리량 수치만 보면 이 동작을 성능 향상으로 오인할 수 있다.
빠른 sink에서는 이번 두 실행 모두 유실이 없었고 느린 sink에서만 queue 포화를 재현했다. 표의 비율은 scheduler와 pipe 소비 속도에 민감한 관측 예시다. `try_send()` 실패를 무시하는 유실 메커니즘과 포화 시 발행/도달 불일치는 확정이지만 특정 비율을 보편값으로 해석하면 안 된다.

별도 direct-handler probe에서 raw HTTPHandler에 5,000건을 넣고 `handler.flush()`를 호출하자 5.007초 timeout 뒤 반환했고, 반환 시점에는 0건이었다. 5,000건 payload는 반환 16.406ms 뒤 도착했다.

## 4. 병목 상세

### P0-1. Rust 핸들러마다 Python `handle()` dispatch를 잘못 시도한다

메커니즘:

1. `src/globals.rs:318-328`은 정상적으로 Rust handler의 `Arc<dyn Handler>`를 로컬 목록에 넣은 뒤, Python wrapper 객체도 `PYTHON_HANDLERS_KEEP_ALIVE`에 추가한다.
2. `src/py_logger.rs:540-600`은 이 전역 수명 유지 목록 전체를 `global_py_handlers`로 복제한다.
3. 목록이 비어 있지 않으면 표준 Python `LogRecord`를 새로 만들고 logger 소유 관계와 무관하게 모든 객체에 `handle()`을 호출한다.
4. 직접 PyO3 Rust wrapper는 예를 들어 `src/py_handlers.rs:164-167`처럼 `emit()`만 노출하므로 `handle()` 호출이 실패하고 무시된다. 반면 권장 공개 wrapper는 `logxide/handlers.py:95-121`, `logxide/handlers.py:352-382`처럼 stdlib `Handler`를 상속해 실제 `handle()`→`emit()`이 실행된다. 이 객체는 `_inner` 때문에 Rust handler로도 이미 등록되어 owner 로그를 두 번 출력하고, 전역 dispatch 때문에 다른 logger의 로그까지 받는다.
5. `src/globals.rs:153-156`의 `clear_handlers()`는 Rust `HANDLERS`만 비우고 이 목록은 비우지 않는다.

따라서 Rust 핸들러 1개가 추가될 때마다 관련 없는 모든 enabled 로그에 Python `LogRecord` 생성과 메서드 조회 비용이 붙는다. 직접 wrapper에서는 실패한 호출과 예외 정리, 공개 wrapper에서는 실제 두 번째 포맷/emit과 오배송 비용이 더해진다. 샘플 프로파일에서도 `PyLogger::makeRecord`, `_PyObject_Malloc/_Free`, `_PyObject_GetMethod`, `PyObject_GetOptionalAttr`, import/attribute-error 경로가 관측됐다.

권고:

- 수명 유지와 Python dispatch를 서로 다른 저장소로 분리한다.
- 정확한 built-in Rust wrapper는 이미 `Arc`가 로컬/전역 Rust handler 목록에 보관되므로 Python dispatch 목록에 넣지 않는다.
- 순수 Python handler와 Python에서 `handle()`을 override한 subclass/adapter는 실제 Python dispatch 목록에 남겨 호환성을 보존한다.
- `clear_handlers()`와 handler 제거가 각 레지스트리, wrapper `Arc`, worker/channel 수명을 함께 정리하도록 한다. 현재 keep-alive 목록은 공개 wrapper를 계속 보유하고 HTTP/OTLP PyO3 wrapper의 Drop도 worker shutdown을 보장하지 않으므로 CPU 비용뿐 아니라 background resource도 남을 수 있다.
- 회귀 기준: 핸들러 0/1/100개에서 무관한 no-handler logger의 비용이 일정하고, owner의 1 emit은 정확히 1건만 전달되며 unrelated logger는 0건이어야 한다. remove/clear/close 뒤에는 routing과 worker 수명이 모두 종료돼야 한다.

### P0-2. queue 포화와 불완전한 flush가 지연·유실을 함께 만든다

Stream 경로는 `src/handler.rs:53-55`에서 용량 8,192의 queue를 만들고, `src/handler.rs:140-148`에서 `try_send()` 결과를 무시한다. queue가 차면 로그가 조용히 사라진다.

HTTP/OTLP 경로는 `src/handler.rs:700-709`, `src/handler.rs:974-983`에서 최대 5ms 기다리는 `send_timeout()` 결과를 무시한다. 따라서 포화 시 producer tail latency가 증가한 뒤 로그도 사라진다. 또한 HTTP 기본 직렬화는 `src/handler.rs:584-656`의 `Python::attach()` 안에서 실행된다. callback이 없어도 HTTP background worker가 GIL을 필요로 하므로 producer와 consumer가 서로 진행을 방해할 수 있다. 반면 OTLP 기본 protobuf 직렬화는 순수 Rust이며, Python error callback을 실행할 때만 GIL이 필요하다.

HTTP worker의 `src/handler.rs:487-541`과 OTLP worker의 `src/handler.rs:784-834`는 flush 신호를 확인한 뒤 queue 전체가 아니라 다음 레코드 하나만 받아 batch를 전송하고 완료 신호를 보낼 수 있다. `src/handler.rs:674-682`, `src/handler.rs:959-968`의 `flush()`/`shutdown()`도 이 신호와 flag만 사용한다. 따라서 `flush()` 완료가 queue drain 또는 sink acknowledgement를 보장하지 않으며, buffer가 빈 순간의 shutdown은 queue에 남은 레코드를 버릴 수 있다.

직접 HTTP handler의 `src/py_handlers.rs:360-362` `flush()`는 GIL을 유지한 채 최대 5초를 기다리지만 HTTP worker는 기본 직렬화에도 GIL이 필요하다. 이 때문에 위 probe처럼 worker가 진행하지 못한 채 timeout하고 반환 뒤에야 전송한다. 반면 module-level `logging.flush()`는 `src/globals.rs:102-109`에서 `py.detach()`를 사용한다. 이는 handler `flush()`도 완료를 기다린다고 명시한 `docs/usage.md:230-242`, `docs/reference.md:145-150` 계약과 다르다.

내부 `OverflowStrategy`는 `src/handler.rs:446-453`에서 인자를 받지만 사용하지 않는다. Python HTTP/OTLP 생성자에는 이 인자가 노출되지 않았고 기존 공개 계약도 없으므로 지원되던 정책의 회귀는 아니다. 현재 실제 정책은 문서화되지 않은 고정 5ms timeout/drop이며, enum을 공개하기 전에 의미와 관측성 계약부터 설계해야 한다.

권고:

- overflow 정책을 실제 구현하고 drop count를 공개한다.
- 성공 처리량은 발행 건수가 아니라 sink가 확인한 건수로 계산한다.
- callback/context provider가 없는 기본 HTTP 직렬화는 GIL 밖의 순수 Rust 경로로 분리한다. OTLP는 callback 호출 구간만 GIL 경계를 유지한다.
- blocking 정책이면 producer가 GIL을 쥔 채 queue를 기다리지 않도록 한다.
- `flush()`는 먼저 queue를 완전히 drain한 뒤 sink acknowledgement와 drop/전송 실패를 포함한 명시적 결과를 반환하도록 계약을 정한다. 기존 반환·예외 의미가 바뀌므로 호환 버전 정책과 함께 도입한다.
- 회귀 기준은 direct handler와 module-level flush 모두에 대해 “반환 전에 모든 accepted record가 sink에서 확인됨”을 검증하고, close/shutdown도 queue drain 뒤 worker 종료를 보장해야 한다.

### P1-1. Python handler가 모든 로그의 caller 수집을 전역 활성화한다

`src/globals.rs:330-343`은 Sentry에 한정되지 않은 모든 Python handler 등록에서 process-global `CALLER_INFO_REQUIRED`를 영구적으로 켠다. 이번 최소/선택 의존성 대조에서는 `logxide/module_system.py:339-340`이 설치 시 `_auto_configure_sentry()`를 호출하고, `logxide/sentry_integration.py:291-298`이 설정 여부와 무관하게 설치된 SDK를 import한 것이 방아쇠였다. Sentry/urllib3가 추가한 stdlib handler가 patched `addHandler()`를 통해 등록됐다.

그 뒤 모든 enabled 로그는 formatter가 pathname/line/function을 사용하지 않아도 `src/py_logger.rs:370-412`의 Python frame helper를 호출한다. 동일 HEAD wheel과 `sentry-sdk==2.48.0`에서 import 허용 시 337.63ns, import 차단 시 159.92ns였고 caller 필드는 각각 채워짐/비어 있음으로 원인 토글도 확인했다.

권고:

- advertised Sentry auto-detect를 유지하면서 설정되지 않은 SDK import가 만든 부수 handler를 전역 caller 요구로 고착시키지 않는 경로를 우선한다. 명시적 opt-in으로 바꾸는 선택지는 import-time 자동 설정 계약을 바꾸므로 major-version 또는 deprecation 정책으로 다룬다.
- caller 필요 여부를 process-global 단방향 boolean이 아니라 실제 handler/formatter snapshot에서 계산한다.
- handler 제거 시 필요 여부가 다시 false가 될 수 있어야 한다.

### P1-2. enabled 로그는 출력이 없어도 완전한 레코드를 만든다

`src/py_logger.rs:760-783`의 `info()`는 handler 존재 여부와 무관하게 메시지 문자열 변환, args 직렬화, `LogRecord` 생성, caller 정보, 예외 필드를 처리한다. `src/core.rs:402-443`은 매 호출마다 시간, logger name, level name, thread name과 여러 빈 `String`을 채운다. 그 뒤 `src/py_logger.rs:439-549`에서 filter와 handler 목록을 위해 여러 mutex/snapshot 경로를 지난다.

심볼이 있는 native sample은 `create_log_record_with_extra`, `PyLogger::populate_caller_info`, `PyLogger::emit_record`, allocator/free, `mach_absolute_time`, mutex를 직접 가리켰다.

권고:

- 활성 handler와 전파 대상뿐 아니라 Rust/Python logger filter와 Python dispatch handler도 모두 없는 경우에만 완전한 레코드 생성 전에 반환한다. filter의 부작용과 record 변경 의미를 보존해야 한다.
- formatter/handler 요구 필드에 따라 caller, thread/process, exception, extra를 지연 생성한다.
- logger name과 정적 level name을 매번 owned `String`으로 만들지 않도록 레코드 표현을 검토한다.
- 빈 filter/handler 목록의 lock/clone을 immutable snapshot 또는 빠른 존재 flag로 우회한다.

### P1-3. args·extra·포매터가 중복 변환과 할당을 만든다

- `src/py_logger.rs:416-433`: Python args를 재귀적으로 `serde_json::Value`로 변환한다.
- `src/core.rs:365-384`: `%` 포맷 시 이를 다시 Python 객체로 바꾸고 Python `__mod__`를 호출한다.
- `src/formatter.rs:222-358`: 이미 고정된 format string을 매 로그마다 다시 파싱한다.
- `src/formatter.rs:199-202`: thread-local scratch buffer를 사용하지만 반환 시 결과 `String` 전체를 clone한다.
- `src/formatter.rs:305-317`: `asctime`마다 local datetime과 strftime 문자열을 만든다.
- `src/formatter.rs:468-474`: `ColorFormatter`는 매 호출 `PythonFormatter`를 만들며 format/date 문자열을 clone한다.

권고:

- formatter 생성 시 placeholder를 token plan으로 한 번만 파싱한다.
- 초 단위 날짜 prefix cache가 허용되는 포맷은 timestamp 변환을 재사용한다.
- `%` args는 Python→JSON→Python 왕복을 피하는 표현을 설계하되 Python handler 호환성 경계를 별도로 둔다.
- ColorFormatter가 사전 생성한 내부 formatter/plan을 재사용하도록 한다.

### P2. producer hot path가 다중 스레드에서 확장되지 않는다

`PyLogger`의 `debug/info/...` 메서드는 `Python` token을 받은 상태로 레코드 생성과 handler emit까지 수행한다. 반면 명시적으로 GIL을 놓는 `py.detach()`는 `src/globals.rs:102-109`의 전역 `flush()`에서만 확인된다. 측정 결과 1~8스레드 처리량이 사실상 고정됐다.

이는 `docs/compatibility.md:28-35`와 `docs/comparison.md:12-23` 등이 주장하는 “즉시 GIL 해제, formatting/filtering/bubbling/I/O 전체가 GIL 밖” 설명과도 다르다. 최적화 전까지 공개 문구를 현재 구현 범위에 맞게 수정해야 한다.

권고:

- Python filter/handler/caller가 없는 pure-Rust branch는 Python 종속 필드 추출 후 GIL 밖에서 emit한다.
- File/Rotating/Memory handler의 단일 mutex가 다음 병목이 될 수 있으므로 GIL 분리 후 다시 프로파일한다.
- free-threaded CPython 빌드에서는 별도 검증이 필요하다.

## 5. 기존 벤치마크의 신뢰도 문제

현재 문서의 일부 높은 수치는 실제 전달량이 아니라 producer 호출률일 가능성이 있다.

1. `benchmark/basic_handlers_benchmark.py:20`에서 stdlib `logging`을 가져온 같은 프로세스가 `benchmark/basic_handlers_benchmark.py:63`에서 `logxide`를 import한다. 이 import는 `logxide/__init__.py:193`과 `logxide/module_system.py:245-340`을 통해 기존 logger의 메서드와 `logging.getLogger/basicConfig`를 LogXide 경로로 patch한다. 따라서 `benchmark/basic_handlers_benchmark.py:178-188`의 “Python logging”과 stdlib 기반 Structlog은 순수 비교군이 아니다.
2. `benchmark/basic_handlers_benchmark.py:106-107`의 `with open(os.devnull, "w") as self.null_stream`은 생성자 종료 전에 stream을 닫는다. 이후 Python/Loguru/Logbook/Structlog/Picologging StreamHandler가 이 닫힌 객체를 사용해 정상 출력 대신 오류·skip 경로를 측정한다.
3. `benchmark/basic_handlers_benchmark.py:140-152`는 호출 수와 시간만 측정하고 sink의 실제 메시지 수를 검증하지 않는다. 비동기 drop이 빠른 처리량으로 기록된다.
4. `benchmark/basic_handlers_benchmark.py:423-435`는 Python `sys.stderr`를 handler 생성 동안만 `/dev/null`로 바꾼다. Rust StreamHandler는 이후 OS stderr로 직접 쓰므로 이 리다이렉션은 측정 sink를 제어하지 못한다.
5. `benchmark/basic_handlers_benchmark.py:440-457`의 “LogXide RotatingFileHandler”는 rotating handler를 만들지 않고 filename도 없는 `basicConfig()`를 호출한다. 실제로는 StreamHandler 경로다.
6. `benchmark/perf_micro.py:35-45`, `benchmark/perf_micro.py:176-188`은 로컬 MemoryHandler를 반복 등록한다. P0-1 문제 때문에 뒤 시나리오일수록 누적 Python dispatch 비용이 증가한다.
7. `docs/benchmarks.md:91-120`의 “same harness/apples-to-apples” File/Stream/Rotating 표는 모두 위 결함의 영향을 받는다. 동일 수치를 재게시한 `README.md:42-49`, `docs/comparison.md:21-31`, `docs/comparison-stdlib.md:21-31`, `docs/comparison-picologging.md:23-34`, `docs/comparison-structlog.md:21-32`도 하네스 수정 전에는 성능 근거로 사용하면 안 된다.

벤치마크 수정 원칙:

- 시나리오마다 새 프로세스를 사용한다.
- stdlib/Structlog 비교 프로세스에는 `logxide`를 import하지 않고, 각 library를 별도 worker에서 실행한다.
- 발행 수, sink 확인 수, queue drop 수, 전송 실패 수, flush 완료를 함께 기록한다.
- 동기/비동기 로거를 비교할 때 “producer latency”와 “durable throughput”을 별도 표로 낸다.
- RotatingFileHandler는 실제 회전 횟수, 최종 파일 행 수, 총 byte를 검증한다.
- 처리량과 함께 p50/p95/p99 producer latency를 기록한다.

## 6. 권장 실행 순서와 완료 기준

1. **핸들러 레지스트리 분리**
   - 완료 기준: raw 로컬 FileHandler가 전역 FileHandler의 ±10% 이내이고, 핸들러 100개 누적 후 무관한 logger 비용 증가가 10% 미만이며, 공개 handler의 owner/unrelated 전달 건수가 각각 1/0.
2. **queue overflow/관측성 계약 확정**
   - 완료 기준: flush 뒤 in-flight가 0일 때 `sink_acknowledged + queue_dropped + delivery_failed = emitted`가 항상 성립하고, 각 수치가 payload를 포함하지 않는 API/metric으로 노출됨.
3. **HTTP 기본 경로의 GIL 제거**
   - 완료 기준: 100ms sink 포화 시 설정한 overflow 정책대로 동작하고 producer p95가 정책 예산 안에 있음.
4. **caller-info 활성화 범위 축소**
   - 완료 기준: Sentry SDK가 설치만 된 상태에서 caller 필드를 쓰지 않는 로그의 비용이 최소 환경 대비 10% 이내.
5. **레코드/args/formatter 최적화**
   - 완료 기준: no-handler enabled 경로와 `%` args/asctime 경로를 allocation profile과 함께 다시 측정.
6. **벤치마크 교정 후 공개 수치 재작성**
   - 완료 기준: 모든 비동기 결과에 sink 확인·queue drop·전송 실패·in-flight가 포함되고 정책별 회계가 일치함.

## 7. 재현 절차와 원시 결과

### 7.1 격리 빌드

저장소 루트에서 다음 명령을 사용했다. 모든 scenario는 아래 virtualenv의 새 Python process에서 실행했으며, 한 process에서 handler를 누적하는 3.2 실험만 예외다.

```bash
set -euo pipefail
git rev-parse HEAD
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/logxide-perf-repro.XXXXXX")"
trap 'rm -rf -- "$WORKDIR"' EXIT
TARGET="$WORKDIR/target"
DIST="$WORKDIR/dist"
VENV="$WORKDIR/venv"
CARGO_TARGET_DIR="$TARGET" \
  CARGO_PROFILE_RELEASE_DEBUG=1 \
  CARGO_PROFILE_RELEASE_STRIP=none \
  .venv/bin/maturin build --release \
  --interpreter .venv/bin/python \
  --out "$DIST"
.venv/bin/python -m venv "$VENV"
"$VENV/bin/python" -m pip install --no-deps \
  "$DIST/logxide-0.1.22-cp314-cp314-macosx_11_0_arm64.whl"
```

출력 HEAD는 `89afeaaa2aa25dcaedf22415fb2cccf9387e3d1d`였다. Sentry 대조에서만 다음 명령을 추가했다.

```bash
"$VENV/bin/python" -m pip install 'sentry-sdk==2.48.0'
```

Sentry 설치는 설정된 package index에 접근하는 선택적 네트워크 단계다. 공급망 무결성이 필요한 환경에서는 사전 검증한 local wheel과 hash-checking mode를 사용해야 한다.

### 7.2 단일 호출과 스레드 측정

공통 timer는 다음과 같다. 각 setup 뒤 `fn`을 20,000회 warm-up했고, GC를 끈 상태의 각 반복 시간을 `number`로 나눴다.

```python
import gc, statistics, timeit

def measure(fn, number, repeat=7):
    for _ in range(20_000):
        fn()
    gc.collect()
    gc.disable()
    try:
        seconds = timeit.Timer(fn).repeat(repeat=repeat, number=number)
    finally:
        gc.enable()
    raw_ns = [value * 1e9 / number for value in seconds]
    return raw_ns, statistics.median(raw_ns)
```

| 그룹 | 정확한 setup/호출 | `number × repeat` |
|---|---|---:|
| filtered | 새 logger, level=INFO, handler 없음, `debug("filtered")` | 2,000,000 × 7 |
| enabled | 새 logger, level=INFO, handler 없음, `info("enabled")` | 1,000,000 × 7 |
| global file | `register_file_handler(os.devnull, 10, "%(message)s", None)` | 1,000,000 × 7 |
| local file | 새 logger에 native `logging.FileHandler(os.devnull)`를 `addHandler` | 300,000 × 7 |
| handler scaling | 다른 logger마다 native MemoryHandler를 0/1/10/50/100개까지 누적 | 300,000 × 5; 50/100은 80,000 × 5 |
| format | scenario별 새 process와 `/dev/null` global file handler | 500,000 × 7 |
| payload | `%(message)s` global file handler, literal/args/extra별 새 process | 400,000 × 7 |
| threads | handler 없는 동일 logger, barrier 동시 시작, 총 1,000,000건 | 5회 |

원시 반복값은 다음과 같다. 시간은 ns/call, 스레드는 M ops/s이며 표시는 소수 둘째 자리로 반올림했다.

| 시나리오 | 원시 반복값 |
|---|---|
| filtered | 31.16, 31.03, 31.82, 31.41, 31.53, 31.52, 31.50 |
| enabled | 166.14, 168.26, 169.33, 169.47, 167.97, 165.76, 168.26 |
| global file | 224.72, 228.22, 223.12, 224.68, 223.34, 224.58, 226.35 |
| local file | 1386.68, 1383.68, 1378.47, 1394.83, 1398.25, 1378.35, 1381.82 |
| handler 0 | 171.08, 164.62, 165.32, 165.05, 168.29 |
| handler 1 | 1287.14, 1304.53, 1316.78, 1296.61, 1297.19 |
| handler 10 | 2858.33, 2862.41, 2852.69, 2878.46, 2873.52 |
| handler 50 | 9797.94, 9638.71, 9590.72, 9587.91, 9527.27 |
| handler 100 | 17872.52, 17842.30, 17737.79, 17784.93, 17697.34 |
| raw/message/level/asctime 중앙값 | 192.15 / 227.07 / 239.49 / 499.47 |
| literal/args/extra 중앙값 | 219.50 / 465.46 / 569.27 |
| thread 1 | 6.307, 6.273, 6.229, 6.256, 6.273 |
| thread 2 | 6.383, 6.091, 6.101, 6.170, 6.278 |
| thread 4 | 6.135, 6.165, 6.112, 6.287, 6.259 |
| thread 8 | 6.179, 6.105, 6.103, 6.011, 6.104 |

포맷과 payload도 7개 raw 반복을 저장했으며 범위는 각각 raw 188.00~202.75ns, message 224.92~232.63ns, level+message 237.19~244.36ns, asctime 498.01~504.88ns, literal 218.07~226.85ns, args 461.15~476.33ns, extra 566.40~627.26ns였다. 50개 handler의 `clear_handlers()` 전/후 raw 중앙값은 9,532.24/9,600.51ns였다.

### 7.3 전달 건수와 HTTP 대조

Stream은 child process가 native `register_stream_handler("stdout", 10, "%(message)s", None)`로 literal 1행을 반복 발행하고 module-level `flush()`를 호출했다. Parent는 stdout pipe를 동시에 읽어 행 수를 셌다. 느린 sink만 각 행 뒤 `time.sleep(0.0001)`을 적용했다. 원시 결과는 3.5 표의 발행/도달/producer/flush 값이며 child exit code는 모두 0이었다.

HTTP 포화는 `ThreadingHTTPServer(("127.0.0.1", 0), handler)`가 POST마다 100ms 대기한 뒤 200을 반환하도록 하고, raw handler를 아래처럼 구성했다. 50회 개별 호출 시간을 저장한 후 1.5초 기다려 server 수신 수를 셌다.

```python
h = logxide.RustHTTPHandler(
    local_url, capacity=1, batch_size=1, flush_interval=60
)
logger.addHandler(h)
for i in range(50):
    t0 = time.perf_counter()
    logger.info("item-%d", i)
    calls_ms.append((time.perf_counter() - t0) * 1e3)
time.sleep(1.5)
```

두 raw 결과는 각각 `(received=3, producer=276.47ms, p50=6.048ms, p95=6.378ms, >4ms=47/50)`와 `(3, 281.60ms, 6.283ms, 6.408ms, 47/50)`였다.

direct-flush 대조는 같은 local server에 `capacity=10000`, `batch_size=5000`, `flush_interval=60`인 raw HTTPHandler로 5,000건을 발행한 직후 `handler.flush()`를 호출했다. 결과는 `flush=5.007s`, 반환 전 수신 `False`, 반환 후 수신 5,000건, 마지막 payload 도착은 반환 16.406ms 뒤였다.

공개 wrapper 정확성 대조는 scenario별 새 process에서 수행했다. FileHandler는 임시 파일의 `splitlines()` 길이를, MemoryHandler는 `record.getMessage()`를 사용했다. raw 출력은 public file `['once', 'once']`, direct Rust file `['once']`, logger A에만 public MemoryHandler를 연결한 B/A 순차 발행은 `['from-b', 'from-a', 'from-a']`였다.

### 7.4 Sentry 원인 토글

두 새 process 중 하나는 정상 import했고, 다른 하나는 `sys.meta_path` finder가 `sentry_sdk`와 하위 모듈에 `ModuleNotFoundError`를 발생시키도록 한 뒤 `logxide`를 import했다. 양쪽 모두 이후 `clear_handlers()`를 호출하고 handler 없는 enabled logger를 1,000,000회 × 7회 측정했다.

| 조건 | 원시 ns/call | 중앙값 | caller pathname |
|---|---|---:|---|
| `sentry-sdk==2.48.0` 설치/import 허용 | 352.50, 338.36, 336.55, 337.63, 336.15, 335.85, 339.22 | 337.63 | probe script 경로 |
| Sentry import 차단 | 163.71, 168.58, 159.61, 158.95, 159.79, 159.92, 161.36 | 159.92 | 빈 문자열 |

## 8. 결론

현재 성능 개선의 최고 레버리지는 저수준 formatter 미세 최적화가 아니다. 먼저 **Rust-backed public handler를 전역 Python handler로 다시 dispatch해 중복·오배송과 O(N) 비용을 만드는 경로**와 **queue 포화 시 조용한 drop/5ms 대기 및 불완전한 flush 경로**를 제거해야 한다. 그 다음 모든 Python handler에 의해 전역화되는 caller 수집, 레코드 고정비, args/formatter 변환을 순서대로 다루는 것이 측정상 효과가 크다.

이 보고서 작성 과정에서는 소스와 테스트를 수정하지 않았다.
