# Project Prompt: Rust-Python Logging Framework (Drop-in Replacement for Python’s `logging`)

## Objective

Develop a high-performance logging framework with the core logic implemented in Rust and exposed to Python via PyO3 and Maturin. The framework must serve as a **drop-in replacement** for Python’s standard `logging` module, providing an identical API and seamless integration with existing Python code.

---

## Key Requirements

### 1. Pythonic Wrapper (Drop-in Replacement)

- Expose a Python class (and module) via PyO3 that **mirrors the standard `logging` API**.
    - All standard classes, functions, and methods (`getLogger`, `Logger`, `Handler`, `Formatter`, `Filter`, etc.) must be present and behave identically to the standard library.
    - The module should be importable as `from logixde import logging` (via monkey-patching or aliasing).
    - Support hierarchical loggers, log levels, propagation, and configuration (dictConfig, fileConfig, etc.) as in the standard library.

### 2. General

- The Rust core should implement all core logging logic (loggers, handlers, formatters, filters, etc.) for performance and safety.
- Expose all necessary configuration and customization options to Python.
- Provide comprehensive tests to ensure compatibility with the standard `logging` API and correct handler invocation.

---

## Suggested Architecture

### A. Rust Core

- **Logger Struct**
    - Implements all standard logging methods (`info`, `debug`, `warning`, `error`, `critical`, etc.).
    - Supports hierarchical loggers and log level management.
    - Maintains a registry of handlers and propagates log records as per the standard logging model.

- **Handler Trait**
    - Defines a common interface for all handlers (file, stream, memory, etc.).
    - Includes a special handler type for Python callables, which safely invokes Python code from Rust.

- **Formatter Trait**
    - Allows formatting of log records (plain text, JSON, etc.).
    - Supports user-defined formatters.

- **Filter Trait**
    - Enables filtering of log records before they reach handlers.

- **Config Struct**
    - Supports programmatic and file-based configuration (YAML/JSON/dictConfig).


### B. PyO3 Python Bindings

- **Expose Rust Logger as Python Class**
    - All methods and properties of the standard `logging.Logger` are available.
    - `getLogger`, `basicConfig`, and other module-level functions are provided.

- **Handler Registration API**
    - Python users can register and remove handlers using standard methods (`addHandler`, `removeHandler`).
    - Python callables can be registered as handlers and will receive log records as Python objects.

- **Module Initialization**
    - The module can be imported as `from logixde import logging` for drop-in replacement.
    - Optionally, provide a compatibility layer for third-party libraries expecting the standard `logging` module.

### C. Migration Layer

- **Drop-in Replacement**
    - The Python module/package can be used as a direct substitute for the standard `logging` module.
    - Existing code using `from logixde import logging` and standard logging configuration should work without modification.

---

## Deliverables

- Rust library (with PyO3) implementing the logging core and Python bindings.
- Python module/package that can be used as a drop-in replacement for `logging`.
- Documentation and migration guide for replacing standard `logging` with the new framework.
- Example scripts demonstrating:
    - Basic logging usage.
    - Compatibility with existing logging configuration patterns.

---

## Notes

- The primary goal is **compatibility**: existing Python code using `logging` should work without modification.
- Performance and thread safety are important, especially when bridging between Rust and Python.

---

**Start by designing the Rust core API and the PyO3 bindings, then implement the Python wrapper and handler registration mechanism.**
