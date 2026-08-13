"""VALENCE environment diagnostic.

    python -m valence.doctor

Answers one question: *why is it not working?* Every failed check names a fix
rather than only a symptom. Exit code is 0 when nothing is FAIL, 1 otherwise -
WARN never fails the run, because a missing optional integration is a normal
state, not a broken install.

Nothing here mutates the system and nothing here makes a paid API call. Provider
checks confirm that a key is *present and plausibly shaped*, not that it is
valid - verifying a key costs a request and would make `doctor` unrunnable
offline.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from valence import models as valence_models
from valence.settings import BASE_DIR, ENV_FILE, LEGACY_KEYS_FILE, get_settings


class Status(Enum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class Check:
    name: str
    status: Status
    detail: str
    fix: str = ""


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

MIN_PYTHON = (3, 11)
MAX_TESTED_PYTHON = (3, 12)


def check_python() -> Check:
    version = sys.version_info
    shown = ".".join(str(part) for part in version[:3])

    if version[:2] < MIN_PYTHON:
        return Check(
            "Python version", Status.FAIL, f"{shown} is too old",
            f"VALENCE needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer "
            "(asyncio.TaskGroup is used by the voice loop).",
        )
    if version[:2] > MAX_TESTED_PYTHON:
        return Check(
            "Python version", Status.WARN,
            f"{shown} is newer than the tested range",
            "Native wheels for pyaudio, pycaw, and win10toast are unreliable "
            f"above {MAX_TESTED_PYTHON[0]}.{MAX_TESTED_PYTHON[1]}. If any of "
            "those fail to install, create a venv from Python 3.11 or 3.12.",
        )
    return Check("Python version", Status.OK, shown)


def check_platform() -> Check:
    settings = get_settings()
    host = platform.system()
    detail = f"{host} {platform.release()} (configured as '{settings.os_system}')"

    expected = {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(host)
    if expected and expected != settings.os_system:
        return Check(
            "Platform", Status.WARN, detail,
            f"Configured OS does not match the host. Set VALENCE_OS={expected} "
            "in .env, or clear it to auto-detect. OS-specific tools will "
            "target the wrong platform until this matches.",
        )
    return Check("Platform", Status.OK, detail)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

# (import name, pip name, what breaks without it)
_REQUIRED = [
    ("PyQt6", "PyQt6", "the user interface"),
    ("sounddevice", "sounddevice", "microphone and speaker"),
    ("google.genai", "google-genai", "the real-time voice session"),
    ("requests", "requests", "the OpenRouter provider"),
    ("psutil", "psutil", "system metrics"),
    ("PIL", "pillow", "image handling"),
    ("numpy", "numpy", "audio and image buffers"),
]

_OPTIONAL = [
    ("cv2", "opencv-python", "camera vision"),
    ("mss", "mss", "screen capture"),
    ("pyautogui", "pyautogui", "desktop automation"),
    ("pyperclip", "pyperclip", "clipboard"),
    ("pygetwindow", "pygetwindow", "window management"),
    ("playwright", "playwright", "browser automation"),
    ("ddgs", "ddgs", "web search fallback"),
    ("pdfplumber", "pdfplumber", "PDF reading"),
    ("docx", "python-docx", "Word documents"),
    ("pptx", "python-pptx", "PowerPoint files"),
    ("pandas", "pandas", "CSV and Excel"),
    ("pydub", "pydub", "audio processing"),
    ("youtube_transcript_api", "youtube-transcript-api", "YouTube summaries"),
]

_WINDOWS_ONLY = [
    ("pycaw", "pycaw", "volume control"),
    ("comtypes", "comtypes", "Windows COM interfaces"),
    ("win10toast", "win10toast", "reminder notifications"),
    ("pywinauto", "pywinauto", "Steam and Epic automation"),
]


def _installed(import_name: str) -> bool:
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ImportError, ValueError):
        return False


def check_dependencies() -> list[Check]:
    checks: list[Check] = []

    missing_required = [
        (pip, purpose) for mod, pip, purpose in _REQUIRED if not _installed(mod)
    ]
    if missing_required:
        checks.append(Check(
            "Required packages", Status.FAIL,
            f"{len(missing_required)} missing: "
            + ", ".join(pip for pip, _ in missing_required),
            "pip install -r requirements.txt\n"
            + "\n".join(f"{pip} provides {purpose}"
                        for pip, purpose in missing_required),
        ))
    else:
        checks.append(Check(
            "Required packages", Status.OK, f"all {len(_REQUIRED)} present"
        ))

    optional = list(_OPTIONAL)
    if platform.system() == "Windows":
        optional += _WINDOWS_ONLY

    missing_optional = [
        (pip, purpose) for mod, pip, purpose in optional if not _installed(mod)
    ]
    if missing_optional:
        checks.append(Check(
            "Optional packages", Status.WARN,
            f"{len(missing_optional)} of {len(optional)} missing",
            "These features are unavailable until installed:\n"
            + "\n".join(f"{pip:24} {purpose}"
                        for pip, purpose in missing_optional)
            + "\npip install -r requirements.txt",
        ))
    else:
        checks.append(Check(
            "Optional packages", Status.OK, f"all {len(optional)} present"
        ))

    return checks


def check_browser_automation() -> Check:
    if not _installed("playwright"):
        return Check(
            "Browser automation", Status.WARN, "playwright not installed",
            "pip install -r requirements.txt && playwright install",
        )

    # Playwright ships browsers separately from the package.
    candidates = []
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if override and override != "0":
        candidates.append(Path(override))
    if platform.system() == "Windows":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "ms-playwright")
    else:
        candidates.append(Path.home() / ".cache" / "ms-playwright")

    for path in candidates:
        try:
            if path.is_dir() and any(path.iterdir()):
                return Check("Browser automation", Status.OK,
                             f"playwright browsers at {path}")
        except OSError:
            continue

    return Check(
        "Browser automation", Status.WARN, "no playwright browsers found",
        "playwright install\n"
        "Without this, browser_control and flight_finder fail.",
    )


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

def _audio_devices() -> tuple[list, list] | None:
    """Return (inputs, outputs), or None if the audio stack is unusable."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
    except Exception:  # noqa: BLE001 - any driver problem means "unavailable"
        return None

    inputs = [d for d in devices if d.get("max_input_channels", 0) > 0]
    outputs = [d for d in devices if d.get("max_output_channels", 0) > 0]
    return inputs, outputs


def check_audio() -> list[Check]:
    result = _audio_devices()
    if result is None:
        return [Check(
            "Audio devices", Status.FAIL, "could not query the audio system",
            "Check that sounddevice and its PortAudio backend installed "
            "correctly: pip install --force-reinstall sounddevice",
        )]

    inputs, outputs = result
    checks = []

    if inputs:
        default = inputs[0].get("name", "unknown")
        checks.append(Check("Microphone", Status.OK,
                            f"{len(inputs)} input device(s), e.g. {default}"))
    else:
        checks.append(Check(
            "Microphone", Status.FAIL, "no input device found",
            "Connect a microphone and check Windows Settings > Privacy & "
            "security > Microphone. Voice input cannot work without one.",
        ))

    if outputs:
        default = outputs[0].get("name", "unknown")
        checks.append(Check("Speaker", Status.OK,
                            f"{len(outputs)} output device(s), e.g. {default}"))
    else:
        checks.append(Check(
            "Speaker", Status.FAIL, "no output device found",
            "Connect speakers or headphones. VALENCE cannot speak without one.",
        ))

    return checks


# ---------------------------------------------------------------------------
# Configuration and providers
# ---------------------------------------------------------------------------

def check_configuration() -> Check:
    sources = []
    if ENV_FILE.exists():
        sources.append(".env")
    if LEGACY_KEYS_FILE.exists():
        sources.append("config/api_keys.json")

    if not sources:
        return Check(
            "Configuration", Status.WARN, "no configuration file found",
            f"cp .env.example .env  ({BASE_DIR})\n"
            "Then add your API keys. The first-run setup window "
            "can also write config/api_keys.json for you.",
        )
    return Check("Configuration", Status.OK, "reading " + " + ".join(sources))


# Minimum plausible length per provider. Catches truncated pastes, not invalid
# keys - validating a key would cost a request and break offline use.
_KEY_SHAPES = {
    "Gemini": ("gemini_api_key", 30, "https://aistudio.google.com/apikey"),
    "OpenRouter": ("openrouter_api_key", 30, "https://openrouter.ai/keys"),
}


def check_providers() -> list[Check]:
    settings = get_settings()
    checks: list[Check] = []

    for label, (attr, min_length, url) in _KEY_SHAPES.items():
        key = getattr(settings, attr, "")
        env_name = attr.upper() if attr.startswith("gemini") else "OPENROUTER_API_KEY"

        if not key:
            checks.append(Check(
                f"{label} provider", Status.WARN, "no key configured",
                f"Set {env_name} in .env - get one free at {url}",
            ))
        elif len(key) < min_length:
            checks.append(Check(
                f"{label} provider", Status.WARN,
                f"key is only {len(key)} characters",
                "That looks truncated. Re-copy the whole key from "
                f"{url}",
            ))
        else:
            checks.append(Check(
                f"{label} provider", Status.OK,
                f"key present ({len(key)} chars, not validated)",
            ))

    extra = [p for p in settings.configured_providers
             if p not in ("gemini", "openrouter")]
    if extra:
        checks.append(Check("Additional providers", Status.OK, ", ".join(extra)))

    if not settings.configured_providers:
        checks.append(Check(
            "Provider availability", Status.FAIL, "no provider is configured",
            "VALENCE cannot think without at least one. Start with Gemini: "
            "https://aistudio.google.com/apikey",
        ))

    return checks


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def check_storage() -> list[Check]:
    settings = get_settings()
    checks = []

    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.log_dir / ".doctor_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(Check("Log directory", Status.OK, str(settings.log_dir)))
    except OSError as exc:
        checks.append(Check(
            "Log directory", Status.WARN, f"not writable: {exc}",
            f"Set VALENCE_LOG_DIR in .env to a writable path. VALENCE still "
            "runs; logs go to the console only.",
        ))

    memory_file = BASE_DIR / "memory" / "long_term.json"
    if memory_file.exists():
        try:
            size = memory_file.stat().st_size
            checks.append(Check("Memory store", Status.OK,
                                f"{memory_file.name} ({size} bytes)"))
        except OSError as exc:
            checks.append(Check("Memory store", Status.WARN, str(exc)))
    else:
        checks.append(Check("Memory store", Status.OK,
                            "empty (created on first memory)"))

    return checks


def check_models() -> Check:
    """Report the configured models and catch a regression to a retired one.

    Offline: this cannot prove a model is reachable, only that it is not one
    already known to be dead. `python -m valence.verify` does the live check.
    """
    retired = [
        f"{role}={value}"
        for role, value in (("fast", valence_models.FAST),
                            ("reasoning", valence_models.REASONING),
                            ("live", valence_models.LIVE))
        if value.removeprefix("models/") in valence_models.RETIRED_GEMINI
    ]

    if retired:
        return Check(
            "Model selection", Status.FAIL,
            "configured with retired model(s): " + ", ".join(retired),
            "These return 404 for keys issued after their retirement. Override "
            "with VALENCE_MODEL_FAST / _REASONING / _LIVE in .env, or update "
            "valence/models.py.",
        )

    return Check(
        "Model selection", Status.OK, valence_models.describe(),
    )


def check_integrations() -> Check:
    """Report integrations that are designed but not yet built."""
    return Check(
        "Optional integrations", Status.WARN,
        "Calendar, Gmail, Spotify, GitHub not yet implemented",
        "Planned for later phases - see docs/ROADMAP.md. Nothing to configure "
        "yet; VALENCE runs fully without them.",
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def run_checks() -> list[Check]:
    checks = [check_python(), check_platform()]
    checks += check_dependencies()
    checks.append(check_browser_automation())
    checks += check_audio()
    checks.append(check_configuration())
    checks += check_providers()
    checks.append(check_models())
    checks += check_storage()
    checks.append(check_integrations())
    return checks


_MARK = {Status.OK: "[ OK ]", Status.WARN: "[WARN]", Status.FAIL: "[FAIL]"}


def format_report(checks: list[Check], assistant_name: str = "VALENCE") -> str:
    lines = [
        "=" * 72,
        f"  {assistant_name.upper()} - environment diagnostic",
        "=" * 72,
        "",
    ]

    for check in checks:
        lines.append(f"{_MARK[check.status]}  {check.name:24} {check.detail}")
        if check.fix and check.status is not Status.OK:
            for i, fix_line in enumerate(check.fix.split("\n")):
                lines.append(f"        {'-> ' if i == 0 else '   '}{fix_line.strip()}")

    failed = sum(1 for c in checks if c.status is Status.FAIL)
    warned = sum(1 for c in checks if c.status is Status.WARN)
    passed = len(checks) - failed - warned

    lines += ["", "-" * 72,
              f"  {passed} ok, {warned} warning(s), {failed} failure(s)"]

    if failed:
        lines.append(f"  {assistant_name} will not start. Fix the failures above.")
    elif warned:
        lines.append(f"  {assistant_name} will start. Warnings are reduced capability,")
        lines.append("  not breakage.")
    else:
        lines.append("  Everything checks out.")

    lines.append("-" * 72)
    return "\n".join(lines)


def main() -> int:
    checks = run_checks()
    try:
        name = get_settings().assistant.name
    except Exception:  # noqa: BLE001 - doctor must run even if config is broken
        name = "VALENCE"

    report = format_report(checks, name)
    try:
        print(report)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "ascii"
        print(report.encode(encoding, "replace").decode(encoding))

    return 1 if any(c.status is Status.FAIL for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
