import logxide

# Install logxide as drop-in replacement
logxide.install()

import logging

print("=== JSON-like Structured Format ===")
json_format = '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","thread":%(thread)d,"process":%(process)d,"message":"%(message)s"}'
logging.basicConfig(format=json_format, datefmt="%Y-%m-%dT%H:%M:%S")

logger = logging.getLogger("api.service")
logger.setLevel(logging.INFO)
logger.info("User authentication successful")
logger.warning("Rate limit approaching for user")
logger.error("Database connection timeout")
logging.flush()
