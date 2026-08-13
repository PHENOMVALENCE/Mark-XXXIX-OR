"""Live provider verification.

    python -m valence.verify              # connectivity only
    python -m valence.verify --models     # also validate the OpenRouter pool

Deliberately separate from ``valence.doctor``. Doctor is offline, free, and
safe to run anywhere — it confirms a key is *present*. This makes real API
calls, so it confirms a key actually *works*, and answers the question doctor
structurally cannot: are the 22 text and 8 vision model IDs hard-coded in
or_client.py real?

Stale model IDs degrade silently. or_client walks its pool, each dead ID fails,
and it moves to the next — so a mostly-invalid pool presents as slowness rather
than as an error. This is how you find out.

Keys are never printed. Failures report status codes and messages only.
"""

from __future__ import annotations

import argparse
import sys
import time

from valence import models as valence_models
from valence.log import get_logger, setup_logging
from valence.settings import get_settings

log = get_logger("verify")

_OK = "[ OK ]"
_FAIL = "[FAIL]"
_SKIP = "[SKIP]"


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def verify_gemini() -> bool:
    settings = get_settings()
    if not settings.has_gemini:
        print(f"{_SKIP}  Gemini — no key configured")
        return True  # not configured is not a failure

    try:
        from google import genai
    except ImportError:
        print(f"{_FAIL}  Gemini — google-genai not installed")
        return False

    client = genai.Client(api_key=settings.gemini_api_key)
    ok = True

    for role, model in (("fast", valence_models.FAST),
                        ("reasoning", valence_models.REASONING)):
        try:
            started = time.perf_counter()
            response = client.models.generate_content(
                model=model, contents="Reply with exactly: OK",
            )
            elapsed = (time.perf_counter() - started) * 1000
            text = (response.text or "").strip()
            print(f"{_OK}  Gemini {role:<10}{model:<28} {elapsed:>6.0f} ms  -> {text[:20]!r}")
        except Exception as exc:
            detail = str(exc)
            print(f"{_FAIL}  Gemini {role:<10}{model:<28} {type(exc).__name__}: {detail[:90]}")
            if "404" in detail or "no longer available" in detail:
                print(f"         -> This model is retired for this key. Override with")
                print(f"            VALENCE_MODEL_{role.upper()} in .env, or update valence/models.py.")
            ok = False

    return ok


def verify_gemini_live_model() -> bool:
    """Confirm the Live model main.py depends on is actually reachable.

    main.py hard-codes a preview model ID. Preview models get retired, and when
    that happens the failure surfaces as an opaque websocket close during
    startup rather than as a clear error.
    """
    settings = get_settings()
    if not settings.has_gemini:
        print(f"{_SKIP}  Gemini Live — no key configured")
        return True

    try:
        from google import genai
    except ImportError:
        print(f"{_FAIL}  Gemini Live — google-genai not installed")
        return False

    live_model = valence_models.LIVE

    # Open a real session. models.list() is not evidence: it reports retired
    # models that 404 on invocation, which is exactly how the whole Gemini 2.5
    # family passed a listing check while being unusable.
    import asyncio

    from google.genai import types

    async def _probe() -> tuple[bool, str]:
        client = genai.Client(api_key=settings.gemini_api_key,
                              http_options={"api_version": "v1beta"})
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="Reply with one word.",
        )
        started = time.perf_counter()
        async with client.aio.live.connect(model=live_model, config=config) as session:
            elapsed = (time.perf_counter() - started) * 1000
            await session.send_client_content(
                turns={"parts": [{"text": "Say the word ready."}]}, turn_complete=True
            )
            got_audio, said = False, ""
            async for response in session.receive():
                if response.data:
                    got_audio = True
                content = response.server_content
                if content and content.output_transcription and content.output_transcription.text:
                    said += content.output_transcription.text
                if content and content.turn_complete:
                    break
            return got_audio, f"{elapsed:.0f} ms, said {said.strip()[:20]!r}"

    bare = live_model.removeprefix("models/")
    try:
        got_audio, detail = asyncio.run(_probe())
        if not got_audio:
            print(f"{_FAIL}  Gemini Live      {bare} connected but returned no audio")
            return False
        print(f"{_OK}  Gemini Live      {bare}  {detail}")
        return True
    except Exception as exc:
        print(f"{_FAIL}  Gemini Live      {bare}  {type(exc).__name__}: {str(exc)[:110]}")
        print(f"         -> The voice loop cannot connect. Override with")
        print(f"            VALENCE_MODEL_LIVE in .env, or update valence/models.py.")
        return False


# ---------------------------------------------------------------------------
# OpenRouter
# ---------------------------------------------------------------------------

def verify_openrouter() -> bool:
    settings = get_settings()
    if not settings.has_openrouter:
        print(f"{_SKIP}  OpenRouter — no key configured")
        return True

    from or_client import client

    try:
        started = time.perf_counter()
        reply = client.chat("Reply with exactly: OK", max_tokens=16)
        elapsed = (time.perf_counter() - started) * 1000
        print(f"{_OK}  OpenRouter       {elapsed:.0f} ms  -> {reply[:40]!r}")
        return True
    except Exception as exc:
        print(f"{_FAIL}  OpenRouter       {type(exc).__name__}: {str(exc)[:160]}")
        return False


def verify_model_pool() -> bool:
    """Check every hard-coded model ID against OpenRouter's live catalogue."""
    settings = get_settings()
    if not settings.has_openrouter:
        print(f"{_SKIP}  Model pool — no OpenRouter key configured")
        return True

    import requests

    from or_client import TEXT_MODELS, VISION_MODELS, client

    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {client.api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        available = {m["id"] for m in response.json().get("data", [])}
    except Exception as exc:
        print(f"{_FAIL}  Model pool       could not fetch catalogue: "
              f"{type(exc).__name__}: {str(exc)[:120]}")
        return False

    print(f"\n  OpenRouter catalogue: {len(available)} models available\n")

    ok = True
    for label, pool in (("TEXT", TEXT_MODELS), ("VISION", VISION_MODELS)):
        alive = [m for m in pool if m in available]
        dead = [m for m in pool if m not in available]

        status = _OK if not dead else _FAIL
        print(f"{status}  {label} pool: {len(alive)}/{len(pool)} valid")
        for model in dead:
            print(f"         DEAD  {model}")
        if dead:
            ok = False
            print(f"         -> Remove these from or_client.py. Each dead ID is")
            print(f"            tried and skipped, so the pool degrades to slowness.")
        print()

    return ok


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m valence.verify",
        description="Verify configured providers with live API calls.",
    )
    parser.add_argument(
        "--models", action="store_true",
        help="also validate every hard-coded OpenRouter model ID",
    )
    args = parser.parse_args(argv)

    setup_logging(level="WARNING")

    settings = get_settings()
    print("=" * 72)
    print(f"  {settings.assistant.name.upper()} - live provider verification")
    print("=" * 72)
    print()

    if not settings.configured_providers:
        print("  No provider configured. Add keys to .env, then run:")
        print("    python -m valence.doctor")
        return 1

    results = [
        verify_gemini(),
        verify_gemini_live_model(),
        verify_openrouter(),
    ]

    if args.models:
        results.append(verify_model_pool())

    print()
    print("-" * 72)
    if all(results):
        print("  All configured providers reachable.")
        return 0
    print("  Some checks failed - see above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
