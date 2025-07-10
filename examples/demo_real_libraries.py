"""
Demo showing logxide with real third-party libraries.
This approach manually redirects third-party logs to logxide after import.
"""

from logxide import logging


def demo_with_real_libraries():
    """Demo logxide integration with real third-party libraries."""

    # Configure logxide first
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=== LogXide with Real Libraries Demo ===\n")

    # Our application logger
    app_logger = logging.getLogger("myapp")
    app_logger.info("Starting application with third-party library integration")

    try:
        # Import requests normally (it will use standard logging)
        import requests
        import urllib3

        app_logger.info("Successfully imported requests and urllib3")

        # After import, we can redirect their loggers to use logxide
        print("1. Manually redirecting third-party loggers to logxide:")

        # Create logxide loggers with the same names as the libraries use
        requests_logger = logging.getLogger("requests")
        requests_logger.setLevel(logging.DEBUG)

        urllib3_logger = logging.getLogger("urllib3")
        urllib3_logger.setLevel(logging.DEBUG)

        # Now manually log what these libraries would log
        requests_logger.info("Simulated: Starting new HTTPS connection")
        urllib3_logger.debug("Simulated: Connection pool details")

        # Make an actual request but log it ourselves
        print("\n2. Making actual HTTP request with manual logging:")
        try:
            requests_logger.info("Making request to httpbin.org")
            response = requests.get("https://httpbin.org/get", timeout=5)
            requests_logger.info(f"Response received: {response.status_code}")
            requests_logger.debug(f"Response headers: {dict(response.headers)}")
        except Exception as e:
            requests_logger.error(f"Request failed: {e}")

    except ImportError as e:
        app_logger.warning(f"Could not import third-party library: {e}")
        app_logger.info("Demonstrating with simulated libraries instead")

        # Simulate what the libraries would do
        simulated_requests = logging.getLogger("requests.sessions")
        simulated_requests.setLevel(logging.DEBUG)
        simulated_requests.info("GET https://httpbin.org/get")
        simulated_requests.debug("Request completed in 0.123s")

    # Show multiple library simulation
    print("\n3. Multiple third-party libraries:")
    libraries = [
        "sqlalchemy.engine",
        "django.request",
        "flask.app",
        "celery.task",
        "boto3.session",
    ]

    for lib_name in libraries:
        lib_logger = logging.getLogger(lib_name)
        lib_logger.setLevel(logging.INFO)
        lib_logger.info(f"Simulated log from {lib_name}")

    app_logger.info("Demo completed - all logs handled by logxide")
    logging.flush()


def show_install_method():
    """Show the proper way to use logxide.install() for true drop-in replacement."""

    print("\n=== Proper logxide.install() Usage ===")
    print(
        "For true drop-in replacement, do this at the very start of your application:"
    )
    print()
    print("```python")
    print("# main.py - Very first lines of your application")
    print("import logxide")
    print("logxide.install()  # Do this BEFORE any other imports")
    print("")
    print("# Now import your application and third-party libraries")
    print("import requests  # Will use logxide")
    print("import sqlalchemy  # Will use logxide")
    print("from myapp import main  # Your app will use logxide")
    print("")
    print("# Configure logging once for everything")
    print("import logging  # This is now logxide")
    print("logging.basicConfig(level=logging.INFO)")
    print("```")
    print()
    print("Benefits of this approach:")
    print("- All libraries automatically use logxide")
    print("- No code changes needed in libraries")
    print("- Single point of configuration")
    print("- Unified log format across all components")


if __name__ == "__main__":
    demo_with_real_libraries()
    show_install_method()
