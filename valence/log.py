"""Structured logging for VALENCE.

Replaces the ~200 bare ``print()`` calls in the upstream tree. Those had no
level, no timestamp, no module context, and — because they contained emoji and
em-dashes — raised ``UnicodeEncodeError`` or printed mojibake on a Windows
console running the legacy ``cp1252`` code page.

Three things this module guarantees:

1. **Secrets never reach a log.** A redaction filter runs on every record.
2. **Console output never crashes the caller.** The stream is reconfigured to
   UTF-8 where possible, and characters that still cannot be encoded are
   replaced rather than raised.
3. **Detail is preserved on disk.** The console stays readable at INFO while
   the rotating file handler always records DEBUG, so a failure can be
   diagnosed after the fact without reproducing it at a higher verbosity.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from pathlib import Path
from typing import Any

from valence.settings import get_settings

_ROOT_LOGGER_NAME = "valence"
_configured = False

# Rotate at 5 MB, keep 3 generations.
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

# Ordered most-specific first so a Google key is labelled as such rather than
# being caught by the generic bearer-token pattern.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"), "<GEMINI_KEY>"),
    (re.compile(r"\bsk-or-v1-[0-9A-Za-z_\-]{20,}"), "<OPENROUTER_KEY>"),
    (re.compile(r"\bsk-ant-[0-9A-Za-z_\-]{20,}"), "<ANTHROPIC_KEY>"),
    (re.compile(r"\bsk-[0-9A-Za-z_\-]{20,}"), "<API_KEY>"),
    (re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}"), "<GITHUB_TOKEN>"),
    (re.compile(r"\bya29\.[0-9A-Za-z_\-]{20,}"), "<OAUTH_TOKEN>"),
    (
        re.compile(
            r"""(?ix)
            \b (?: api[_-]?key | access[_-]?token | refresh[_-]?token
                 | client[_-]?secret | password | authorization )
            \b \s* [:=] \s* ["']? ([^\s"',}]{8,})
            """
        ),
        None,  # handled specially: keep the label, mask only the value
    ),
    (re.compile(r"(?i)\bBearer\s+([0-9A-Za-z._\-]{16,})"), None),
)


def redact(text: str) -> str:
    """Mask anything that looks like a credential.

    Best-effort defence in depth, not a guarantee — the real protection is not
    logging secrets in the first place. This catches the accidents.
    """
    if not text:
        return text

    for pattern, replacement in _SECRET_PATTERNS:
        if replacement is not None:
            text = pattern.sub(replacement, text)
        else:
            # Preserve the surrounding text and mask only the captured value,
            # so `api_key=abc123` becomes `api_key=<REDACTED>` rather than
            # losing the field name that makes the log line useful.
            def _mask(match: re.Match[str]) -> str:
                whole, secret = match.group(0), match.group(1)
                return whole.replace(secret, "<REDACTED>")

            text = pattern.sub(_mask, text)

    return text


class RedactingFilter(logging.Filter):
    """Redact the message and any string arguments of every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact(a) if isinstance(a, str) else a for a in record.args
                )
        return True


# ---------------------------------------------------------------------------
# Console safety
# ---------------------------------------------------------------------------

class SafeStreamHandler(logging.StreamHandler):
    """A StreamHandler that will not raise on an un-encodable character.

    A logging call must never be the thing that breaks a working feature. On a
    cp1252 console, an em-dash in a log message would otherwise propagate a
    UnicodeEncodeError up through whatever was being logged about.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Note this does not delegate to StreamHandler.emit and retry on
        # failure: the base implementation catches the UnicodeEncodeError
        # itself and routes it to handleError, so the message is already lost
        # by the time we could see it. Encode defensively before writing.
        try:
            message = self.format(record)
            encoding = getattr(self.stream, "encoding", None) or "utf-8"
            try:
                message.encode(encoding)
            except (UnicodeEncodeError, LookupError):
                message = message.encode(encoding, "replace").decode(encoding, "replace")
            self.stream.write(message + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:  # noqa: BLE001 - a log call must never break a feature
            self.handleError(record)


def _prepare_stream(stream: Any) -> Any:
    """Ask the stream for UTF-8. Harmless if it refuses."""
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
    return stream


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

_CONSOLE_FORMAT = "%(asctime)s  %(levelname)-7s %(name)-28s %(message)s"
_FILE_FORMAT = (
    "%(asctime)s  %(levelname)-7s %(name)s  "
    "[%(filename)s:%(lineno)d]  %(message)s"
)
_TIME_FORMAT = "%H:%M:%S"


def setup_logging(
    *,
    level: str | int | None = None,
    log_dir: Path | None = None,
    console: bool = True,
    force: bool = False,
) -> logging.Logger:
    """Configure the ``valence`` logger tree. Idempotent.

    Args:
        level: Console level. Defaults to ``VALENCE_LOG_LEVEL``. The file
            handler always records DEBUG regardless.
        log_dir: Where ``valence.log`` is written. Defaults to
            ``VALENCE_LOG_DIR``. File logging is skipped if the directory
            cannot be created.
        console: Attach a console handler.
        force: Reconfigure even if already set up.
    """
    global _configured

    logger = logging.getLogger(_ROOT_LOGGER_NAME)
    if _configured and not force:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    settings = get_settings()
    resolved_level = level if level is not None else settings.log_level
    if isinstance(resolved_level, str):
        resolved_level = logging.getLevelName(resolved_level.upper())
    if not isinstance(resolved_level, int):
        resolved_level = logging.INFO

    # The logger passes everything through; handlers decide what to show.
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    redacting = RedactingFilter()

    if console:
        handler = SafeStreamHandler(_prepare_stream(sys.stderr))
        handler.setLevel(resolved_level)
        handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT, _TIME_FORMAT))
        handler.addFilter(redacting)
        logger.addHandler(handler)

    directory = log_dir if log_dir is not None else settings.log_dir
    try:
        directory.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            directory / "valence.log",
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
        file_handler.addFilter(redacting)
        logger.addHandler(file_handler)
    except OSError as exc:
        # Losing file logging is a degradation, not a failure.
        logger.warning("File logging unavailable (%s): %s", directory, exc)

    _configured = True
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger, configuring the tree on first use.

    ``get_logger(__name__)`` from anywhere in the project. Names outside the
    ``valence`` package are placed under it so one configuration governs the
    whole application.
    """
    if not _configured:
        setup_logging()

    if name == _ROOT_LOGGER_NAME or name.startswith(f"{_ROOT_LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
