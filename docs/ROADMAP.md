# VALENCE — Implementation Roadmap

Derived from the [Phase 0 audit](AUDIT.md), targeting the design in
[ARCHITECTURE.md](ARCHITECTURE.md).

**Working rules.**

- All work happens on `codex/master-changes`. `main` stays stable.
- Small, coherent commits with conventional prefixes. One understandable change
  each.
- No phase begins until the previous one is verified.
- Working upstream behaviour is preserved unless there is a stated reason to
  change it.
- Nothing is claimed to work until it has been run.

**Legend:** ✅ done · 🔨 in progress · ⬜ not started · 🔑 blocked on credentials

---

## Phase 0 — Audit ✅

| | Task |
|---|---|
| ✅ | Inspect every module, map the architecture |
| ✅ | Compile-check (29/29) and import-check (26/27) in a clean Python 3.11 venv |
| ✅ | Boot the UI headless and exercise its timers |
| ✅ | Confirm no secrets in git history |
| ✅ | Document findings — `docs/AUDIT.md` |
| ✅ | Produce target architecture — `docs/ARCHITECTURE.md` |

---

## Phase 1 — Stabilisation ✅

*Make the repository reproducible and safe to develop against. No user-visible
behaviour changes.*

| | Task | Addresses |
|---|---|---|
| ✅ | `.gitignore` + `.env.example` | Audit §6 HIGH |
| ✅ | Re-encode `requirements.txt` as UTF-8; add PyQt6 and the six undeclared runtime packages; document Python 3.11/3.12 | §3.2, §3.3 |
| ✅ | Make `or_client` lazy — no import-time key read, actionable error when unconfigured | §3.1 |
| ✅ | Centralised typed settings reading `.env` **and** the existing `config/api_keys.json` | §5.3 |
| ✅ | Structured logging (`DEBUG`/`INFO`/`WARNING`/`ERROR`) replacing `print()`, secrets redacted | §5.5 |
| ✅ | `valence.doctor` — Python version, dependencies, microphone, speaker, providers, storage, integrations, with actionable fixes | Spec §46 |
| ✅ | Fix the dead `except` in `web_search`; remove the `cmd_control` reference | §3.4, §3.6 |
| ✅ | `actions/__init__.py`, `agent/__init__.py` | §5.10 |
| ✅ | Tests: settings resolution, logging redaction, doctor, executor dispatch | Spec §45 |

Two items were reassessed during the work:

- **`face.png` needs no fix.** `paintEvent` has a complete fallback that draws
  the orb every user actually sees. The audit entry is corrected.
- **Removing the `cmd_control` reference alone would have made things worse.**
  It would have routed those calls into the executor's unknown-tool fallback,
  which executes unvalidated LLM-generated Python. That fallback was removed in
  the same commit — pulled forward from Phase 3 because the Phase 1 fix was
  unsafe without it.

**Exit criteria — met.**

| Criterion | Result |
|---|---|
| `pip install -r requirements.txt` resolves | verified in a clean Python 3.11 venv |
| `python main.py` starts | **connects to the Live session in 1.6 s, microphone open at 16 kHz** |
| `python -m valence.doctor` reports accurately | 12 ok, 2 warnings, 0 failures |
| Every module imports on an unconfigured checkout | 27/27, was 26/27 |
| Tests pass | 120/120, via both `pytest` and `python -m pytest` |

### Phase 1 addendum — live verification (2026-08-13)

Configuring real keys exposed failures invisible to static analysis, fixed in
[PR #2](https://github.com/PHENOMVALENCE/Mark-XXXIX-OR/pull/2):

| | Task | Addresses |
|---|---|---|
| ✅ | `valence.models` — every model ID in one verified registry, selected by role | Audit §3.7 |
| ✅ | Replace the retired Gemini 2.5 family, which had broken the entire agent subsystem | Audit §3.7 |
| ✅ | Rebuild the OpenRouter pools from the live catalogue, ordered by measured latency | Audit §3.7 |
| ✅ | `valence.verify` — live provider check that opens a real Live session | Spec §46 |
| ✅ | `harden_console()` — an emoji `print()` was killing the voice thread on first connect | §5.5 |
| ✅ | Route nine modules through settings so `.env` installs actually work | §5.3 |
| ✅ | Redact the current `AQ.` Gemini key format | §6 HIGH |

---

## Phase 2 — VALENCE identity ⬜

*Replace Mark/JARVIS branding with configurable identity. Upstream license and
attribution preserved.*

| | Task |
|---|---|
| ⬜ | `assistant.name = "Valence"` in central config; all user-facing text reads from it |
| ⬜ | Rewrite `core/prompt.txt` for VALENCE — voice, tone, tool discipline |
| ⬜ | Window title, header, setup overlay, log prefixes |
| ⬜ | Rename `shutdown_jarvis` → `shutdown_assistant`; retain the old name as an alias for one release |
| ⬜ | Configurable honorific replacing hard-coded "sir" in 12 modules |
| ⬜ | Normalise `MARKReminder_*` task names and the `X-Title: MARK XXV` HTTP header |
| ⬜ | Update `readme.md`; keep CC BY-NC 4.0 and upstream credit |

**Exit criteria.** Changing one config value renames the assistant everywhere.
No Marvel-derived naming remains in user-facing text.

---

## Phase 3 — Core refactor ⬜

*Extract the seams. Incremental — the application runs after every commit.*

| | Task | Addresses |
|---|---|---|
| ⬜ | Event bus + event types; UI subscribes instead of being called | §5, Arch §3 |
| ⬜ | Explicit state machine with legal transitions | Arch §4 |
| ⬜ | **Tool registry** — one typed declaration per tool; model schema generated from it | §5.2 |
| ⬜ | **Permission model** — levels 0–4, one central gate, approval flow | §6 CRITICAL |
| ⬜ | Gate `generated_code`; remove the unknown-tool → code-execution fallback | §6 CRITICAL |
| ⬜ | Structured audit log + Activity History view | §6 LOW |
| 🟡 | Provider abstraction; consolidate onto `google-genai`, retire `google-generativeai` | §4 — `valence.models` centralises IDs; the provider interface itself is still absent |
| ⬜ | Fix reminder script injection; remove `shell=True` where avoidable | §6 HIGH/MEDIUM |
| ⬜ | Tests: permission logic, tool schemas, command validation, provider routing |

**Exit criteria.** Every side-effecting tool passes the gate. Level 3–4 actions
prompt. No path reaches code execution without approval. Permission tests pass.

---

## Phase 4 — Voice quality ⬜

| | Task |
|---|---|
| ⬜ | Wake-word engine — "Valence" / "Hey Valence", modular, decoupled from STT |
| ⬜ | Activation modes: always-listening, push-to-talk, keyboard, muted, conversation |
| ⬜ | Conversation sessions — no wake word for follow-ups; configurable idle timeout |
| ⬜ | Local VAD |
| ⬜ | **Barge-in** — keep the mic open during playback with echo cancellation, cancel synthesis on a confirmed user turn |
| ⬜ | Sentence-level streaming TTS |
| ⬜ | Latency instrumentation: wake word, first transcription, first token, first audio |

**Exit criteria.** Multi-turn conversation without repeating the wake word.
Interruption works. Measured latencies recorded — no claim without a number.

---

## Phase 5 — Windows foundation ⬜

| | Task | Addresses |
|---|---|---|
| ⬜ | **Rewrite `open_app` for Windows** — Start-menu shortcut index, `App Paths` registry, `AppsFolder` for UWP; no keystroke injection; verify the process actually started | §3.8 |
| ⬜ | Close / focus / switch / minimize / maximize / restore |
| ⬜ | Filesystem: open, create, rename, move, copy, metadata, recursive search, recent files — destructive ops gated |
| ⬜ | System: volume, mute, brightness, clipboard, screenshot, processes, battery, storage, network |
| ⬜ | Media control separated from shell execution — Windows media sessions first |
| ⬜ | Tests for filesystem and command validation |

**Exit criteria.** "Valence, open VS Code" launches it and confirms it launched,
without typing into the focused window.

---

## Phase 6+ — Capability expansion ⬜

Order per the specification, adjusted only where the codebase justifies it.

| Phase | Scope | Notes |
|---|---|---|
| 6 | Memory layers — episodic, project, retrieval scoring | Local |
| 7 | UI redesign — dashboard, compact, overlay, VALENCE visualiser | Original identity |
| 8 | Web research — query → search → read → synthesise, sources preserved | Separate from browser automation |
| 9 | File intelligence — indexing, semantic search, document Q&A | Include/exclude directory policy |
| 10 | 🔑 Google Calendar — OAuth | Needs Cloud project + consent screen |
| 11 | 🔑 Gmail — OAuth. Send is always intent → draft → approval → send | Never auto-send |
| 12 | 🔑 Spotify + media | Needs developer app registration |
| 13 | Vision — screen understanding with a visible capture indicator; camera off by default | |
| 14 | Developer tools — repos, git status, tests, dev servers, log summarising | Execution gated |
| 15 | 🔑 GitHub — repos, PRs, issues, CI. Never auto-merge | Needs token |
| 16 | Daily briefing, task system, background service, setup wizard | |

---

## What is blocked on you

**Nothing.** Gemini and OpenRouter keys are configured and verified working, so
Phases 2–9 can all proceed.

These require your action before the corresponding phase can start:

| Needed | For | Where to get it |
|---|---|---|
| Google Cloud project + OAuth client (Calendar, Gmail scopes) + consent screen | Phases 10–11 | https://console.cloud.google.com |
| Spotify developer app (client id, secret, redirect URI) | Phase 12 | https://developer.spotify.com/dashboard |
| GitHub personal access token | Phase 15 | GitHub → Settings → Developer settings |

Put them in `.env` (copy `.env.example`). `.env` is git-ignored. Existing
`config/api_keys.json` installations keep working — Phase 1 settings reads both.

**Re-run `python -m valence.verify --models` whenever something starts failing
for no visible reason.** Providers retire models on their own schedule; that is
exactly how 15 of the 17 IDs in this repository went dead without anything
noticing.

**Decisions I will not make for you.** Which directories VALENCE may index and
which are excluded; whether level-2 actions require confirmation; whether the
camera is ever enabled; whether a local model is installed for the `private`
task class. Each gets a documented default that errs toward the restrictive
option, changeable in config.
