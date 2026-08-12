"""Tests for valence.log.

Redaction is the security-relevant part, so it carries the most cases: a leaked
key in a log file is a real incident, and the filter is the last line of
defence when something accidentally logs a request payload.
"""

from __future__ import annotations

import logging

import pytest

from valence.log import RedactingFilter, SafeStreamHandler, get_logger, redact, setup_logging


# ---------------------------------------------------------------------------
# Redaction — provider key formats
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "secret, expected_label",
    [
        ("AIzaSyD-1234567890abcdefghijklmnopqrst", "<GEMINI_KEY>"),
        ("sk-or-v1-0123456789abcdef0123456789abcdef", "<OPENROUTER_KEY>"),
        ("sk-ant-api03-0123456789abcdefghijklmnop", "<ANTHROPIC_KEY>"),
        ("sk-proj0123456789abcdefghijklmnop", "<API_KEY>"),
        ("ghp_0123456789abcdefghijklmnopqrstuvwxyz", "<GITHUB_TOKEN>"),
        ("ya29.a0AfH6SMBexampletokenvalue123456", "<OAUTH_TOKEN>"),
    ],
)
def test_provider_keys_are_redacted(secret, expected_label):
    result = redact(f"request failed with key {secret} attached")

    assert secret not in result
    assert expected_label in result


def test_openrouter_key_is_not_swallowed_by_generic_pattern():
    """Ordering matters: the specific label must win over the generic sk- one."""
    result = redact("key=sk-or-v1-0123456789abcdef0123456789abcdef")

    assert "<OPENROUTER_KEY>" in result
    assert "<API_KEY>" not in result


# ---------------------------------------------------------------------------
# Redaction — labelled fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "api_key=supersecretvalue123",
        "api-key: supersecretvalue123",
        'API_KEY="supersecretvalue123"',
        "access_token=supersecretvalue123",
        "refresh_token: supersecretvalue123",
        "client_secret='supersecretvalue123'",
        "password=supersecretvalue123",
    ],
)
def test_labelled_secrets_are_masked(text):
    result = redact(text)

    assert "supersecretvalue123" not in result
    assert "<REDACTED>" in result


def test_field_name_survives_redaction():
    """The log line must stay useful — mask the value, keep the label."""
    result = redact("calling provider with api_key=supersecretvalue123 and model=gpt")

    assert "api_key=" in result
    assert "model=gpt" in result
    assert "supersecretvalue123" not in result


def test_bearer_tokens_are_masked():
    result = redact("Authorization: Bearer abcdef0123456789abcdef")

    assert "abcdef0123456789abcdef" not in result
    assert "<REDACTED>" in result


# ---------------------------------------------------------------------------
# Redaction — false positives
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "Opened VS Code successfully",
        "search returned 6 results for machine learning",
        "C:\\Users\\someone\\Documents\\report.pdf",
        "sk-short",  # too short to be a key
        "",
    ],
)
def test_ordinary_text_is_untouched(text):
    assert redact(text) == text


# ---------------------------------------------------------------------------
# Filter integration
# ---------------------------------------------------------------------------

def test_filter_redacts_the_message():
    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1,
        "using AIzaSyD-1234567890abcdefghijklmnopqrst", None, None,
    )

    RedactingFilter().filter(record)

    assert "AIzaSy" not in record.msg
    assert "<GEMINI_KEY>" in record.msg


def test_filter_redacts_tuple_arguments():
    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1,
        "key is %s", ("AIzaSyD-1234567890abcdefghijklmnopqrst",), None,
    )

    RedactingFilter().filter(record)

    assert "<GEMINI_KEY>" in record.args[0]


def test_filter_redacts_dict_arguments():
    # logging passes mapping-style args wrapped in a tuple and unwraps them in
    # LogRecord.__init__; constructing the record the same way keeps the test
    # faithful to how `logger.info("%(k)s", {...})` actually behaves.
    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1,
        "key is %(k)s", ({"k": "AIzaSyD-1234567890abcdefghijklmnopqrst"},), None,
    )
    assert isinstance(record.args, dict), "logging should have unwrapped the mapping"

    RedactingFilter().filter(record)

    assert "<GEMINI_KEY>" in record.args["k"]


def test_filter_leaves_non_string_arguments_alone():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "n=%d", (42,), None)

    RedactingFilter().filter(record)

    assert record.args == (42,)


def test_redaction_reaches_the_log_file(tmp_path):
    setup_logging(level="DEBUG", log_dir=tmp_path, console=False, force=True)
    get_logger("test.redaction").info(
        "connecting with AIzaSyD-1234567890abcdefghijklmnopqrst"
    )

    for handler in logging.getLogger("valence").handlers:
        handler.flush()

    written = (tmp_path / "valence.log").read_text(encoding="utf-8")
    assert "AIzaSy" not in written
    assert "<GEMINI_KEY>" in written


# ---------------------------------------------------------------------------
# Console safety
# ---------------------------------------------------------------------------

class _Cp1252Stream:
    """Stands in for a legacy Windows console."""

    encoding = "cp1252"

    def __init__(self):
        self.written: list[str] = []

    def write(self, text: str) -> None:
        text.encode("cp1252")  # raises on em-dash, exactly like the real thing
        self.written.append(text)

    def flush(self) -> None:
        pass


def test_unencodable_characters_do_not_raise():
    """A log call must never be the thing that breaks a working feature."""
    stream = _Cp1252Stream()
    handler = SafeStreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))

    handler.emit(
        logging.LogRecord("t", logging.INFO, __file__, 1, "done — 🔧 ok", None, None)
    )

    assert stream.written, "message should still have been written"
    assert "done" in stream.written[0]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def test_file_handler_records_debug_even_when_console_is_quiet(tmp_path):
    """Detail on disk, calm console — diagnose without reproducing."""
    setup_logging(level="ERROR", log_dir=tmp_path, console=False, force=True)
    get_logger("test.levels").debug("a detail worth keeping")

    for handler in logging.getLogger("valence").handlers:
        handler.flush()

    assert "a detail worth keeping" in (tmp_path / "valence.log").read_text(encoding="utf-8")


def test_unwritable_log_dir_degrades_instead_of_raising(tmp_path):
    blocker = tmp_path / "logs"
    blocker.write_text("I am a file, not a directory", encoding="utf-8")

    # Must not raise — losing file logging is a degradation, not a failure.
    setup_logging(log_dir=blocker, console=False, force=True)


def test_get_logger_namespaces_under_valence():
    assert get_logger("actions.open_app").name == "valence.actions.open_app"
    assert get_logger("valence.already").name == "valence.already"


def test_invalid_level_falls_back_to_info(tmp_path):
    setup_logging(level="NOT_A_LEVEL", log_dir=tmp_path, console=True, force=True)

    console = [
        h for h in logging.getLogger("valence").handlers
        if isinstance(h, SafeStreamHandler)
    ]
    assert console and console[0].level == logging.INFO


def test_setup_is_idempotent(tmp_path):
    setup_logging(log_dir=tmp_path, console=True, force=True)
    before = len(logging.getLogger("valence").handlers)
    setup_logging(log_dir=tmp_path, console=True)

    assert len(logging.getLogger("valence").handlers) == before
