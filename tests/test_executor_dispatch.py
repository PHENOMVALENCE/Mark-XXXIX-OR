"""Tests for agent.executor tool dispatch.

Focused on the security-relevant property: an unrecognised tool name must never
reach code execution. It previously did — _call_tool's else-branch handed the
parameters to _run_generated_code, which asks a model to write Python and then
runs it unsandboxed against the user's home directory. A single hallucinated
tool name was therefore enough to trigger arbitrary code execution with no
confirmation.
"""

from __future__ import annotations

import pytest

from agent.executor import KNOWN_TOOLS, _call_tool


def _boom(*args, **kwargs):
    raise AssertionError(
        "code execution was reached from an unknown tool name"
    )


@pytest.mark.parametrize(
    "tool_name",
    [
        "cmd_control",        # the tool the planner prompt used to advertise
        "shell",
        "run_command",
        "execute",
        "totally_made_up_tool",
        "",
    ],
)
def test_unknown_tool_raises_instead_of_executing_code(tool_name, monkeypatch):
    monkeypatch.setattr("agent.executor._run_generated_code", _boom)

    with pytest.raises(ValueError, match="Unknown tool"):
        _call_tool(tool_name, {"task": "rm -rf /"}, None)


def test_unknown_tool_error_lists_what_is_available(monkeypatch):
    monkeypatch.setattr("agent.executor._run_generated_code", _boom)

    with pytest.raises(ValueError) as exc:
        _call_tool("nope", {}, None)

    message = str(exc.value)
    assert "nope" in message
    # The recovery path feeds this back to the planner, so it has to say what
    # the valid options actually are.
    assert "web_search" in message
    assert "file_controller" in message


def test_generated_code_is_still_reachable_when_asked_for_explicitly(monkeypatch):
    """Removing the implicit fallback must not remove the explicit tool."""
    called = {}

    def _record(description, speak=None):
        called["description"] = description
        return "ran"

    monkeypatch.setattr("agent.executor._run_generated_code", _record)

    assert _call_tool("generated_code", {"description": "do a thing"}, None) == "ran"
    assert called["description"] == "do a thing"


def test_generated_code_requires_a_description(monkeypatch):
    monkeypatch.setattr("agent.executor._run_generated_code", _boom)

    with pytest.raises(ValueError, match="description"):
        _call_tool("generated_code", {}, None)


# ---------------------------------------------------------------------------
# Registry consistency
# ---------------------------------------------------------------------------

def test_known_tools_has_no_duplicates():
    assert len(KNOWN_TOOLS) == len(set(KNOWN_TOOLS))


def test_removed_cmd_control_is_not_advertised():
    """actions/cmd_control.py does not exist; nothing may claim it does."""
    assert "cmd_control" not in KNOWN_TOOLS


def test_every_known_tool_is_dispatchable(monkeypatch):
    """No entry in KNOWN_TOOLS may fall through to the unknown-tool error.

    Guards against the list and the dispatch chain drifting apart, which is how
    the planner ended up advertising a tool that had no implementation.
    """
    monkeypatch.setattr("agent.executor._run_generated_code", lambda *a, **k: "ok")

    for tool in KNOWN_TOOLS:
        try:
            _call_tool(tool, {}, None)
        except ValueError as exc:
            # A tool rejecting empty parameters is fine; not being routed is not.
            assert "Unknown tool" not in str(exc), f"{tool} is not dispatchable"
        except Exception:
            # Import errors, missing credentials, and OS calls are all expected
            # here — this test only asserts that dispatch reaches the handler.
            pass


def test_planner_prompt_does_not_reference_missing_tools():
    """The planner's hand-written tool list must not drift from reality."""
    from agent.planner import PLANNER_PROMPT

    assert "cmd_control" not in PLANNER_PROMPT
