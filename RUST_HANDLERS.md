# LogXide Rust Native Handler Architecture

## Overview

LogXide v0.1.2+ uses **100% Rust native handlers** for maximum performance.
Python handlers are **NOT supported** to avoid FFI overhead and GIL contention.

## Architecture

```
Python Layer:
  logger.info("message") 
      ↓
  Rust FFI (once)
      ↓
  Channel send (once)
      ↓
  Rust native handler
      ↓
  Direct I/O (no GIL, no Python)
```

**vs Old Approach (REMOVED):**
```
Python → Rust → Channel → GIL reacquire → Python handler → Python I/O
```

## Why Rust Native Handlers?

### Theoretical Benefits

Removing Python handler support eliminates:
1. **Second FFI crossing** - No need to call back into Python
2. **GIL contention** - Rust can do I/O without GIL
3. **Python object overhead** - No LogRecord dict creation
4. **Python method calls** - Direct Rust function calls

### Performance Reality

⚠️ **IMPORTANT**: Actual performance has NOT been measured yet.

The channel + async runtime still has overhead. Real-world performance 
depends on:
- Message size
- Logging frequency
- I/O destination (file vs stdout vs network)
- System load

**TODO**: Run comprehensive benchmarks against:
- Python stdlib logging
- Picologging
- Loguru
- Structlog

## API Changes

### ✅ Supported (Use these)

```python
import logxide.logging as logging

# Configure via basicConfig
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log'  # or omit for stderr
)

logger = logging.getLogger('myapp')
logger.info('This goes through Rust native handlers')
```

### ❌ NOT Supported (Will raise error)

```python
# These will raise ValueError
logger.addHandler(handler)  # ❌ Not supported
handler = logging.StreamHandler()  # Creates dummy object
logger.addHandler(handler)  # ❌ Raises ValueError
```

## Handler Classes

All handler classes exist for **API compatibility only**:

- `StreamHandler` - No-op wrapper
- `FileHandler` - No-op wrapper  
- `NullHandler` - No-op wrapper
- `RotatingFileHandler` - No-op wrapper

They can be instantiated but do nothing. Use `basicConfig()` instead.

## Limitations

Current limitations of Rust-only approach:

1. **Single handler only** - Can't write to multiple destinations simultaneously
2. **No custom formatters** - Must use format string in basicConfig
3. **No per-handler filtering** - Only logger-level filtering
4. **Breaking change** - Existing code using addHandler() will break

## Migration from Old Code

**Before (NOT supported):**
```python
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)
```

**After (Use this):**
```python
logging.basicConfig(
    level=logging.DEBUG,
    format='%(message)s'
)
```

## Rust Handler Implementations

Located in `src/handler.rs`:

- `StreamHandler` - Writes to stdout/stderr
- `FileHandler` - Writes to file with buffering
- `RotatingFileHandler` - Auto-rotating file handler
- `NullHandler` - Discards all logs (zero overhead)

All handlers:
- Are async (tokio)
- Thread-safe
- Zero Python interaction

## Testing

Tests using `addHandler()` are **skipped** with explanation.

Working tests use `basicConfig()`:
- `test_stream_handler_writes_to_stream` ✅
- `test_file_handler_writes_to_file` ✅
- `test_basicConfig_creates_working_handler` ✅

Skipped tests (incompatible API):
- `test_multiple_handlers_all_receive_logs` ⏭️
- `test_handler_level_filtering` ⏭️
- Custom formatter tests ⏭️

## FAQ

**Q: Why can't I use custom handlers?**  
A: Custom Python handlers require crossing the FFI boundary twice and acquiring the GIL, which would destroy performance. The tradeoff is API limitation for speed.

**Q: What about custom formatters?**  
A: Use the `format` parameter in `basicConfig()`. Custom Formatter objects are not supported.

**Q: Can I write to multiple destinations?**  
A: Not currently. LogXide supports one output destination at a time via `basicConfig()`.

**Q: Is this faster than picologging?**  
A: Unknown. Benchmarks need to be run. Picologging is pure C and very fast.

**Q: Is this a breaking change?**  
A: Yes. `addHandler()` now raises `ValueError`. Use `basicConfig()` instead.

## Status

✅ Implemented:
- Rust native StreamHandler
- Rust native FileHandler  
- Rust native NullHandler
- Rust native RotatingFileHandler
- `addHandler()` blocks Python handlers
- Tests updated
- Benchmarks updated

❌ Removed:
- `PythonHandler` (deprecated, not used)
- `register_python_handler()` (removed from API)
- Python handler support via `addHandler()`

⏳ TODO:
- Run comprehensive benchmarks
- Compare with picologging, loguru, structlog
- Measure actual speedup
- Profile bottlenecks

## Next Steps

1. Run `benchmark/basic_handlers_benchmark.py`
2. Compare results with competitors
3. Update this document with real numbers
4. Identify remaining bottlenecks
5. Consider adding multi-handler support if performance allows
