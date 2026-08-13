"""Tests for valence.models.

These are regression guards for a failure that already happened: 15 of 17
hard-coded model IDs in the upstream tree were dead against a newly issued API
key, and nothing in the codebase noticed. The whole agent subsystem was broken
and reported only as generic tool errors.

Live reachability is verified by `python -m valence.verify`, which needs keys
and network. These tests are offline and assert the structural properties that
let the failure happen in the first place.
"""

from __future__ import annotations

import re

import pytest

from valence import models


# ---------------------------------------------------------------------------
# No retired models anywhere
# ---------------------------------------------------------------------------

def test_no_role_points_at_a_retired_model():
    """The Gemini 2.5 family 404s for keys issued after its retirement."""
    for role, value in (("FAST", models.FAST),
                        ("REASONING", models.REASONING),
                        ("LIVE", models.LIVE)):
        bare = value.removeprefix("models/")
        assert bare not in models.RETIRED_GEMINI, (
            f"{role} points at retired model {bare!r}"
        )


def test_retired_set_covers_the_family_that_broke():
    for dead in ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"):
        assert dead in models.RETIRED_GEMINI


# ---------------------------------------------------------------------------
# The structural fix: no dated IDs in text roles
# ---------------------------------------------------------------------------

_DATED = re.compile(r"(preview-)?\d{2}-\d{4}$|-\d{4}-\d{2}-\d{2}$")


def test_text_roles_use_undated_aliases():
    """Dated IDs rot. `-latest` tracks the current model for a tier.

    LIVE is exempt only if no undated alias exists for it; today one does, and
    it is what we use.
    """
    for role, value in (("FAST", models.FAST), ("REASONING", models.REASONING)):
        assert not _DATED.search(value), (
            f"{role}={value!r} pins a dated build that will be retired on "
            "Google's schedule rather than ours"
        )


def test_live_model_uses_undated_alias():
    assert "latest" in models.LIVE, (
        f"LIVE={models.LIVE!r} should track the undated native-audio alias"
    )


def test_live_model_keeps_the_models_prefix():
    """The Live API expects a fully-qualified `models/...` name."""
    assert models.LIVE.startswith("models/")


# ---------------------------------------------------------------------------
# OpenRouter pools
# ---------------------------------------------------------------------------

def test_pools_are_not_empty():
    assert models.OPENROUTER_TEXT
    assert models.OPENROUTER_VISION


def test_pools_have_no_duplicates():
    assert len(models.OPENROUTER_TEXT) == len(set(models.OPENROUTER_TEXT))
    assert len(models.OPENROUTER_VISION) == len(set(models.OPENROUTER_VISION))


def test_no_removed_model_reappears():
    """Every one of these was verified absent from the live catalogue."""
    removed = {
        "nousresearch/hermes-3-llama-3.1-405b:free",
        "minimax/minimax-m2.5:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "qwen/qwen3-coder:free",
        "google/gemma-3-27b-it:free",
        "arcee-ai/trinity-large-preview:free",
        "z-ai/glm-4.5-air:free",
        "google/gemma-3-12b-it:free",
        "google/gemma-3-4b-it:free",
        "google/gemma-3n-e4b-it:free",
        "google/gemma-3n-e2b-it:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "liquid/lfm-2.5-1.2b-instruct:free",
        "liquid/lfm-2.5-1.2b-thinking:free",
        "nvidia/llama-nemotron-embed-vl-1b-v2:free",
    }
    for pool in (models.OPENROUTER_TEXT, models.OPENROUTER_VISION):
        assert not (removed & set(pool)), f"dead model reintroduced: {removed & set(pool)}"


def test_vision_pool_contains_only_image_capable_models():
    """The old pool sent images to text-only models.

    meta-llama/llama-3.3-70b-instruct and nvidia/nemotron-3-super-120b-a12b
    were both listed as vision models and neither accepts image input.
    """
    text_only = {
        "meta-llama/llama-3.3-70b-instruct:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "openai/gpt-oss-20b:free",
        "inclusionai/ling-3.0-tiny:free",
    }
    assert not (text_only & set(models.OPENROUTER_VISION))


def test_slowest_model_is_not_tried_first():
    """or_client walks the pool in order, so position one is the common case.

    The previous pool led with nemotron-3-super-120b, measured at 24.7 s — the
    slowest candidate, tried first on every single call.
    """
    assert models.OPENROUTER_TEXT[0] != "nvidia/nemotron-3-super-120b-a12b:free"


def test_or_client_pools_come_from_the_registry():
    """or_client must not carry its own copy of the model list."""
    import or_client

    assert list(or_client.TEXT_MODELS) == list(models.OPENROUTER_TEXT)
    assert list(or_client.VISION_MODELS) == list(models.OPENROUTER_VISION)


# ---------------------------------------------------------------------------
# Single source of truth
# ---------------------------------------------------------------------------

def test_no_module_hard_codes_a_gemini_model_id():
    """17 IDs across 10 files is how this broke. Keep them in one place."""
    from pathlib import Path

    from valence.settings import BASE_DIR

    pattern = re.compile(r'["\'](models/)?gemini-[0-9]')
    offenders = []

    for path in list(BASE_DIR.glob("*.py")) + \
                list((BASE_DIR / "actions").glob("*.py")) + \
                list((BASE_DIR / "agent").glob("*.py")):
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(BASE_DIR).as_posix())

    assert not offenders, (
        f"hard-coded Gemini model IDs found in {offenders} - "
        "add them to valence/models.py instead"
    )


def test_describe_mentions_every_role():
    summary = models.describe()

    for value in (models.FAST, models.REASONING):
        assert value in summary
    assert models.LIVE.removeprefix("models/") in summary


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------

def test_env_override_wins_over_default(monkeypatch):
    monkeypatch.setenv("VALENCE_MODEL_FAST", "some-other-model")

    assert models._env("VALENCE_MODEL_FAST", "default-value") == "some-other-model"


def test_env_override_is_stripped(monkeypatch):
    monkeypatch.setenv("VALENCE_MODEL_FAST", "  padded-model  ")

    assert models._env("VALENCE_MODEL_FAST", "default-value") == "padded-model"


def test_default_applies_when_unset(monkeypatch):
    monkeypatch.delenv("VALENCE_MODEL_NONEXISTENT", raising=False)

    assert models._env("VALENCE_MODEL_NONEXISTENT", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# Configuration reaches every consumer
# ---------------------------------------------------------------------------

def test_no_module_reads_api_keys_json_directly():
    """Every key reader must go through valence.settings.

    Nine modules opened config/api_keys.json themselves, so a .env-only
    install raised FileNotFoundError at first use and the UI sat on the setup
    overlay forever with no explanation.
    """
    from valence.settings import BASE_DIR

    offenders = []
    for path in (list(BASE_DIR.glob("*.py"))
                 + list((BASE_DIR / "actions").glob("*.py"))
                 + list((BASE_DIR / "agent").glob("*.py"))):
        text = path.read_text(encoding="utf-8")
        if 'json.load(f)["gemini_api_key"]' in text:
            offenders.append(path.relative_to(BASE_DIR).as_posix())

    assert not offenders, (
        f"{offenders} read api_keys.json directly - use valence.settings"
    )
