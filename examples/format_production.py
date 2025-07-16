from logxide import logging

print("=== Production Format ===")
prod_format = "%(asctime)s [%(process)d:%(thread)d] %(levelname)s %(name)s: %(message)s"
logging.basicConfig(format=prod_format, datefmt="%Y-%m-%d %H:%M:%S")

# Simulate different application components
components = [
    "auth.service",
    "db.connection",
    "api.gateway",
    "cache.redis",
    "queue.processor",
]

for component in components:
    logger = logging.getLogger(component)
    logger.setLevel(logging.INFO)
    logger.info(f"{component} initialized successfully")
    if component == "db.connection":
        logger.warning("Connection pool at 80% capacity")
    elif component == "cache.redis":
        logger.error("Cache miss rate high")
logging.flush()
