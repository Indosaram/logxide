
### 3. Python-side Handler Registration (not primary goal for now, revisit later. Do not consi)
- Allow Python users to **register custom logging handlers** (Python callables) that will receive log records.
    - The package must expose a mechanism for Python code to add/remove handlers at runtime.
    - When a log event occurs, the Rust core should invoke all registered Python handlers with the log record (as a Python object or dict).
    - Ensure thread safety and performance when calling back into Python from Rust (consider GIL management and batching if needed).
    - Support both synchronous and (optionally) asynchronous handler invocation.


- **Python Handler Registry**
    - Maintains a thread-safe list of Python callables registered as handlers.
    - Ensures safe and efficient invocation of Python handlers from Rust, managing the GIL and error handling.


    - Registering and using Python-side handlers.
- The handler registration API should be as intuitive as possible for Python users.
