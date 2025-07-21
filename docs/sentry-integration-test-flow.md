# Sentry Integration Test Flow

## How Integration Tests Work

```mermaid
graph TD
    A[LogXide Logger] -->|log.error()| B[SentryHandler]
    B -->|emit()| C[Sentry SDK]
    C -->|Process Event| D{before_send Hook}
    D -->|event| E[captured_events.append]
    D -->|return None| F[Drop Event]

    style E fill:#90EE90
    style F fill:#FFB6C1
```

## Step-by-Step Process

1. **Test Setup**
   ```python
   captured_events = []  # List to capture events

   def before_send(event, hint):
       captured_events.append(event)  # Capture for testing
       return None  # Don't send to Sentry
   ```

2. **LogXide Logs an Error**
   ```python
   handler = SentryHandler()
   handler.emit(error_record)  # Triggers Sentry SDK
   ```

3. **Sentry SDK Processes**
   - Creates event structure with all metadata
   - Adds tags, context, exception info
   - Calls `before_send` hook before transmission

4. **Event Capture**
   - `before_send` receives the fully-formed event
   - We save it to `captured_events` list
   - Return `None` to prevent actual sending

5. **Test Verification**
   ```python
   assert len(captured_events) == 1
   event = captured_events[0]
   assert event['level'] == 'error'
   assert event['message'] == 'Test error message'
   ```

## Benefits of This Approach

1. **Real Sentry SDK Behavior**
   - Tests use actual Sentry SDK code
   - Event structure is exactly what Sentry would receive
   - All Sentry features work (breadcrumbs, context, etc.)

2. **No Network Calls**
   - Events never leave the test environment
   - Tests run fast and reliably
   - No dependency on external services

3. **Full Event Inspection**
   - Can verify complete event structure
   - Test tags, extra context, exception details
   - Ensure proper integration behavior

## Example Event Structure

```python
{
    'level': 'error',
    'message': 'Test error message',
    'tags': {
        'logger': 'test.logger',
        'logxide': True
    },
    'extra': {
        'filename': 'test.py',
        'lineno': 42,
        'funcName': 'test_function'
    },
    'exception': {
        'values': [{
            'type': 'ZeroDivisionError',
            'value': 'division by zero',
            'stacktrace': {...}
        }]
    },
    'timestamp': '2024-01-01T00:00:00Z',
    'platform': 'python',
    ...
}
```

This approach ensures our integration tests verify the actual behavior of LogXide with Sentry SDK without requiring a real Sentry account or network connectivity.
