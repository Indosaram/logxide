# Building the Fastest Python Logger in Rust — Part 1: Production Guide

![Part 1 cover](../assets/blog/blog-part1-cover.png)

Last month I was setting up Sentry for a FastAPI project. I'd done this fourteen times before, so I thought I knew the drill. Install sentry-sdk. Configure the SentryHandler. Set the right level so WARNING becomes events but INFO becomes breadcrumbs. Tweak the formatter. Debug why context isn't showing up.

Forty minutes later I had three packages installed, a 25-line config file, and Sentry breadcrumbs that still refused to appear. I stared at my screen and thought: this is stupid. This should take thirty seconds.

That's why I built LogXide. It's a drop-in replacement for Python's stdlib logging, written in Rust. Same API. Same `getLogger`, same format strings. But up to 13× faster, and Sentry and OTLP just work. No handlers to configure. No JSON files to juggle.

## The One-Line Migration

Here's where I save you 45 minutes:

```python
# Before
import logging

# After
from logxide import logging
```

That's it. Everything else stays identical. `logging.getLogger` works. `basicConfig` works. Every library that uses stdlib logging automatically gets the speed boost and observability features.

Behind the scenes, LogXide replaces `sys.modules["logging"]` with itself. Yeah, I know. It's aggressive. Every subsequent `import logging` in your codebase, your dependencies, Django's internals, gets the LogXide version. It works though.

## Flask: The Easy One

Flask was the framework I tested first because I knew it would be easy. Flask's `app.logger` is just a thin wrapper around stdlib logging. LogXide intercepts it automatically.

```python
from flask import Flask
from logxide import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("myapp")

app = Flask(__name__)

@app.route("/")
def index():
    logger.info("Request received")
    return {"status": "ok"}
```

SQLAlchemy queries log through LogXide too. Just set the level:

```python
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
```

No extensions to install. No `init_app` calls. I spent maybe five minutes on Flask support and it just worked.

## Django: The LOGGING Dict from Hell

Django's `LOGGING` dictionary is a crime against readability. Twelve levels of nesting to say "print to stdout." I've seen 80-line LOGGING configs that nobody on the team dares touch. Everyone just copies the same StackOverflow answer and hopes it works.

LogXide works with Django's dictConfig because it patches the handler registry. When Django tries to create a `logging.StreamHandler`, it gets LogXide's version instead.

```python
# settings.py
from logxide import logging

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
```

All the Django loggers work. `django.request`. `django.db`. Your app logs. They all get the performance boost and observability features. You can keep your LOGGING dict minimal because LogXide handles the hard stuff.

## FastAPI: Where Logging Goes to Die

FastAPI with Uvicorn is where things usually get messy. Uvicorn has its own logging setup. Access logs go one place, error logs another. You end up with two logging systems fighting each other, and half your logs missing.

I spent way too long on this. Uvicorn configures loggers at startup, before your code runs. The trick is making sure LogXide is imported before Uvicorn starts logging.

```python
from fastapi import FastAPI
from logxide import logging  # This MUST be first

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("myapp")

app = FastAPI()

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Hello"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

The `uvicorn.error` and `uvicorn.access` loggers get intercepted. Your app logs and Uvicorn's logs flow through the same pipeline. No more missing logs. No more double-formatting.

## Sentry: The Feature That Made Me Build This

This is why LogXide exists.

Normally, adding Sentry logging means configuring a SentryHandler. Setting event levels. Figuring out breadcrumbs. Maintaining yet another config file. Every project I worked on had slightly different Sentry logging setup, and nobody remembered why.

LogXide does it automatically:

```python
import sentry_sdk
sentry_sdk.init(dsn="https://your-dsn@sentry.io/123")

from logxide import logging

logger = logging.getLogger(__name__)
logger.error("Payment failed for user 42")  # → automatically sent to Sentry
logger.info("User logged in")               # → added as Sentry breadcrumb
```

LogXide checks for sentry_sdk at import time. It looks for `Hub.current.client`. If it finds it, the integration configures itself.

Here's what happens:

- `WARNING` and above become Sentry events with full stack traces
- `INFO` and below become breadcrumbs for context
- No SentryHandler to configure
- No logging.yml changes
- Zero lines of Sentry logging config

Install with Sentry support:

```bash
pip install logxide[sentry]
```

The first time I saw this work, I felt actual relief. No more copy-pasting Sentry config from old projects. No more "why aren't my breadcrumbs showing up" debugging sessions. It just works.

## OTLP: Oh, and This Too

Want to ship logs to Grafana Loki, Datadog, Honeycomb, or any OTLP-compatible backend?

```python
from logxide import OTLPHandler, logging

handler = OTLPHandler(
    url="http://localhost:4318/v1/logs",
    service_name="my-api"
)

logger = logging.getLogger("myapp")
logger.addHandler(handler)
logger.info("This goes to your OTLP backend")
```

The OTLP exporter is built in Rust. No external dependencies. It exports HTTP/protobuf to your OTLP endpoint.

Sentry and OTLP work together. An error can trigger a Sentry event and ship to your OTLP backend simultaneously. They don't conflict.

## Performance

LogXide is up to 13× faster than stdlib logging:

| Scenario   |   LogXide |  stdlib |   Speedup |
| :--------- | --------: | ------: | --------: |
| Simple msg | 1.92M ops/s | 146K ops/s | **13.21×** |
| Structured | 1.61M ops/s | 144K ops/s | **11.17×** |
| with `%s` args | 977K ops/s | 144K ops/s | **6.77×** |

It's also ~3× faster than Microsoft's picologging on the same Python version, which is written in C. Picologging exists and is good. LogXide is faster, runs on Python 3.13+, and has Sentry/OTLP built in.

Full benchmarks with methodology are [on GitHub](https://github.com/Indosaram/logxide/blob/main/docs/benchmarks.md).

## Where It Breaks

I need to be honest with you. LogXide isn't perfect.

You can't subclass `LogRecord` or `Logger`. They're Rust types, not Python classes. If you have custom logging subclasses, you'll need to adapt them. Most people don't do this, but if you do, you'll hit a wall.

Custom Python handlers via `addHandler()` work, but they bypass the Rust pipeline. The logs still flow through, but you lose the speed benefit for that handler.

If you use pytest, the standard `caplog` fixture doesn't capture LogXide logs. I provide `caplog_logxide` as a drop-in replacement.

Not all stdlib logging edge cases are covered. The API surface is huge. I've hit the 99% use case, but if you're doing something exotic with logging, test it first.

## Try It

```bash
pip install logxide
```

- GitHub: https://github.com/Indosaram/logxide
- PyPI: https://pypi.org/project/logxide/

LogXide has 10 GitHub stars but 5,767 PyPI downloads per month. People use it. They just don't star it. I find that both encouraging and slightly funny.

Part 2 is coming. I'll write about the Rust core, the GIL deadlocks that nearly made me give up, and how I made Python's logging API work from Rust without breaking the world. The deadlocks were bad. Really bad. I almost deleted the repository twice.
