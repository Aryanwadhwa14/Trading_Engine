"""
utils/logger.py
───────────────
Loguru-based logger factory for the ct_ig pipeline.

KEY DESIGN: stdout sink is added exactly ONCE at module load.
File sinks are tracked by path and added at most once per path.
All callers receive a bound context logger — no new sinks are created
on repeated get_logger() calls, eliminating the duplicate-log problem.
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger as _base

# ── Remove the default Loguru handler ────────────────────────────────────────
_base.remove()

_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[name]}</cyan> | "
    "<level>{message}</level>"
)

# ── Stdout sink — added ONCE at import ───────────────────────────────────────
_base.add(
    sys.stdout,
    format=_LOG_FORMAT,
    level="DEBUG",
    colorize=True,
    enqueue=True,
)

# ── Track file sinks so we never add the same path twice ─────────────────────
_registered_file_sinks: set[str] = set()


def get_logger(name: str = "ct_ig", log_path: Path | None = None):
    """Return a Loguru logger bound to `name`, optionally writing to `log_path`.

    - The stdout sink is shared and added only once (at module import).
    - A file sink for `log_path` is added at most once per unique path.
    - Repeated calls with the same arguments are cheap — no sink duplication.

    Args:
        name:     Label shown in every log line under the `name` field.
        log_path: Optional path for a rotating file sink.

    Returns:
        loguru.Logger bound with `name` context.
    """
    if log_path is not None:
        key = str(Path(log_path).resolve())
        if key not in _registered_file_sinks:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            _base.add(
                str(log_path),
                format=_LOG_FORMAT,
                level="DEBUG",
                colorize=False,
                enqueue=True,
                rotation="50 MB",
                retention="30 days",
            )
            _registered_file_sinks.add(key)

    return _base.bind(name=name)


# Module-level default logger (stdout only; no file sink)
log = get_logger("ct_ig")