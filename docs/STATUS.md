# VALENCE — Project Status

**Last updated:** 2026-08-12
**Branch:** `codex/master-changes`
**Open PR:** [#1 — Phase 0-1: repository audit, secret protection, and stabilisation](https://github.com/PHENOMVALENCE/Mark-XXXIX-OR/pull/1) *(open, not merged)*
**Position:** Phases 0 and 1 complete. Phase 2 not started.

This is the living ledger. It records what is done with the evidence for it,
what remains, and exactly where to resume. Update it at the end of every working
session.

---

## 1. Where things stand in one paragraph

The upstream Mark-XXXIX-OR fork has been audited by execution, its install path
repaired, its secrets protected, and its worst security hole closed. A
configuration layer, a logging layer, a diagnostic command, and a 96-test suite
now exist. Nothing user-facing has changed yet — the assistant still calls
itself JARVIS and still has no permission model. **The single blocker to any
end-to-end verification is that no Gemini or OpenRouter API key is configured**,
so the voice loop has never been run.

---

## 2. Blocked on you

| Needed | Unblocks | Where to get it |
|---|---|---|
| **Gemini API key** | Voice session, vision, planning — and *any* real end-to-end testing | https://aistudio.google.com/apikey |
| **OpenRouter API key** | Tool-side reasoning, memory extraction, web search quality | https://openrouter.ai/keys |

```bash
cp .env.example .env
```

Then paste the keys into `.env`. It is git-ignored and will not be committed.
Verify with:

```bash
python -m valence.doctor
```

Later phases need more (Google OAuth for Calendar and Gmail, Spotify app,
GitHub token) but none of those block the next several phases of work.

---

## 3. Achieved

### Phase 0 — Audit ✅

| Achievement | Evidence |
|---|---|
| Every module inspected, architecture mapped | [AUDIT.md §4](AUDIT.md) |
| Syntax verified across the tree | `py_compile`, 29/29 clean |
| Import behaviour verified in a clean Python 3.11 venv | 26/27 modules; the failure was `or_client` |
| UI booted headless and run for real event-loop time | `QT_QPA_PLATFORM=offscreen`, 1.5 s, no crash |
| Git history confirmed free of committed secrets | `git log --all -- config/api_keys.json` empty |
| Findings documented, including what was *not* tested | [AUDIT.md §10 appendix](AUDIT.md) |
| Target architecture designed with per-module migration mapping | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Phased roadmap with exit criteria | [ROADMAP.md](ROADMAP.md) |

### Phase 1 — Stabilisation ✅

| Achievement | Commit |
|---|---|
| `.gitignore` + `.env.example` — secrets can no longer be committed | `2878cda` |
| Architecture, audit, and roadmap documentation | `05315be` |
| `requirements.txt` re-encoded UTF-8, PyQt6 + 7 undeclared packages added | `4986995` |
| `valence.settings` — centralised typed configuration and assistant identity | `2ae7eaa` |
| `or_client` key resolution made lazy and injectable | `e6d07a2` |
| `valence.log` — structured logging with credential redaction | `c2e14fd` |
| `valence.doctor` — environment diagnostic | `94ba586` |
| Unknown tool names no longer reach arbitrary code execution | `604df67` |
| `web_search` fallback chain repaired, compare mode wired up | `58c4b53` |
| `pytest.ini` so tests run under both invocations | `b082764` |

### Verified working on this machine

Facts, not assessments:

- `pip install -r requirements.txt` resolves and installs in a clean 3.11 venv
- **27/27 modules import** on an unconfigured checkout (was 26/27)
- `python main.py` **starts** and holds at the setup overlay, stopped only by the
  test timeout
- `python -m valence.doctor` runs and correctly identifies "no provider
  configured" as the sole blocker
- **`web_search` works end to end with no API key** — OpenRouter fails with an
  actionable message, the DuckDuckGo fallback runs, 6 real results returned
- **96 tests pass** under both `pytest` and `python -m pytest`

### Not verified — and why

Carried forward as a standing caveat until a key exists:

- **No live API call has ever been made.** The voice session, planner, memory
  extraction, and vision are assessed from code reading only.
- **No desktop-acting tool has been executed** — `open_app`,
  `computer_settings`, `file_controller`, `send_message` all have real side
  effects.
- **Playwright browser binaries are not installed**, so `browser_control` and
  `flight_finder` are import-checked only.

---

## 4. Remaining — full inventory

Every section of the specification, mapped to its current state.

**Legend:** ✅ done · 🟡 partial (upstream code exists, needs work) · ⬜ not started · 🔑 blocked on credentials

### Foundation

| # | Capability | State | Phase | Note |
|---|---|---|---|---|
| 1 | Repository audit | ✅ | 0 | |
| 2 | Technical documentation | ✅ | 0 | Living — updated each phase |
| 29 | Secrets protection | 🟡 | 1 | `.gitignore` + `.env` done; Windows Credential Manager later |
| 39 | Observability / structured logging | ✅ | 1 | `print()` still present in ~20 upstream modules |
| 44 | Centralised configuration | 🟡 | 1 | Settings object exists; UI/voice/permission categories not yet wired |
| 45 | Testing | 🟡 | 1 | 96 tests on new code; upstream modules untested |
| 46 | Health check | ✅ | 1 | `python -m valence.doctor` |

### Identity and structure

| # | Capability | State | Phase | Note |
|---|---|---|---|---|
| 3 | VALENCE product identity | ⬜ | **2** | ~19 files still say JARVIS / MARK XXXIX |
| 4 | Architectural restructuring | ⬜ | 3 | Incremental, only where justified |
| 25 | Agent orchestrator | 🟡 | 3 | `agent/` exists; intent/plan/execute/verify not separated |
| 26 | Tool registry | ⬜ | 3 | Tools currently declared in 3 places |
| 27 | Permission model (levels 0–4) | ⬜ | 3 | **None exists today** |
| 28 | Command safety + `STOP VALENCE` | 🟡 | 3 | Implicit codegen path closed; explicit path still ungated |
| 30 | Audit log | ⬜ | 3 | |
| 31 | Event-driven architecture | ⬜ | 3 | |
| 32 | State machine | 🟡 | 3 | Bare strings, no transition rules |
| 8 | Multi-model provider abstraction | 🟡 | 3 | Two SDKs used directly; one is retired |
| 40 | Error experience | 🟡 | 3 | Started in `web_search`; raw errors still spoken elsewhere |
| 41 | Offline behaviour | ⬜ | 3 | |

### Voice

| # | Capability | State | Phase | Note |
|---|---|---|---|---|
| 6 | Wake word ("Valence" / "Hey Valence") | ⬜ | 4 | **Nothing exists** — mic is hot whenever unmuted |
| 5 | Conversational engine, sessions, follow-ups | 🟡 | 4 | Gemini Live handles turns; no session timeout logic |
| 7 | Voice pipeline optimisation | 🟡 | 4 | Works; no VAD, no streaming TTS |
| — | Barge-in / interruption | ⬜ | 4 | **Structurally impossible today** — mic is gated off while speaking |
| 42 | Performance instrumentation | ⬜ | 4 | Measure before optimising |

### Machine control

| # | Capability | State | Phase | Note |
|---|---|---|---|---|
| 10 | Windows application control | 🟡 | **5** | `open_app` uses keystroke injection and always reports success |
| 10 | Filesystem operations | 🟡 | 5 | `file_controller` works; destructive ops ungated |
| 10 | System control (volume, brightness, etc.) | 🟡 | 5 | `computer_settings` works; power actions ungated |
| 17 | Media / music control | ⬜ | 5 → 12 | Windows media sessions first, Spotify later |

### Intelligence and data

| # | Capability | State | Phase | Note |
|---|---|---|---|---|
| 20 | Memory — working / episodic / project layers | 🟡 | 6 | Only flat semantic memory exists |
| 20 | Memory retrieval + relevance scoring | ⬜ | 6 | |
| 11 | Smart local file search | ⬜ | 9 | |
| 12 | Document intelligence | 🟡 | 9 | `file_processor` handles many formats already |
| 13 | Web research pipeline | 🟡 | 8 | `web_search` works; no multi-source synthesis |
| 14 | Browser automation | 🟡 | 8 | `browser_control` exists; needs gating + browser install |

### Interface

| # | Capability | State | Phase | Note |
|---|---|---|---|---|
| 33 | UI redesign — original VALENCE identity | ⬜ | 7 | Currently explicit Marvel styling |
| 34 | Dashboard / Compact / Overlay modes | ⬜ | 7 | Dashboard only today |
| 35 | Central state visualiser | 🟡 | 7 | HUD exists, reacts to speaking/muted |
| 36 | Transcript + activity view | 🟡 | 7 | Log panel exists |
| 37 | Dashboard widgets | 🟡 | 7 | CPU/MEM/NET/GPU/TMP exist |
| 38 | UI performance | ⬜ | 7 | Repaints 16 ms unconditionally; 2 subprocesses/1.5 s |

### Integrations

| # | Capability | State | Phase | Note |
|---|---|---|---|---|
| 18 | Visual awareness / screen understanding | 🟡 | 13 | Works; **no capture indicator** |
| 19 | Camera | 🟡 | 13 | Works; must default to off + indicator |
| 15 | Google Calendar | ⬜ 🔑 | 10 | Needs Cloud project + OAuth consent |
| 16 | Gmail | ⬜ 🔑 | 11 | Send must be intent → draft → approve → send |
| 17 | Spotify | ⬜ 🔑 | 12 | Needs developer app |
| 23 | Developer mode | 🟡 | 14 | `code_helper` + `dev_agent` exist, ungated |
| 24 | GitHub integration | ⬜ 🔑 | 15 | Never auto-merge |

### Later

| # | Capability | State | Phase |
|---|---|---|---|
| 21 | Daily briefing | ⬜ | 16 |
| 22 | Task system | ⬜ | 16 |
| 43 | Background service / Windows startup | ⬜ | 16 |
| 47 | First-run setup wizard | 🟡 | 16 |

---

## 5. Known problems still in the tree

Carried from the audit, none yet fixed. Each has a phase.

**Security — Phase 3**

1. **No permission model at all.** `shutdown`, `restart`, WiFi toggle, file
   `delete`, and `send_message` all execute on the model's word alone.
2. **`generated_code` still runs unvalidated model-written Python** when a plan
   asks for it explicitly. The *implicit* path was closed in `604df67`; the
   explicit one still needs an approval gate showing the code first.
3. **`actions/reminder.py` interpolates the reminder message into generated
   Python source**, sanitising only quotes — newlines survive.
4. **Keys are plaintext** in `config/api_keys.json`.
5. **Screen and camera capture have no on-screen indicator.**

**Correctness / debt**

6. **OpenRouter model pool is unvalidated** — 22 text and 8 vision IDs,
   several of which look questionable. Needs a key to check.
7. **`google-generativeai` is retired** and still used by planner, executor, and
   error handler. Emits a `FutureWarning`.
8. **`main.py` is a god module** — 400 lines of tool schemas plus a 130-line
   dispatch chain.
9. **Tool definitions duplicated three times** and already drifted once.
10. **~200 `print()` calls** remain in upstream modules.
11. **`open_app` on Windows types into whatever has focus** and always reports
    success.
12. **UI repaints unconditionally at 16 ms** and `_SysMetrics` spawns
    `nvidia-smi` + `powershell.exe` every 1.5 s from module import.

---

## 6. Resume here tomorrow

**Next phase: Phase 2 — VALENCE identity.** Needs no credentials, no new
dependencies, low risk. The `valence.settings.AssistantIdentity` plumbing built
in `2ae7eaa` exists precisely to make this a config change rather than a
19-file edit.

Concrete first steps:

1. Point `core/prompt.txt` at VALENCE — rewrite voice, tone, and tool discipline.
2. Replace the window title, header, subtitle, and setup overlay text in `ui.py`
   with values read from `settings.assistant`.
3. Replace the HUD orb label (`ui.py:456`) with the configured name.
4. Rename the `shutdown_jarvis` tool to `shutdown_assistant`, keeping the old
   name as an alias for one release.
5. Replace hard-coded `"sir"` across 12 modules with
   `settings.assistant.address(...)`.
6. Normalise `MARKReminder_*` scheduled-task names.
7. Update `readme.md` — **keep the CC BY-NC 4.0 license and upstream
   attribution to FatihMakes intact**.
8. Add tests asserting that changing one config value renames the assistant
   everywhere, and that no Marvel-derived name survives in user-facing text.

**Then Phase 3**, where the permission model and tool registry land — that is
where items 1–5 in §5 above get closed.

**If a Gemini key is added first**, do this before Phase 2 instead: run the
voice loop end to end and record what actually happens. Several audit findings
about the voice pipeline are code-reading assessments that deserve confirmation,
and the OpenRouter model pool (§5 item 6) can finally be validated.

---

## 7. Session log

| Date | Session | Outcome |
|---|---|---|
| 2026-08-12 | Phase 0 audit + Phase 1 stabilisation | 10 commits, 22 files, +3,284/−66, 96 tests. PR #1 opened. Two real bugs found in own code by own tests and fixed pre-commit. One audit finding (`face.png`) corrected after closer inspection. One Phase 3 security fix pulled forward because the Phase 1 fix was unsafe without it. |
