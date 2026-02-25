# Logger-Level Handler Support Design

## Problem Statement

Currently, LogXide uses a global handler registry where all loggers share the same handlers. This differs from Python's standard logging where each logger can have its own handlers.

**Current Architecture:**
```
All Loggers → Global HANDLERS → File/Stream/etc
```

**Target Architecture:**
```
Logger A → Local Handler A → File A
        ↓ (propagate)
        → Global HANDLERS → File B

Logger B → Local Handler B → File C
        ↓ (propagate)
        → Global HANDLERS → File B
```

## Design Goals

1. **Logger-level handler support**: Each logger can have its own handlers
2. **Backward compatibility**: Existing global handler behavior still works
3. **Python API compatibility**: Support `logger.addHandler(handler)`
4. **Performance**: No significant overhead for the common single-handler case
5. **Rust native only**: All handlers remain Rust implementations (no Python handlers)

## Implementation Plan

### Phase 1: Core Data Structures

#### 1.1 Add Local Handlers to PyLogger

```rust
pub struct PyLogger {
    inner: Arc<Mutex<Logger>>,
    fast_logger: Arc<fast_logger::FastLogger>,
    handlers: Arc<Mutex<Vec<PyObject>>>,  // For Python compatibility
    local_handlers: Arc<Mutex<Vec<Arc<dyn Handler + Send + Sync>>>>,  // NEW
    propagate: Arc<Mutex<bool>>,
    parent: Arc<Mutex<Option<PyObject>>>,
    manager: Arc<Mutex<Option<PyObject>>>,
}
```

#### 1.2 Handler Trait (Already Exists)

```rust
pub trait Handler: Send + Sync {
    async fn emit(&self, record: &LogRecord);
    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>);
    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>);
}
```

### Phase 2: Python API

#### 2.1 Expose Handler Classes to Python

```python
# Current (via basicConfig only):
logging.basicConfig(filename="app.log")

# New (direct handler creation):
import logxide.logging as logging

logger = logging.getLogger("myapp")
handler = logging.FileHandler("myapp.log")
logger.addHandler(handler)
```

#### 2.2 Handler Factory Functions

```rust
#[pyclass]
pub struct PyFileHandler {
    inner: Arc<FileHandler>,
}

#[pymethods]
impl PyFileHandler {
    #[new]
    fn new(filename: String) -> PyResult<Self> {
        let handler = FileHandler::new(filename)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        Ok(Self {
            inner: Arc::new(handler),
        })
    }
}
```

#### 2.3 addHandler() Implementation

```rust
impl PyLogger {
    #[pyo3(name = "addHandler")]
    fn add_handler(&self, handler: &Bound<PyAny>) -> PyResult<()> {
        // Extract Rust handler from Python wrapper
        if let Ok(file_handler) = handler.extract::<PyFileHandler>() {
            self.local_handlers.lock().unwrap().push(file_handler.inner.clone());
            Ok(())
        } else if let Ok(stream_handler) = handler.extract::<PyStreamHandler>() {
            self.local_handlers.lock().unwrap().push(stream_handler.inner.clone());
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "Only Rust native handlers are supported (FileHandler, StreamHandler, etc.)"
            ))
        }
    }
}
```

### Phase 3: Logging Flow

#### 3.1 Modified Emit Logic

```rust
fn emit_log(&self, record: LogRecord) {
    // 1. Emit to local handlers (if any)
    let local_handlers = self.local_handlers.lock().unwrap();
    if !local_handlers.is_empty() {
        for handler in local_handlers.iter() {
            let _ = SENDER.send(LogMessage::Record(
                Box::new(record.clone()),
                handler.clone()
            ));
        }
    }
    
    // 2. Emit to global handlers (if propagate = true OR no local handlers)
    let should_use_global = local_handlers.is_empty() || *self.propagate.lock().unwrap();
    if should_use_global {
        let _ = SENDER.send(LogMessage::GlobalRecord(Box::new(record)));
    }
}
```

#### 3.2 Channel Message Types

```rust
enum LogMessage {
    // Send to specific handler
    Record(Box<LogRecord>, Arc<dyn Handler + Send + Sync>),
    
    // Send to all global handlers
    GlobalRecord(Box<LogRecord>),
    
    // Flush signal
    Flush(oneshot::Sender<()>),
}
```

### Phase 4: Performance Optimizations

#### 4.1 Fast Path for Single Handler

```rust
fn emit_log_optimized(&self, record: LogRecord) {
    let local_handlers = self.local_handlers.lock().unwrap();
    
    match local_handlers.len() {
        0 => {
            // Fast path: Use global handlers
            let _ = SENDER.send(LogMessage::GlobalRecord(Box::new(record)));
        }
        1 => {
            // Fast path: Single local handler
            let handler = local_handlers[0].clone();
            drop(local_handlers); // Release lock early
            let _ = SENDER.send(LogMessage::Record(Box::new(record), handler));
        }
        _ => {
            // Multiple handlers: Clone and send to each
            for handler in local_handlers.iter() {
                let _ = SENDER.send(LogMessage::Record(
                    Box::new(record.clone()),
                    handler.clone()
                ));
            }
        }
    }
}
```

#### 4.2 Lock-Free Level Check (Already Implemented)

```rust
// Already using AtomicU8 for level checking
if record.levelno < self.level.load(Ordering::Relaxed) as i32 {
    return; // Fast reject
}
```

### Phase 5: Testing Strategy

#### 5.1 Unit Tests

```python
def test_logger_level_handlers():
    """Test that each logger can have its own handlers."""
    logger1 = logging.getLogger("test1")
    logger2 = logging.getLogger("test2")
    
    handler1 = logging.FileHandler("test1.log")
    handler2 = logging.FileHandler("test2.log")
    
    logger1.addHandler(handler1)
    logger2.addHandler(handler2)
    
    logger1.info("message 1")
    logger2.info("message 2")
    
    # test1.log should contain "message 1" only
    # test2.log should contain "message 2" only
```

#### 5.2 Performance Tests

```python
def test_performance_vs_python():
    """Compare performance with Python stdlib logging."""
    # LogXide
    logger = logxide.logging.getLogger("logxide")
    handler = logxide.logging.FileHandler("logxide.log")
    logger.addHandler(handler)
    
    start = time.perf_counter()
    for i in range(10000):
        logger.info(f"message {i}")
    logxide_time = time.perf_counter() - start
    
    # Python stdlib
    py_logger = logging.getLogger("python")
    py_handler = logging.FileHandler("python.log")
    py_logger.addHandler(py_handler)
    
    start = time.perf_counter()
    for i in range(10000):
        py_logger.info(f"message {i}")
    python_time = time.perf_counter() - start
    
    # LogXide should be faster or equal
    assert logxide_time <= python_time * 1.1
```

### Phase 6: Migration Path

#### 6.1 Backward Compatibility

```python
# Old code (still works):
logging.basicConfig(filename="app.log")
logger = logging.getLogger("myapp")
logger.info("message")

# New code (preferred):
logger = logging.getLogger("myapp")
handler = logging.FileHandler("app.log")
logger.addHandler(handler)
logger.info("message")
```

#### 6.2 Documentation Updates

- Update README with new API
- Add examples for logger-level handlers
- Document differences from Python stdlib
- Add performance comparison benchmarks

## Implementation Checklist

### Rust Side
- [ ] Add `local_handlers` field to `PyLogger`
- [ ] Create `PyFileHandler` wrapper class
- [ ] Create `PyStreamHandler` wrapper class
- [ ] Create `PyRotatingFileHandler` wrapper class
- [ ] Implement `addHandler()` method
- [ ] Implement `removeHandler()` method
- [ ] Update emit logic to use local handlers
- [ ] Add fast path optimization for single handler
- [ ] Update channel message types
- [ ] Update background worker to handle targeted messages

### Python Side
- [ ] Export handler classes in `__init__.py`
- [ ] Update `logging` module wrapper
- [ ] Add type hints for new APIs
- [ ] Ensure `getLogger()` returns logger with handler support

### Testing
- [ ] Add unit tests for logger-level handlers
- [ ] Add integration tests with multiple loggers
- [ ] Update benchmark to use logger-level handlers
- [ ] Performance regression tests

### Documentation
- [ ] Update README.md
- [ ] Add LOGGER_HANDLERS.md guide
- [ ] Update API documentation
- [ ] Add migration guide

## Expected Performance

**Current (global handlers only)**:
- FileHandler: ~850k msgs/sec (99% of Python)
- StreamHandler: ~930k msgs/sec (110% of Python)

**Target (logger-level handlers)**:
- Single logger, single handler: Same as current (~850-930k msgs/sec)
- Multiple loggers, different handlers: Each ~800-900k msgs/sec
- Multiple handlers per logger: Proportional (~400-500k msgs/sec for 2 handlers)

**Goal**: Maintain or improve performance while adding flexibility.

## Risks and Mitigations

### Risk 1: Performance Regression
**Mitigation**: 
- Fast path for common cases (single handler)
- Lock-free optimizations where possible
- Comprehensive benchmarking

### Risk 2: API Confusion
**Mitigation**:
- Clear documentation
- Examples for common patterns
- Deprecation warnings if needed

### Risk 3: Complexity
**Mitigation**:
- Incremental implementation
- Extensive testing
- Code review

## Success Criteria

1. ✅ Each logger can have independent handlers
2. ✅ Performance equal to or better than Python stdlib
3. ✅ Backward compatible with existing code
4. ✅ All tests pass (cargo test && pytest)
5. ✅ Benchmark shows logger-level handlers working correctly
6. ✅ Documentation complete and clear