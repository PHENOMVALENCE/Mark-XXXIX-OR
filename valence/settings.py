"""Centralised, typed configuration for VALENCE.

Replaces the six copies of ``_get_api_key()`` and seven copies of
``get_base_dir()`` scattered across the repository, and gives the assistant a
single place where its identity is defined.

Resolution order, lowest precedence first::

    defaults  <-  config/api_keys.json  <-  .env  <-  os.environ

``config/api_keys.json`` is read for backward compatibility: existing
installations configured through the first-run setup overlay keep working with
no migration step.

Nothing here raises on missing credentials. An unconfigured provider is absent,
not broken — callers ask ``settings.has_gemini`` and degrade gracefully. See
docs/ARCHITECTURE.md §11.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def base_dir() -> Path:
    """Repository root, or the executable's directory when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = base_dir()
CONFIG_DIR = BASE_DIR / "config"
LEGACY_KEYS_FILE = CONFIG_DIR / "api_keys.json"
ENV_FILE = BASE_DIR / ".env"


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a ``.env`` file.

    Deliberately minimal — ``KEY=value``, ``#`` comments, optional surrounding
    quotes, blank lines. No interpolation, no ``export`` prefix handling. This
    avoids a python-dotenv dependency for a format we fully control.
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values

    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return values

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _read_legacy_keys(path: Path) -> dict[str, str]:
    """Read the upstream ``config/api_keys.json``.

    Malformed or unreadable files are treated as absent — a broken config
    should not prevent the application from starting and reporting why.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(v) for k, v in data.items() if isinstance(v, (str, int, float))}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssistantIdentity:
    """Who the assistant is.

    Renaming the assistant must require changing configuration, not application
    logic — so nothing outside this dataclass hard-codes the name.
    """

    name: str = "Valence"
    honorific: str = ""

    @property
    def wake_phrases(self) -> tuple[str, ...]:
        """Phrases that should activate the assistant."""
        lower = self.name.lower()
        return (lower, f"hey {lower}")

    def address(self, sentence: str) -> str:
        """Append the configured honorific to a sentence, if one is set.

        ``address("Done.")`` -> ``"Done."`` with no honorific configured,
        or ``"Done, sir."`` with ``honorific="sir"``.
        """
        if not self.honorific:
            return sentence
        stripped = sentence.rstrip()
        if not stripped:
            return sentence
        if stripped[-1] in ".!?":
            return f"{stripped[:-1]}, {self.honorific}{stripped[-1]}"
        return f"{stripped}, {self.honorific}"


@dataclass(frozen=True)
class Settings:
    """Fully resolved configuration."""

    assistant: AssistantIdentity = field(default_factory=AssistantIdentity)

    # Providers. Empty string means "not configured".
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    local_llm_base_url: str = ""

    # Platform: "windows" | "mac" | "linux"
    os_system: str = "windows"

    # Logging
    log_level: str = "INFO"
    log_dir: Path = field(default_factory=lambda: BASE_DIR / "logs")

    # --- Provider availability --------------------------------------------
    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_openrouter(self) -> bool:
        return bool(self.openrouter_api_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_local_llm(self) -> bool:
        return bool(self.local_llm_base_url)

    @property
    def configured_providers(self) -> tuple[str, ...]:
        names = []
        if self.has_gemini:
            names.append("gemini")
        if self.has_openrouter:
            names.append("openrouter")
        if self.has_openai:
            names.append("openai")
        if self.has_anthropic:
            names.append("anthropic")
        if self.has_local_llm:
            names.append("local")
        return tuple(names)

    # --- Platform ----------------------------------------------------------
    @property
    def is_windows(self) -> bool:
        return self.os_system == "windows"

    @property
    def is_mac(self) -> bool:
        return self.os_system == "mac"

    @property
    def is_linux(self) -> bool:
        return self.os_system == "linux"


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

_OS_FROM_PLATFORM = {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}

# Legacy config/api_keys.json key -> environment variable name.
_LEGACY_ALIASES = {
    "gemini_api_key": "GEMINI_API_KEY",
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "os_system": "VALENCE_OS",
}


def _resolve(
    env: dict[str, str],
    legacy: dict[str, str],
    name: str,
    default: str = "",
) -> str:
    """Look a value up across every source, highest precedence first."""
    if env.get(name):
        return env[name]
    for legacy_key, env_name in _LEGACY_ALIASES.items():
        if env_name == name and legacy.get(legacy_key):
            return legacy[legacy_key]
    return default


def load_settings(
    *,
    env_file: Path | None = None,
    legacy_file: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Settings:
    """Resolve settings from all sources.

    Arguments exist for testing; production callers use :func:`get_settings`.
    """
    environ = os.environ if environ is None else environ
    file_values = _read_env_file(ENV_FILE if env_file is None else env_file)
    legacy = _read_legacy_keys(LEGACY_KEYS_FILE if legacy_file is None else legacy_file)

    # os.environ wins over .env.
    env: dict[str, str] = {**file_values, **{k: v for k, v in environ.items() if v}}

    detected_os = _OS_FROM_PLATFORM.get(platform.system(), "linux")
    os_system = _resolve(env, legacy, "VALENCE_OS", detected_os).lower().strip()
    if os_system not in ("windows", "mac", "linux"):
        os_system = detected_os

    log_dir_raw = _resolve(env, legacy, "VALENCE_LOG_DIR", "logs")
    log_dir = Path(log_dir_raw)
    if not log_dir.is_absolute():
        log_dir = BASE_DIR / log_dir

    return Settings(
        assistant=AssistantIdentity(
            name=_resolve(env, legacy, "VALENCE_ASSISTANT_NAME", "Valence"),
            honorific=_resolve(env, legacy, "VALENCE_USER_HONORIFIC", ""),
        ),
        gemini_api_key=_resolve(env, legacy, "GEMINI_API_KEY"),
        openrouter_api_key=_resolve(env, legacy, "OPENROUTER_API_KEY"),
        openai_api_key=_resolve(env, legacy, "OPENAI_API_KEY"),
        anthropic_api_key=_resolve(env, legacy, "ANTHROPIC_API_KEY"),
        local_llm_base_url=_resolve(env, legacy, "LOCAL_LLM_BASE_URL"),
        os_system=os_system,
        log_level=_resolve(env, legacy, "VALENCE_LOG_LEVEL", "INFO").upper(),
        log_dir=log_dir,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process-wide settings singleton.

    Cached because the upstream code calls its key loaders inside hot paths —
    ``_get_api_key()`` was re-reading and re-parsing JSON on every LLM call.
    """
    return load_settings()


def reload_settings() -> Settings:
    """Discard the cache and re-resolve. Used after the setup flow writes keys."""
    get_settings.cache_clear()
    return get_settings()


# Convenience accessor so callers can write `assistant().name`.
def assistant() -> AssistantIdentity:
    return get_settings().assistant
