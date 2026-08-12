"""Tests for valence.settings.

Resolution order is the contract everything else depends on, so it is tested
explicitly rather than assumed.
"""

from __future__ import annotations

import json

import pytest

from valence.settings import (
    AssistantIdentity,
    Settings,
    _read_env_file,
    _read_legacy_keys,
    load_settings,
)


# ---------------------------------------------------------------------------
# .env parsing
# ---------------------------------------------------------------------------

def test_env_file_parses_basic_pairs(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=abc123\nVALENCE_LOG_LEVEL=DEBUG\n", encoding="utf-8")

    assert _read_env_file(env) == {
        "GEMINI_API_KEY": "abc123",
        "VALENCE_LOG_LEVEL": "DEBUG",
    }


def test_env_file_ignores_comments_and_blank_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# a comment\n"
        "\n"
        "   \n"
        "GEMINI_API_KEY=abc\n"
        "# GEMINI_API_KEY=should_not_win\n",
        encoding="utf-8",
    )

    assert _read_env_file(env) == {"GEMINI_API_KEY": "abc"}


def test_env_file_strips_matching_quotes(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        'A="double"\n'
        "B='single'\n"
        'C=unquoted\n'
        'D="mismatched\'\n',
        encoding="utf-8",
    )

    values = _read_env_file(env)
    assert values["A"] == "double"
    assert values["B"] == "single"
    assert values["C"] == "unquoted"
    # Mismatched quotes are left alone rather than half-stripped.
    assert values["D"] == '"mismatched\''


def test_env_file_keeps_equals_signs_in_values(tmp_path):
    env = tmp_path / ".env"
    env.write_text("LOCAL_LLM_BASE_URL=http://localhost:11434/v1?x=1\n", encoding="utf-8")

    assert _read_env_file(env)["LOCAL_LLM_BASE_URL"] == "http://localhost:11434/v1?x=1"


def test_missing_env_file_is_not_an_error(tmp_path):
    assert _read_env_file(tmp_path / "nope.env") == {}


# ---------------------------------------------------------------------------
# Legacy config/api_keys.json
# ---------------------------------------------------------------------------

def test_legacy_keys_are_read(tmp_path):
    keys = tmp_path / "api_keys.json"
    keys.write_text(
        json.dumps({"gemini_api_key": "g", "openrouter_api_key": "o", "os_system": "mac"}),
        encoding="utf-8",
    )

    assert _read_legacy_keys(keys) == {
        "gemini_api_key": "g",
        "openrouter_api_key": "o",
        "os_system": "mac",
    }


def test_malformed_legacy_keys_do_not_raise(tmp_path):
    keys = tmp_path / "api_keys.json"
    keys.write_text("{ this is not json", encoding="utf-8")

    # A broken config must not stop the app from starting and reporting why.
    assert _read_legacy_keys(keys) == {}


def test_legacy_keys_reads_non_dict_as_absent(tmp_path):
    keys = tmp_path / "api_keys.json"
    keys.write_text('["a", "b"]', encoding="utf-8")

    assert _read_legacy_keys(keys) == {}


# ---------------------------------------------------------------------------
# Resolution order
# ---------------------------------------------------------------------------

def _settings(tmp_path, *, env_text=None, legacy=None, environ=None) -> Settings:
    env_file = tmp_path / ".env"
    if env_text is not None:
        env_file.write_text(env_text, encoding="utf-8")

    legacy_file = tmp_path / "api_keys.json"
    if legacy is not None:
        legacy_file.write_text(json.dumps(legacy), encoding="utf-8")

    return load_settings(
        env_file=env_file,
        legacy_file=legacy_file,
        environ={} if environ is None else environ,
    )


def test_defaults_apply_when_nothing_is_configured(tmp_path):
    s = _settings(tmp_path)

    assert s.assistant.name == "Valence"
    assert s.assistant.honorific == ""
    assert s.gemini_api_key == ""
    assert s.configured_providers == ()
    assert s.log_level == "INFO"


def test_legacy_keys_are_used_when_no_env(tmp_path):
    """Existing installs configured by the setup overlay keep working."""
    s = _settings(tmp_path, legacy={"gemini_api_key": "legacy-g", "openrouter_api_key": "legacy-o"})

    assert s.gemini_api_key == "legacy-g"
    assert s.openrouter_api_key == "legacy-o"
    assert s.configured_providers == ("gemini", "openrouter")


def test_env_file_beats_legacy_keys(tmp_path):
    s = _settings(
        tmp_path,
        env_text="GEMINI_API_KEY=from-env-file\n",
        legacy={"gemini_api_key": "from-legacy"},
    )

    assert s.gemini_api_key == "from-env-file"


def test_process_environment_beats_env_file(tmp_path):
    s = _settings(
        tmp_path,
        env_text="GEMINI_API_KEY=from-env-file\n",
        legacy={"gemini_api_key": "from-legacy"},
        environ={"GEMINI_API_KEY": "from-process"},
    )

    assert s.gemini_api_key == "from-process"


def test_empty_environment_value_does_not_mask_lower_precedence(tmp_path):
    """An exported-but-empty variable should not blank out a real key."""
    s = _settings(
        tmp_path,
        env_text="GEMINI_API_KEY=from-env-file\n",
        environ={"GEMINI_API_KEY": ""},
    )

    assert s.gemini_api_key == "from-env-file"


# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------

def test_os_is_auto_detected_when_unset(tmp_path):
    s = _settings(tmp_path)

    assert s.os_system in ("windows", "mac", "linux")
    assert sum([s.is_windows, s.is_mac, s.is_linux]) == 1


def test_os_can_be_overridden(tmp_path):
    s = _settings(tmp_path, environ={"VALENCE_OS": "linux"})

    assert s.os_system == "linux"
    assert s.is_linux and not s.is_windows


def test_invalid_os_falls_back_to_detection(tmp_path):
    s = _settings(tmp_path, environ={"VALENCE_OS": "solaris"})

    assert s.os_system in ("windows", "mac", "linux")


def test_legacy_os_system_is_honoured(tmp_path):
    s = _settings(tmp_path, legacy={"os_system": "mac"})

    assert s.os_system == "mac"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def test_relative_log_dir_is_anchored_to_repo_root(tmp_path):
    s = _settings(tmp_path, environ={"VALENCE_LOG_DIR": "logs"})

    assert s.log_dir.is_absolute()
    assert s.log_dir.name == "logs"


def test_absolute_log_dir_is_left_alone(tmp_path):
    target = tmp_path / "elsewhere"
    s = _settings(tmp_path, environ={"VALENCE_LOG_DIR": str(target)})

    assert s.log_dir == target


def test_log_level_is_upper_cased(tmp_path):
    s = _settings(tmp_path, environ={"VALENCE_LOG_LEVEL": "debug"})

    assert s.log_level == "DEBUG"


# ---------------------------------------------------------------------------
# Assistant identity
# ---------------------------------------------------------------------------

def test_assistant_name_is_configurable(tmp_path):
    s = _settings(tmp_path, environ={"VALENCE_ASSISTANT_NAME": "Atlas"})

    assert s.assistant.name == "Atlas"
    assert s.assistant.wake_phrases == ("atlas", "hey atlas")


def test_default_wake_phrases():
    assert AssistantIdentity().wake_phrases == ("valence", "hey valence")


@pytest.mark.parametrize(
    "sentence, expected",
    [
        ("Done.", "Done, sir."),
        ("Are you sure?", "Are you sure, sir?"),
        ("Opened VS Code!", "Opened VS Code, sir!"),
        ("Opened VS Code", "Opened VS Code, sir"),
    ],
)
def test_honorific_is_inserted_before_terminal_punctuation(sentence, expected):
    identity = AssistantIdentity(honorific="sir")

    assert identity.address(sentence) == expected


def test_no_honorific_leaves_text_untouched():
    identity = AssistantIdentity(honorific="")

    assert identity.address("Done.") == "Done."


def test_honorific_on_empty_string_is_safe():
    identity = AssistantIdentity(honorific="sir")

    assert identity.address("") == ""
    assert identity.address("   ") == "   "


# ---------------------------------------------------------------------------
# Provider availability
# ---------------------------------------------------------------------------

def test_provider_availability_flags(tmp_path):
    s = _settings(
        tmp_path,
        environ={
            "GEMINI_API_KEY": "g",
            "LOCAL_LLM_BASE_URL": "http://localhost:11434/v1",
        },
    )

    assert s.has_gemini
    assert s.has_local_llm
    assert not s.has_openrouter
    assert not s.has_openai
    assert not s.has_anthropic
    assert s.configured_providers == ("gemini", "local")
