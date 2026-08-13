"""Tests for valence.doctor.

The diagnostic must be the one thing that always runs. Its own failure modes
matter more than most: a doctor that crashes on a broken install is useless
precisely when it is needed.
"""

from __future__ import annotations

import pytest

from valence import doctor
from valence.doctor import Check, Status, format_report


# ---------------------------------------------------------------------------
# Exit code contract
# ---------------------------------------------------------------------------

def test_exit_code_is_zero_when_only_warnings(monkeypatch):
    """A missing optional integration is a normal state, not a broken install."""
    monkeypatch.setattr(doctor, "run_checks", lambda: [
        Check("a", Status.OK, "fine"),
        Check("b", Status.WARN, "missing", "install it"),
    ])

    assert doctor.main() == 0


def test_exit_code_is_one_on_failure(monkeypatch):
    monkeypatch.setattr(doctor, "run_checks", lambda: [
        Check("a", Status.OK, "fine"),
        Check("b", Status.FAIL, "broken", "fix it"),
    ])

    assert doctor.main() == 1


def test_main_survives_broken_settings(monkeypatch):
    """Doctor must run even when configuration is what is broken."""
    monkeypatch.setattr(doctor, "run_checks", lambda: [Check("a", Status.OK, "fine")])
    monkeypatch.setattr(
        doctor, "get_settings",
        lambda: (_ for _ in ()).throw(RuntimeError("config exploded")),
    )

    assert doctor.main() == 0


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def test_report_shows_fixes_only_for_problems():
    report = format_report([
        Check("Healthy", Status.OK, "all good", "this fix should stay hidden"),
        Check("Broken", Status.FAIL, "not good", "run the fix command"),
    ])

    assert "this fix should stay hidden" not in report
    assert "run the fix command" in report


def test_report_counts_each_status():
    report = format_report([
        Check("a", Status.OK, ""),
        Check("b", Status.OK, ""),
        Check("c", Status.WARN, ""),
        Check("d", Status.FAIL, ""),
    ])

    assert "2 ok, 1 warning(s), 1 failure(s)" in report


def test_report_distinguishes_will_not_start_from_reduced_capability():
    failing = format_report([Check("a", Status.FAIL, "")])
    warning = format_report([Check("a", Status.WARN, "")])
    clean = format_report([Check("a", Status.OK, "")])

    assert "will not start" in failing
    assert "will start" in warning
    assert "Everything checks out" in clean


def test_report_uses_the_configured_assistant_name():
    report = format_report([Check("a", Status.OK, "")], assistant_name="Atlas")

    assert "ATLAS" in report
    assert "VALENCE" not in report


def test_report_is_ascii_only():
    """Output must survive a cp1252 Windows console without mojibake."""
    report = format_report([
        Check("a", Status.WARN, "detail", "line one\nline two"),
        Check("b", Status.FAIL, "detail", "fix"),
    ])

    report.encode("ascii")  # raises if any non-ASCII slipped in


def test_multiline_fixes_are_indented_consistently():
    report = format_report([Check("a", Status.WARN, "d", "first line\nsecond line")])
    lines = [ln for ln in report.split("\n") if "line" in ln]

    assert lines[0].startswith("        -> first line")
    assert lines[1].startswith("           second line")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def test_python_version_check_accepts_the_running_interpreter():
    """The suite itself runs on a supported interpreter."""
    assert doctor.check_python().status is not Status.FAIL


@pytest.mark.parametrize("version", [(3, 9), (3, 10)])
def test_old_python_fails(monkeypatch, version):
    monkeypatch.setattr(doctor.sys, "version_info", (*version, 0, "final", 0))

    result = doctor.check_python()
    assert result.status is Status.FAIL
    assert "3.11" in result.fix


def test_newer_python_warns_rather_than_fails(monkeypatch):
    monkeypatch.setattr(doctor.sys, "version_info", (3, 14, 0, "final", 0))

    result = doctor.check_python()
    assert result.status is Status.WARN
    assert "3.11" in result.fix


def test_platform_mismatch_warns(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")

    result = doctor.check_platform()
    # The host is Windows in CI here; a configured/host mismatch must be flagged
    # because OS-specific tools would silently target the wrong platform.
    if result.status is Status.WARN:
        assert "VALENCE_OS" in result.fix


def test_missing_required_package_fails(monkeypatch):
    monkeypatch.setattr(doctor, "_installed", lambda name: name != "PyQt6")

    required = next(c for c in doctor.check_dependencies()
                    if c.name == "Required packages")
    assert required.status is Status.FAIL
    assert "PyQt6" in required.detail
    assert "pip install -r requirements.txt" in required.fix


def test_missing_optional_package_only_warns(monkeypatch):
    monkeypatch.setattr(doctor, "_installed", lambda name: name != "pdfplumber")

    optional = next(c for c in doctor.check_dependencies()
                    if c.name == "Optional packages")
    assert optional.status is Status.WARN
    assert "pdfplumber" in optional.fix


def test_audio_failure_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(doctor, "_audio_devices", lambda: None)

    checks = doctor.check_audio()
    assert len(checks) == 1
    assert checks[0].status is Status.FAIL


def test_missing_microphone_fails(monkeypatch):
    monkeypatch.setattr(
        doctor, "_audio_devices",
        lambda: ([], [{"name": "Speakers", "max_output_channels": 2}]),
    )

    checks = {c.name: c for c in doctor.check_audio()}
    assert checks["Microphone"].status is Status.FAIL
    assert checks["Speaker"].status is Status.OK


def test_no_provider_configured_is_a_failure(monkeypatch):
    class _Empty:
        gemini_api_key = ""
        openrouter_api_key = ""
        configured_providers = ()

    monkeypatch.setattr(doctor, "get_settings", lambda: _Empty())

    checks = doctor.check_providers()
    assert any(c.status is Status.FAIL for c in checks)


def test_truncated_key_is_flagged(monkeypatch):
    class _Short:
        gemini_api_key = "AIzaShort"
        openrouter_api_key = "x" * 40
        configured_providers = ("gemini", "openrouter")

    monkeypatch.setattr(doctor, "get_settings", lambda: _Short())

    checks = {c.name: c for c in doctor.check_providers()}
    assert checks["Gemini provider"].status is Status.WARN
    assert "truncated" in checks["Gemini provider"].fix
    assert checks["OpenRouter provider"].status is Status.OK


def test_configured_keys_are_never_echoed(monkeypatch):
    """The diagnostic must not print the key it is reporting on."""
    secret = "AIzaSy" + "x" * 34

    class _Configured:
        gemini_api_key = secret
        openrouter_api_key = "sk-or-v1-" + "y" * 32
        configured_providers = ("gemini", "openrouter")

    monkeypatch.setattr(doctor, "get_settings", lambda: _Configured())

    report = format_report(doctor.check_providers())
    assert secret not in report
    assert "sk-or-v1-" not in report


def test_run_checks_produces_a_report_without_raising():
    """End-to-end on the real environment — no mocks."""
    checks = doctor.run_checks()

    assert checks
    assert all(isinstance(c, Check) for c in checks)
    format_report(checks).encode("ascii")


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

def test_model_check_passes_with_current_registry():
    assert doctor.check_models().status is Status.OK


def test_model_check_fails_on_a_retired_model(monkeypatch):
    """Regression guard: the Gemini 2.5 family 404s for newly issued keys."""
    monkeypatch.setattr(doctor.valence_models, "FAST", "gemini-2.5-flash-lite")

    result = doctor.check_models()
    assert result.status is Status.FAIL
    assert "gemini-2.5-flash-lite" in result.detail
    assert "VALENCE_MODEL_FAST" in result.fix


def test_model_check_strips_models_prefix_before_comparing(monkeypatch):
    monkeypatch.setattr(doctor.valence_models, "LIVE", "models/gemini-2.0-flash")

    assert doctor.check_models().status is Status.FAIL
