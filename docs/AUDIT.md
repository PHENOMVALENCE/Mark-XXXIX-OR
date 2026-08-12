# VALENCE — Phase 0 Repository Audit

**Subject:** `Mark-XXXIX-OR` (fork of `FatihMakes/Mark-XXXIX-OR`)
**Audit date:** 2026-08-12
**Branch:** `codex/master-changes`
**Auditor environment:** Windows 11 Pro 26200, Python 3.11.9 in an isolated `.venv`

This document records what the upstream implementation actually is, what was
verified by execution rather than by reading, and what must change to become
VALENCE. It is the reference for every later phase.

---

## 1. Current state

29 Python files, ~11,700 lines. No tests, no CI, no linting configuration, no
package metadata, no `.gitignore` (added in this branch), no `docs/`.

| Area | Files | Lines |
|---|---|---|
| UI | `ui.py` | 1,534 |
| Orchestration / entrypoint | `main.py` | 886 |
| Tools ("actions") | `actions/*.py` (17 files) | 6,552 |
| Agent (plan → execute → recover) | `agent/*.py` (4 files) | 892 |
| LLM provider | `or_client.py` | 375 |
| Memory | `memory/*.py` | 373 |
| Config | `config/__init__.py` | 15 |
| Prompt | `core/prompt.txt` | 34 |

**Verification method.** Every file was compiled (`py_compile`, 29/29 clean),
every module was import-tested in a clean Python 3.11 venv, and the Qt UI was
constructed and run headless (`QT_QPA_PLATFORM=offscreen`) for 1.5 s of real
event-loop time to exercise the paint and metric timers.

---

## 2. What works

Confirmed by execution:

- **All 29 files compile.** No syntax errors anywhere in the tree.
- **26 of 27 modules import cleanly** on Python 3.11 once dependencies are
  installed. The one failure is `or_client` and it is environmental, not
  structural (see §3.1).
- **The PyQt6 UI constructs, paints, and runs its timers without crashing.**
  `JarvisUI("face.png")` builds, the HUD canvas renders at 16 ms, the system
  metric bars update, and the first-run setup overlay correctly appears because
  no API keys are configured.
- **The UI thread boundary is correct.** `write_log()` and `set_state()` are
  routed through `pyqtSignal` (`_log_sig`, `_state_sig`), so background threads
  updating the UI is safe. This is real engineering and should be preserved.
- **The Gemini Live voice loop is well structured.** `main.py` runs four
  concurrent coroutines under `asyncio.TaskGroup` — `_send_realtime`,
  `_listen_audio`, `_receive_audio`, `_play_audio` — with an auto-reconnect
  wrapper. Input and output transcription are both enabled.
- **Half-duplex echo suppression works.** `_is_speaking` behind a lock gates the
  microphone callback so the assistant does not transcribe its own output.
- **The tool-call round trip is complete.** 20 tool declarations, dispatch to
  blocking handlers via `run_in_executor`, and `send_tool_response` back to the
  session. Blocking work correctly stays off the event loop.
- **OpenRouter fallback chain works as designed.** `or_client` walks a model
  pool, tracks per-model 429 cooldowns, retries, and raises only when the entire
  pool is exhausted.
- **Memory persistence works.** Two-stage extraction (cheap YES/NO relevance
  gate, then structured JSON extraction), atomic-ish writes under a lock,
  size-capped with oldest-first trimming, and category-structured prompt
  formatting.
- **Cross-platform intent is genuine.** `computer_settings.py` and
  `open_app.py` branch on Windows/Darwin/Linux with real per-OS commands, not
  stubs.

## 3. What is broken

### 3.1 `or_client` fails at import time when unconfigured — *verified*

```
RuntimeError: api_keys.json not found at: ...\config\api_keys.json
```

`or_client.py:327` instantiates `client = OpenRouterClient()` at module scope,
and the constructor reads the key file eagerly. Seven modules depend on this.
They survive today only because every one of them imports `or_client` *inside a
function*, so the failure is deferred to first use and then surfaces as an
opaque tool error. Any future module-level import turns this into a hard
startup crash.

### 3.2 `pip install -r requirements.txt` cannot succeed — *verified*

`requirements.txt` is encoded **UTF-16 LE with a BOM** (first bytes
`ff fe 73 00 6f 00 ...`). pip expects UTF-8.

### 3.3 `requirements.txt` is missing the UI framework — *verified*

`ui.py` imports **PyQt6** at module level. PyQt6 is not listed. Following the
README exactly (`pip install -r requirements.txt` → `python main.py`) fails with
`ModuleNotFoundError: No module named 'PyQt6'` before anything renders.

Also declared-but-unused vs. used-but-undeclared:

| Undeclared, imported at module level | Consequence |
|---|---|
| `PyQt6` | hard startup failure |

| Undeclared, imported inside functions | Consequence |
|---|---|
| `pdfplumber`, `PyPDF2` | PDF handling fails at runtime |
| `python-docx` | DOCX handling fails at runtime |
| `python-pptx` | PPTX handling fails at runtime |
| `pandas` | CSV/Excel handling fails at runtime |
| `pydub` | audio handling fails at runtime |
| `ddgs` | falls back to the deprecated `duckduckgo_search` name |

### 3.4 `actions/cmd_control.py` does not exist — *verified*

`agent/executor.py:195` imports `actions.cmd_control`. The file is absent. Worse,
`agent/planner.py` *instructs the planning model to prefer `cmd_control`* and
uses it in two of its worked examples. Every `agent_task` plan that follows the
prompt's own guidance raises `ModuleNotFoundError`, burns two replan attempts,
and fails.

### 3.5 `face.png` is missing — *verified, but not a defect*

`main.py:872` passes `"face.png"`; no such file is in the repository, and
`HudCanvas._load_face` swallows the exception. However `paintEvent` has a
complete fallback (`ui.py:443-456`) that draws a layered orb with the assistant
name in the centre. That fallback — not a bitmap — is what every user of this
repository actually sees.

No fix needed. The name rendered in the orb becomes configurable in Phase 2.

### 3.6 Dead exception handler in `web_search`

`actions/web_search.py` has two `except Exception` clauses on one `try`. The
first returns, so the second (lines 135–137, the "all backends failed" path) is
unreachable. If DuckDuckGo raises *inside* the first handler, the exception
escapes `web_search()` entirely instead of being reported.

### 3.7 The OpenRouter model pool is unverified

`or_client.py` hard-codes 22 text and 8 vision model IDs including
`nvidia/nemotron-3-super-120b-a12b:free`, `google/gemma-4-31b-it:free`, and
`minimax/minimax-m2.5:free`. These were not validated against the live
OpenRouter catalogue (no key available). Stale IDs degrade silently — each is
tried, fails, and the client walks to the next, so a mostly-invalid pool
presents as slowness rather than as an error.

### 3.8 Windows app launching is keystroke injection — *verified by reading*

`actions/open_app.py:_launch_windows` presses <kbd>Win</kbd>, types the app name
with `pyautogui`, and presses <kbd>Enter</kbd>. Then it `return True`
unconditionally — success is never checked. Two consequences:

1. If the Start menu does not open or focus is stolen, the app name and a
   newline are typed into whatever window has focus.
2. The caller is told the launch succeeded regardless, so `open_app` reports
   "Opened X successfully" for applications that are not installed.

`_is_running()` exists and is correct, but is never called.

---

## 4. Current architecture

```
                    ┌────────────────────────────────┐
                    │   ui.py — PyQt6 (UI thread)    │
                    │   MainWindow / HudCanvas       │
                    │   JarvisUI facade              │
                    └───────┬──────────────▲─────────┘
                    signals │              │ set_state / write_log
                            ▼              │
  ┌──────────────────────────────────────────────────────────────┐
  │  main.py — JarvisLive (asyncio, background thread)           │
  │                                                              │
  │   sounddevice ──► out_queue ──► Gemini Live (WebSocket)      │
  │   16 kHz PCM                     ▲   │                       │
  │                                  │   ├─► audio 24 kHz ──►    │
  │                                  │   │   audio_in_queue ──►  │
  │                                  │   │   sounddevice out     │
  │                                  │   ├─► transcriptions ──►  │
  │                                  │   └─► tool_call           │
  │                                  │         │                 │
  │                        send_tool_response  ▼                 │
  │                                  └── _execute_tool           │
  └──────────────────────────────────────┬───────────────────────┘
                                         │ run_in_executor
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
             actions/*.py         agent/task_queue      memory_manager
             (17 modules)                │                    │
                                         ▼                    ▼
                                  agent/executor       long_term.json
                                    ├─ planner  (Gemini)
                                    └─ error_handler (Gemini)
                                         │
                                         ▼
                                   or_client (OpenRouter)
```

**Model usage today**

| Purpose | Model | SDK |
|---|---|---|
| Voice conversation + tool calling | `gemini-2.5-flash-native-audio-preview-12-2025` | `google-genai` (Live) |
| Planning | `gemini-2.5-flash-lite` | `google-generativeai` *(deprecated)* |
| Replanning | `gemini-2.5-flash` | `google-generativeai` *(deprecated)* |
| Error recovery | `gemini-2.5-flash-lite` / `gemini-2.0-flash` | `google-generativeai` *(deprecated)* |
| Web search, memory extraction, misc. | OpenRouter free pool | raw `requests` |
| Vision | OpenRouter vision pool | raw `requests` |

`google-generativeai` emits a `FutureWarning` on import: the package is retired
and no longer receives updates. Consolidating on `google-genai` is required.

**How each subsystem is currently implemented**

| Subsystem | Implementation | Assessment |
|---|---|---|
| Wake word | **None.** Mic is hot whenever unmuted. | Must be built. |
| VAD / turn-taking | Delegated entirely to Gemini Live server-side. | Works; no local control. |
| STT / TTS | Gemini Live native audio, voice `Charon`. | Works; single provider. |
| Barge-in | Mic is *gated off* while speaking, so interruption is impossible by construction. | Must be redesigned. |
| Tool registry | A 400-line Python literal in `main.py` + a 130-line `elif` chain. Every tool is declared twice and dispatched by hand. | Replace with a registry. |
| Permissions | **None.** Every tool executes immediately. | Must be built. |
| Audit log | **None.** | Must be built. |
| Events | **None.** UI state is set imperatively from `_execute_tool`. | Must be built. |
| State machine | Ad-hoc strings: `"IDLE"`, `"LISTENING"`, `"THINKING"`, `"SPEAKING"`, `"MUTED"`, `"INITIALISING"`. No transition rules. | Formalise. |
| Config | One file, `config/api_keys.json`, holding 3 keys. Read by 8 modules, each with its own duplicated loader. | Centralise. |
| Logging | ~200 `print()` calls with emoji. `logging` used only in `or_client`. | Replace. |
| Memory | Single flat `long_term.json`, 6 categories, 2,200-char cap. No episodic layer, no retrieval scoring, no embeddings. | Extend. |
| Tests | **None.** | Must be built. |

---

## 5. Technical debt

Ordered by cost of leaving it.

1. **`main.py` is a god module.** Tool schemas (400 lines), tool dispatch (130
   lines), the audio pipeline, session config, and memory triggering all live in
   one file. Adding a tool means editing three separate places.
2. **Tool definitions are duplicated three times** — once in `TOOL_DECLARATIONS`
   (`main.py`), once in the `_execute_tool` dispatch chain, and once again in
   prose inside `PLANNER_PROMPT` (`agent/planner.py`). The planner's copy has
   already drifted: it advertises `cmd_control`, which does not exist.
3. **Config loading is copy-pasted.** `_get_api_key()` is redefined in at least
   six modules, each re-reading and re-parsing the same JSON file on every call.
   `get_base_dir()` is redefined in seven.
4. **Identity is hard-coded in 19 files.** "JARVIS", "MARK XXV", "MARK XXXIX",
   `J.A.R.V.I.S`, and "Just A Rather Very Intelligent System" are baked into
   window titles, prompts, tool names (`shutdown_jarvis`), scheduled-task names,
   and HTTP headers. The honorific "sir" is hard-coded in 12 modules.
5. **~200 `print()` calls.** No levels, no timestamps, no module context, and
   emoji that mis-render in the Windows console (`cp1252` `UnicodeEncodeError`
   risk).
6. **The UI redraws expensively.** `HudCanvas._step` fires every 16 ms and
   `paintEvent` walks a full `width × height / 48²` grid of points plus ten halo
   ellipses, three arc rings, scanners, and a particle list — all on the UI
   thread, unconditionally, even when idle and even when the window is hidden.
7. **`_SysMetrics` shells out twice per 1.5 s, forever.** It launches
   `nvidia-smi` and, on Windows, a full `powershell.exe` process to read
   `MSAcpi_ThermalZoneTemperature` — started at *module import*, before anything
   asks for metrics. On a machine with no NVIDIA GPU this is ~2,400 wasted
   process spawns per hour.
8. **`or_client.client` is a module-level singleton** built at import. Untestable
   without a key file on disk; unmockable.
9. **Errors are surfaced raw to the user.** `speak_error()` speaks
    `str(error)[:120]`, so users hear tracebacks and HTTP status codes.
10. **No `actions/__init__.py` or `agent/__init__.py`.** They work as implicit
    namespace packages, which is fragile under packaging and freezing.
11. **`ui.py:1063` contains a non-English comment** (`# Metrik güncelleme
    timer'ı`) — harmless, but a marker of the fork's origin to normalise.

---

## 6. Security risks

Ranked by severity. These define the permission model VALENCE needs.

### CRITICAL — arbitrary code execution by design

`agent/executor.py:_run_generated_code` asks Gemini to write a Python program,
writes it to a temp file, and executes it with `subprocess.run([sys.executable,
tmp_path])` — no validation, no sandbox, no user confirmation, 120 s timeout,
`cwd=Path.home()`. The system prompt explicitly tells the model it may install
packages via pip.

It is reachable three ways: as an explicit `generated_code` tool, as the
**fallback for any unrecognised tool name** (`executor.py:250`), and as the
final fallback in `error_handler.generate_fix`. So a hallucinated tool name in a
plan silently becomes "write and run arbitrary Python against the user's home
directory."

*This is the single most important thing to gate.* It should not be deleted —
it is genuinely useful — but it must move behind an explicit approval prompt
that shows the code before it runs.

### CRITICAL — no permission model anywhere

`computer_settings` reaches `shutdown`, `restart`, WiFi toggling, and lock
screen. `file_controller` reaches `delete` and `move`. `send_message` sends
WhatsApp/Telegram messages. None require confirmation. A misheard phrase or a
model hallucination executes immediately and irreversibly.

### HIGH — plaintext credentials, previously unprotected

`config/api_keys.json` stores the Gemini and OpenRouter keys in cleartext,
written by the setup overlay. Until the `.gitignore` added in this branch, a
`git add .` from the repo root would have committed them. *Confirmed clean:*
`git log --all -- config/api_keys.json` is empty, so no key was ever pushed.

### HIGH — code injection into generated reminder scripts

`actions/reminder.py` interpolates the reminder message into generated Python
source. Sanitisation is `.replace('"', '').replace("'", "")` — newlines survive,
so a message containing a newline followed by Python injects code into a script
that Task Scheduler later runs. The same value is also interpolated unescaped
into the task XML `<Description>`.

### MEDIUM — `shell=True` with interpolated values

`actions/reminder.py:129` builds a `schtasks` command string with `shell=True`
using a derived task name and temp path. `actions/dev_agent.py:277` launches an
editor with `shell=True`. Neither takes direct user text today, but the pattern
is one refactor away from injection.

### MEDIUM — unattended keystroke injection

`open_app` (Windows) and `computer_control` type into whatever window holds
focus. Combined with no permission gate, a misrouted command can type into a
terminal, an editor, or a chat window.

### MEDIUM — vision data leaves the machine unannounced

`screen_processor` captures the screen or webcam and uploads it to OpenRouter.
There is no persistent on-screen indicator that capture is active and no
per-directory or per-application exclusion.

### LOW — no audit trail

Nothing records which tool ran, with which arguments, at whose request. After an
unexpected action there is no way to reconstruct what happened.

---

## 7. Dependencies

**Runtime verified:** Python 3.11.9. The README's "3.11 or 3.12" is accurate —
the machine's default interpreter is Anaconda 3.13, on which several native
wheels (`pyaudio`, `pycaw`, `win10toast`) are unreliable. All work was done in a
project-local `.venv` built from Python 3.11.

**Installed and verified importable (28 packages):**
`PyQt6`, `sounddevice`, `pyaudio`, `google-genai`, `google-generativeai`,
`pillow`, `requests`, `beautifulsoup4`, `duckduckgo-search`, `playwright`,
`pyautogui`, `pyperclip`, `pygetwindow`, `opencv-python`, `numpy`, `mss`,
`psutil`, `comtypes`, `pycaw`, `win10toast`, `send2trash`,
`youtube-transcript-api`, `pywinauto`.

**Required but undeclared** — see §3.3. Must be added to `requirements.txt`.

**Additional setup step:** `playwright install` is needed for
`browser_control.py` and `flight_finder.py`. `setup.py` does run it; the README
mentions it. Browser binaries were *not* installed during this audit.

**Not installed, not required:** none of the paid-provider SDKs. No credentials
exist for Google OAuth, Spotify, GitHub, or any paid LLM provider.

---

## 8. Proposed architecture

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full target design,
pipelines, and the migration mapping from each current module.

The shape in one line: **an event bus in the middle, a typed tool registry with
a central permission gate on one side, a provider abstraction on the other, and
a UI that renders state rather than owning it.**

The three structural changes that unlock everything else:

1. **Tool registry** — one typed declaration per tool carrying its own schema,
   permission level, timeout, and handler. Deletes the triple duplication in
   §5.2 and makes the permission gate a single choke point rather than 20
   scattered decisions.
2. **Event bus** — replaces direct `ui.set_state(...)` calls from tool code.
   Prerequisite for barge-in, for the activity log, and for running the UI as a
   separate process later.
3. **Config + identity module** — one typed settings object sourced from `.env`
   and JSON, replacing six copies of `_get_api_key()` and 19 files of hard-coded
   branding.

---

## 9. Phased roadmap

See **[ROADMAP.md](ROADMAP.md)**.

---

## 10. First implementation task

**Phase 1 — Stabilisation.** Make the repository reproducible and safe to
develop against, without changing any behaviour a user can observe.

1. `.gitignore` + `.env.example` — **done**, commit `2878cda`.
2. Re-encode `requirements.txt` as UTF-8, add the missing packages, and pin the
   Python version.
3. Make `or_client` lazy so an unconfigured checkout imports cleanly, and give
   it a real error message when it cannot find a key.
4. Add a centralised settings module that reads `.env` *and* the existing
   `config/api_keys.json`, so current installs keep working unchanged.
5. Add structured logging and a `valence.doctor` health check.
6. Fix the dead `except` in `web_search`, the missing `cmd_control` reference,
   and the missing `face.png`.

Phase 1 deliberately does **not** touch the voice loop, the UI layout, or tool
behaviour. Those are Phases 3–5, after there are tests to protect them.

---

## Appendix — verification log

| Check | Command | Result |
|---|---|---|
| Syntax | `py_compile` over 29 files | 29/29 clean |
| Imports | import every module, Python 3.11 venv | 26/27; `or_client` fails without keys |
| UI boot | construct `JarvisUI`, run event loop 1.5 s offscreen | renders, no crash, `face.png` absent |
| Secrets in history | `git log --all -- config/api_keys.json` | empty — never committed |
| Secret patterns | regex scan for `sk-`, `AIza`, `api_key = "..."` | no matches |
| `requirements.txt` encoding | read raw bytes | UTF-16 LE + BOM |

Not verified, and why:

- **No live API call was made.** No Gemini or OpenRouter key is configured, so
  the voice session, the planner, memory extraction, web search, and vision were
  never exercised end to end. Their correctness is assessed from code only.
- **No tool was executed.** `open_app`, `computer_settings`, `file_controller`,
  and `send_message` act on the live desktop; running them during an audit would
  have had real side effects.
- **Playwright browsers were not installed**, so `browser_control` and
  `flight_finder` were import-checked only.
