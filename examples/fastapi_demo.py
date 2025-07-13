#!/usr/bin/env python3
"""
FastAPI + LogXide Integration Demo

This demo shows how LogXide works as a perfect drop-in replacement for Python's logging module.
Simply replace 'import logging' with LogXide import and everything works identically.
"""

import time

# Install LogXide as complete logging replacement BEFORE importing uvicorn
import logxide

logxide.install()

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging  # Now this is LogXide


# Create FastAPI app
app = FastAPI(title="LogXide Drop-in Replacement Demo")

# Everything else is identical to standard logging usage
logging.basicConfig(
    level=10,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Use logging exactly as you normally would
logger = logging.getLogger("uvicorn.error")
# print(logger)


# All endpoints use standard logging - no special LogXide code needed
@app.get("/")
async def root():
    """Root endpoint - shows API info."""
    logger.info("Root endpoint accessed")
    return {
        "message": "LogXide Drop-in Replacement Demo",
        "note": "Uses LogXide instead of standard logging for better performance",
        "endpoints": ["/", "/simple", "/levels", "/performance", "/error"],
    }


@app.get("/simple")
async def simple_log():
    """Simple logging example - identical to standard logging usage."""
    logger.info("Simple log message")
    return {"message": "Logged a simple message"}


@app.get("/levels")
async def log_levels():
    """Demonstrate all log levels - standard logging API."""
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    # logger.critical("Critical message")  # Skip critical for demo

    return {"message": "Logged messages at different levels"}


@app.get("/performance")
async def performance_test(count: int = 1000):
    """Performance test - standard logging API."""
    start_time = time.time()

    # Log many messages using standard logging
    for i in range(count):
        logger.info(f"Performance test message {i + 1}")

    # Flush logs (standard logging method)
    logging.flush()

    elapsed = time.time() - start_time
    rate = count / elapsed if elapsed > 0 else 0

    logger.info(
        f"Performance test: {count} messages in {elapsed:.3f}s ({rate:.0f} msg/sec)"
    )

    return {"messages": count, "time": f"{elapsed:.3f}s", "rate": f"{rate:.0f} msg/sec"}


@app.get("/error")
async def error_simulation():
    """Error logging - standard exception handling."""
    try:
        result = 10 / 0  # Intentional error
    except ZeroDivisionError as e:
        logger.error(f"Calculation error: {e}")
        logger.exception("Full exception details:")

        return JSONResponse(
            status_code=500, content={"error": "Calculation failed", "logged": True}
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {"status": "healthy", "logger": "logxide"}


if __name__ == "__main__":
    logger.info("Starting FastAPI server...")

    # Run the app with LogXide logging configuration
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        access_log=True,  # Use our middleware instead
    )
