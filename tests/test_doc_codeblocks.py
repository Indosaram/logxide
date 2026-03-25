#!/usr/bin/env python3
"""
Test suite for verifying Python code blocks in documentation files.

Extracts all ```python code blocks from docs/ markdown files and verifies:
1. Syntax: All blocks must pass `compile()` (no syntax errors)
2. Execution: Standalone blocks (without `# notest`) can be exec'd
"""

import re
import tempfile
import textwrap
from pathlib import Path

import pytest

DOCS_DIR = Path(__file__).parent.parent / "docs"

# Regex to extract fenced Python code blocks from markdown
CODE_BLOCK_RE = re.compile(
    r"```python\s*\n(.*?)```",
    re.DOTALL,
)


def _extract_codeblocks(md_path: Path) -> list[tuple[str, int, str]]:
    """Extract Python code blocks from a markdown file.

    Returns list of (relative_path, block_index, code_string).
    """
    content = md_path.read_text(encoding="utf-8")
    blocks = []
    for i, match in enumerate(CODE_BLOCK_RE.finditer(content)):
        code = textwrap.dedent(match.group(1))
        # Calculate line number of the block start
        line_no = content[: match.start()].count("\n") + 1
        rel_path = md_path.relative_to(DOCS_DIR)
        block_id = f"{rel_path}:L{line_no}"
        blocks.append((block_id, i, code))
    return blocks


def _collect_all_codeblocks() -> list[tuple[str, str]]:
    """Collect all Python code blocks from all docs."""
    blocks = []
    for md_file in sorted(DOCS_DIR.rglob("*.md")):
        for block_id, _, code in _extract_codeblocks(md_file):
            blocks.append((block_id, code))
    return blocks


ALL_CODEBLOCKS = _collect_all_codeblocks()


# ---------------------------------------------------------------------------
# 1. Syntax verification — compile() all blocks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "block_id,code",
    ALL_CODEBLOCKS,
    ids=[b[0] for b in ALL_CODEBLOCKS],
)
def test_doc_codeblock_syntax(block_id: str, code: str):
    """Every Python code block in docs must be syntactically valid."""
    try:
        compile(code, block_id, "exec")
    except SyntaxError as exc:
        pytest.fail(f"Syntax error in {block_id}: {exc}")


# ---------------------------------------------------------------------------
# 2. Execution verification — exec() standalone blocks
# ---------------------------------------------------------------------------


def _is_executable(code: str) -> bool:
    """Determine if a code block should be exec'd.

    Skip blocks that:
    - Contain `# notest` marker
    - Start servers (app.run, uvicorn.run)
    - Use placeholder DSN/URLs that would fail
    - Are partial Django modules (views.py, models.py, middleware.py)
    - Reference undefined names
    - Use `if __name__` guards (main entry points)
    - Are deliberate "wrong" examples (❌)
    - Are partial snippets using undefined `logger`
    """
    if "# notest" in code:
        return False
    # Deliberate wrong-example blocks
    if "❌" in code:
        return False
    # Server starts that will block forever
    if "app.run(" in code or "uvicorn.run(" in code:
        return False
    # Placeholder DSNs / URLs that will cause Sentry errors
    if 'dsn="your-dsn"' in code or 'dsn="your-' in code:
        return False
    if 'dsn="https://your-dsn@' in code or 'dsn="..."' in code:
        return False
    if 'url="https://logs.example.com"' in code:
        return False
    # Django partial modules (reference project-internal imports)
    if "from .models" in code or "from .views" in code:
        return False
    # Django management command base
    if "BaseCommand" in code:
        return False
    # Django LOGGING dict config (uses stdlib handler classes as strings)
    if "'class': 'logging." in code:
        return False
    # Django middleware with MiddlewareMixin
    if "MiddlewareMixin" in code:
        return False
    # References to undefined example variables
    undefined_refs = [
        "process_order(",
        "critical_operation(",
        "process_request(",
        "order.id",
        "user.id",
        "user.username",
        "query_time",
        "user_id",
        "endpoint",
        "ip_address",
        "transaction_id",
    ]
    if any(ref in code for ref in undefined_refs):
        return False
    # Blocks containing if __name__ guard (entry points that call main())
    if "if __name__" in code:
        return False
    # Sentry scope usage (needs active sentry client)
    if "configure_scope" in code or "start_transaction" in code:
        return False
    # SentryHandler.is_available check (needs Sentry configured)
    if "is_available" in code:
        return False
    # Partial snippet using `logger` without defining it or importing logxide
    if "logger." in code and "getLogger" not in code and "from logxide" not in code:
        return False
    # Uses stdlib `import logging` directly (for debugging snippets, etc.)
    if "import logging\n" in code and "from logxide" not in code:
        return False
    # logging.Filter subclass (needs logxide.logging.Filter which may not exist)
    if "logging.Filter" in code:
        return False
    # Sentry before_send / event processors
    if "before_send" in code:
        return False
    # sentry_sdk.init() without arguments—still needs SDK
    if "sentry_sdk.init(" in code:
        return False
    # Partial: uses `logging.` at top level without any import in this block
    if ("logging." in code or "logging\n" in code) and "import" not in code:
        return False
    # Partial: uses sentry_sdk without importing it
    if "sentry_sdk." in code and "import sentry_sdk" not in code:
        return False
    # Blocks that only set format strings (not standalone)
    stripped = code.strip()
    return not stripped.startswith("format=")


def _needs_framework(code: str) -> set[str]:
    """Detect which optional frameworks a code block needs."""
    needed = set()
    framework_markers = {
        "flask": ["from flask ", "import flask", "Flask("],
        "django": ["from django", "import django", "django."],
        "fastapi": ["from fastapi", "import fastapi", "FastAPI("],
        "sentry_sdk": ["import sentry_sdk", "from sentry_sdk", "sentry_sdk."],
        "sqlalchemy": ["from sqlalchemy", "import sqlalchemy"],
        "flask_sqlalchemy": ["from flask_sqlalchemy", "flask_sqlalchemy"],
        "pydantic": ["from pydantic", "import pydantic"],
        "httpx": ["import httpx", "from httpx"],
        "uvicorn": ["import uvicorn", "from uvicorn"],
    }
    for framework, markers in framework_markers.items():
        if any(marker in code for marker in markers):
            needed.add(framework)
    return needed


EXEC_CODEBLOCKS = [
    (block_id, code)
    for block_id, code in ALL_CODEBLOCKS
    if _is_executable(code) and not block_id.split(":")[0].startswith("integrations")
]


@pytest.mark.parametrize(
    "block_id,code",
    EXEC_CODEBLOCKS,
    ids=[b[0] for b in EXEC_CODEBLOCKS],
)
def test_doc_codeblock_exec(block_id: str, code: str):
    """Executable doc code blocks should run without errors.

    Each block is executed in a subprocess to prevent logxide's Rust
    background threads from keeping the pytest process alive.
    """
    import subprocess
    import sys

    needed = _needs_framework(code)

    # Skip if required frameworks are not installed
    for framework in needed:
        try:
            __import__(framework)
        except ImportError:
            pytest.skip(f"Requires {framework}")

    # Run in a subprocess with timeout to prevent hanging
    with tempfile.TemporaryDirectory() as tmpdir:
        script = tmpdir + "/test_block.py"
        with open(script, "w") as f:
            f.write(code)

        result = subprocess.run(
            [sys.executable, script],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip().split("\n")
            # Get last few lines of traceback
            err_msg = "\n".join(stderr[-5:]) if len(stderr) > 5 else "\n".join(stderr)
            pytest.fail(f"Execution error in {block_id}:\n{err_msg}")
