"""Model selection by task role.

Every model ID in VALENCE lives here. Nothing else hard-codes one.

**Why this module exists.** The upstream tree hard-coded 17 model IDs across
10 files. On 2026-08-13, live verification against a newly issued API key found
15 of them dead:

- The entire Gemini 2.5 text family (``gemini-2.5-flash``,
  ``gemini-2.5-flash-lite``, ``gemini-2.5-pro``) returns 404 for keys issued
  after its retirement — "no longer available to new users". That broke the
  planner, the executor, error recovery, code generation, document processing,
  and Gemini-backed web search. Silently, and everywhere at once.
- 16 of 22 OpenRouter text models and 4 of 8 vision models no longer exist.

The structural cause was dated model IDs scattered across the codebase. Two
fixes, both applied here:

1. **Prefer non-dated ``-latest`` aliases.** They track Google's current model
   for a tier instead of pinning to one that will be retired.
2. **Select by role, not by name.** Callers ask for ``FAST`` or ``REASONING``.
   Swapping a model is a one-line change in this file.

Every ID below was verified callable — not merely *listed*. ``models.list()``
reports retired models that 404 on invocation, so listing proves nothing.

Override any role from the environment without touching code::

    VALENCE_MODEL_FAST=gemini-3.5-flash-lite
    VALENCE_MODEL_REASONING=gemini-3.6-flash
    VALENCE_MODEL_LIVE=models/gemini-2.5-flash-native-audio-latest
"""

from __future__ import annotations

import os

from valence.settings import _read_env_file, ENV_FILE


# ---------------------------------------------------------------------------
# Gemini — verified callable 2026-08-13
# ---------------------------------------------------------------------------

# Cheap, fast, high-volume: relevance gates, classification, language
# detection, short summaries. Measured ~640 ms.
_DEFAULT_FAST = "gemini-flash-lite-latest"

# Planning, replanning, translation, code generation, document understanding.
# Measured ~1.9 s.
_DEFAULT_REASONING = "gemini-flash-latest"

# Real-time voice. Non-dated alias; verified to connect in ~1.2 s and return
# both audio and transcription. main.py previously pinned the dated
# preview-12-2025 build, which works today but will be retired on Google's
# schedule rather than ours.
_DEFAULT_LIVE = "models/gemini-2.5-flash-native-audio-latest"


def _env(name: str, default: str) -> str:
    """Read an override from the process environment, then .env, else default."""
    value = os.environ.get(name)
    if value:
        return value.strip()
    value = _read_env_file(ENV_FILE).get(name)
    if value:
        return value.strip()
    return default


FAST: str = _env("VALENCE_MODEL_FAST", _DEFAULT_FAST)
REASONING: str = _env("VALENCE_MODEL_REASONING", _DEFAULT_REASONING)
LIVE: str = _env("VALENCE_MODEL_LIVE", _DEFAULT_LIVE)


# Models confirmed retired for newly issued keys. Referenced by valence.doctor
# and the tests so a regression to any of them is caught rather than shipped.
RETIRED_GEMINI: frozenset[str] = frozenset({
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
})


# ---------------------------------------------------------------------------
# OpenRouter — verified present in the live catalogue 2026-08-13
# ---------------------------------------------------------------------------

# Ordered by measured round-trip on a trivial prompt, balanced against
# capability — or_client walks this list in order, so position one is the
# common case. The previous pool led with nemotron-3-super-120b, measured at
# 24.7 s: the slowest of every candidate, tried first on every call.
OPENROUTER_TEXT: tuple[str, ...] = (
    "nvidia/nemotron-3-nano-30b-a3b:free",           # ~1.8 s, 256k ctx
    "nvidia/nemotron-3.5-lightning:free",            # ~2.1 s, 1M ctx
    "inclusionai/ling-3.0-tiny:free",                # ~1.1 s, fastest
    "nvidia/nemotron-nano-12b-v2-vl:free",           # ~2.1 s
    "nvidia/nemotron-nano-9b-v2:free",               # ~3.9 s
    "openai/gpt-oss-20b:free",                       # ~4.2 s, 131k ctx
    "google/gemma-4-31b-it:free",                    # capable, rate-limited when measured
    "google/gemma-4-26b-a4b-it:free",
    "liquid/lfm-2.5-2.6b:free",                      # ~5.0 s
    "nvidia/nemotron-3-super-120b-a12b:free",        # ~24.7 s - most capable, last resort
)

# Only models the catalogue reports as accepting image input. The previous
# vision pool listed meta-llama/llama-3.3-70b-instruct and
# nvidia/nemotron-3-super-120b-a12b, neither of which accepts images — so
# vision requests were being sent to text-only models.
OPENROUTER_VISION: tuple[str, ...] = (
    "nvidia/nemotron-nano-12b-v2-vl:free",           # purpose-built vision-language
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-3.5-content-safety:free",
)


def describe() -> str:
    """Human-readable summary, used by valence.doctor."""
    return (
        f"fast={FAST}  reasoning={REASONING}  live={LIVE.removeprefix('models/')}  "
        f"openrouter={len(OPENROUTER_TEXT)} text / {len(OPENROUTER_VISION)} vision"
    )
