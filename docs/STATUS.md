# VALENCE — Project Status

**Last updated:** 2026-08-13
**Branch:** `codex/master-changes`
**Open PR:** [#1 — Phase 0-1: repository audit, secret protection, and stabilisation](https://github.com/PHENOMVALENCE/Mark-XXXIX-OR/pull/1) *(open, not merged)*
**Position:** Phases 0 and 1 complete, plus live provider verification.
**The assistant runs.** Voice session confirmed working end to end.

This is the living ledger. It records what is done with the evidence for it,
what remains, and exactly where to resume. Update it at the end of every working
session.

---

## 1. Where things stand in one paragraph

The upstream Mark-XXXIX-OR fork has been audited by execution, its install path
repaired, its secrets protected, and its worst security hole closed. Keys are
now configured, and live verification found that **15 of the 17 hard-coded
model IDs in the tree were dead** — the entire Gemini 2.5 family 404s for newly
issued keys, which had silently broken the whole agent subsystem. Those are
replaced by a verified central registry. **The assistant now starts, connects,
and runs.** Nothing user-facing has changed yet: it still calls itself JARVIS
and still has no permission model.

---

## 2. Blocked on you

**Nothing.** Gemini and OpenRouter keys are configured and verified working.

> **Security note.** The keys pasted into chat on 2026-08-13 appeared in a
> transcript and in screenshots. Treat them as exposed and rotate both when
> convenient — revoke at
> [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and
> [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys), then
> update `.env`. Nothing in the repository holds a key; `.env` is git-ignored
> and was never committed.

Later phases need more credentials (Google OAuth for Calendar and Gmail,
Spotify app, GitHub token) but none of those block the next several phases.

### Two commands worth knowing

```bash
python -m valence.doctor
```

Offline, free, safe anywhere. Confirms a key is *present*.

```bash
python -m valence.verify --models
```

Makes real API calls. Confirms a key *works*, opens an actual Live voice
session, and validates every model ID against the live catalogue. This is what
found the 15 dead models. Worth re-running whenever something starts failing
for no visible reason.

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
| Vision, status ledger, documentation index | `a625f0b` |

### Live verification — 2026-08-13 ✅

Keys configured. Everything below was found by making real API calls, and
none of it was visible without them.

| Achievement | Commit |
|---|---|
| Current-format (`AQ.`) Gemini keys added to log redaction | `1ab71b1` |
| `harden_console()` — emoji `print()` no longer kills the voice thread | `1ab71b1` |
| `valence.models` — every model ID in one verified registry | `476d729` |
| `valence.verify` — live provider check, opens a real Live session | `476d729` |
| `.env` configuration actually reaches the app | `73611a1` |
| `main.py` converted from `print()` to structured logging | `73611a1` |

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
- **120 tests pass** under both `pytest` and `python -m pytest`

**With keys configured (2026-08-13):**

- **The voice loop runs.** `python main.py` connects to the Live session in
  1.6 s, opens the microphone at 16 kHz, and runs all four audio coroutines
  without error. First confirmed successful run of the assistant.
- **A real Live session returns audio and transcription** — verified
  independently in ~1.2 s.
- Gemini `fast` 1.1 s, `reasoning` 1.4 s, both callable.
- OpenRouter round trip **1.5 s, down from 56.6 s** — the old pool led with
  its slowest model on every call.
- Model pools **10/10 text and 5/5 vision valid**, was 6/22 and 4/8.
- `python -m valence.doctor` reports 12 ok, 2 warnings, 0 failures.

### What live verification found

Nothing here was visible without a key. It is the reason the "add a key first"
recommendation was worth following.

| Finding | Consequence |
|---|---|
| The entire **Gemini 2.5 family 404s** for newly issued keys | Planner, replanner, error recovery, code generation, document processing, and Gemini-backed search were **all broken**, reported only as generic tool errors |
| 16 of 22 OpenRouter text models, 4 of 8 vision models gone | Silent degradation to slowness, not an error |
| Pool led with its **slowest** model (24.7 s) | Every call paid it first |
| Vision pool listed **two text-only models** | Image requests sent to models that cannot accept images |
| Emoji `print()` in the reconnect loop | **`UnicodeEncodeError` killed the whole voice thread** on the first connection attempt whenever stdout was redirected |
| Nine modules read `config/api_keys.json` directly | A `.env`-only install — the documented path — left the UI stuck on the setup overlay forever |
| Redaction missed the `AQ.` key format | A current-format Gemini key would be written to `logs/valence.log` in plaintext |

### Still not verified — and why

- **No desktop-acting tool has been executed** — `open_app`,
  `computer_settings`, `file_controller`, `send_message` all have real side
  effects on the live machine.
- **No spoken conversation has been held.** The session connects and the
  microphone opens; nobody has talked to it yet. Tool calling over voice is
  therefore still unproven.
- **Playwright browser binaries are not installed**, so `browser_control` and
  `flight_finder` remain import-checked only. Run `playwright install`.

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
| 39 | Observability / structured logging | ✅ | 1 | `main.py` converted; ~180 `print()` remain in actions/agent |
| 44 | Centralised configuration | 🟡 | 1 | Settings object exists; UI/voice/permission categories not yet wired |
| 45 | Testing | 🟡 | 1 | 120 tests on new code; upstream modules untested |
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
| 8 | Multi-model provider abstraction | 🟡 | 3 | `valence.models` centralises IDs; provider interface still absent |
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

**Worth doing first, it is quick:** hold an actual spoken conversation with the
assistant and watch `logs/valence.log`. The session connects and the microphone
opens, but nobody has spoken to it yet, so voice-driven tool calling is still
unproven. Any failure there changes Phase 4's priorities.

```bash
playwright install     # unblocks browser_control and flight_finder
python main.py         # then talk to it
```

---

## 7. Session log

| Date | Session | Outcome |
|---|---|---|
| 2026-08-12 | Phase 0 audit + Phase 1 stabilisation | 10 commits, 22 files, +3,284/−66, 96 tests. PR #1 opened. Two real bugs found in own code by own tests and fixed pre-commit. One audit finding (`face.png`) corrected after closer inspection. One Phase 3 security fix pulled forward because the Phase 1 fix was unsafe without it. |
| 2026-08-13 | Live provider verification | Keys configured. Found 15 of 17 model IDs dead, a crash that killed the voice thread, a redaction gap for current-format Gemini keys, and nine modules bypassing the settings layer. Added `valence.models` and `valence.verify`. **First confirmed run of the assistant.** OpenRouter 56.6 s → 1.5 s. 3 commits, 120 tests. |
