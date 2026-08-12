# VALENCE — Architecture

**Status:** target design. Sections marked *(current)* describe what exists
today; everything else is the destination. See [AUDIT.md](AUDIT.md) for the
detailed assessment of the current implementation and [ROADMAP.md](ROADMAP.md)
for the order of work.

VALENCE is a persistent, voice-first personal operating layer for Windows 11. It
is local-first: filesystem, application control, OS state, search indexes,
memory metadata, and logs stay on the machine. Cloud services are used where
they add capability that cannot be had locally — advanced reasoning, calendar
and mail APIs, web research — and never as a default conduit for local data.

---

## 1. Design principles

1. **One intelligence, many backends.** The user never needs to know whether an
   answer came from Gemini, a local model, the Windows API, or a cached index.
2. **State flows through events; the UI renders state.** Business logic never
   calls into a widget, and a widget never calls into a tool.
3. **Every side effect is a registered tool with a declared permission level.**
   The model chooses *which* tool; it never chooses whether the safety gate
   applies.
4. **Degrade, do not fail.** No provider, no network, no integration, and no
   microphone are each survivable states with a clear indication, not crashes.
5. **Refactor only where justified.** The upstream code contains real working
   behaviour. Structure is introduced where it removes duplication or closes a
   security hole, not to satisfy a diagram.

---

## 2. Target directory structure

The upstream layout is migrated toward this incrementally. Directories are
created **when the code that belongs in them exists**, never in advance.

```
valence/
├── app/                    # composition root, lifecycle, DI wiring
├── agent/
│   ├── orchestrator/       # intent → plan → execute → verify → respond
│   ├── planner/            # goal decomposition
│   ├── context/            # what the model is allowed to see this turn
│   └── execution/          # step runner, cancellation, verification
├── audio/
│   ├── wakeword/           # "Valence" / "Hey Valence"
│   ├── vad/                # local voice-activity detection
│   ├── stt/                # transcription providers
│   └── tts/                # synthesis providers, sentence streaming
├── intelligence/
│   ├── providers/          # Gemini, OpenRouter, OpenAI, Anthropic, local
│   ├── routing/            # task class → model selection
│   └── prompts/            # versioned prompt assets
├── tools/                  # the registry and its typed tools
│   ├── windows/  filesystem/  browser/  web/
│   ├── media/    productivity/  developer/
├── integrations/           # google/ gmail/ calendar/ spotify/ github/
├── memory/
│   ├── short_term/  long_term/  episodic/  retrieval/
├── security/
│   ├── permissions/        # risk levels and policy
│   ├── approvals/          # confirmation flow
│   ├── audit/              # structured action log
│   └── secrets/            # credential storage
├── platform/               # windows/ macos/ linux/
├── ui/                     # shell/ components/ views/ animations/
├── events/                 # event bus and event types
├── config/                 # typed settings
└── tests/
```

**Migration mapping.** Every current module has a destination. Nothing is
deleted without its behaviour being carried forward.

| Today | Destination | Treatment |
|---|---|---|
| `main.py` (`JarvisLive`) | `app/` + `agent/orchestrator/` | Split. Audio loop, tool dispatch, and session config separate. |
| `main.py` (`TOOL_DECLARATIONS`) | `tools/registry` | Replaced by typed declarations colocated with handlers. |
| `ui.py` (`MainWindow`, `HudCanvas`) | `ui/shell/`, `ui/components/` | Retained and restyled. Thread-safe signal pattern preserved. |
| `or_client.py` | `intelligence/providers/openrouter.py` | Retained; made lazy and injectable. |
| `actions/open_app.py` | `tools/windows/applications.py` | Rewritten — keystroke injection replaced (see §7). |
| `actions/file_controller.py` | `tools/filesystem/` | Retained; destructive ops gated. |
| `actions/computer_settings.py` | `tools/windows/system.py` + `platform/` | Split by OS; power actions gated. |
| `actions/browser_control.py` | `tools/browser/` | Retained. |
| `actions/web_search.py` | `tools/web/` | Retained; dead handler fixed. |
| `actions/screen_processor.py` | `tools/windows/vision.py` | Retained; capture indicator added. |
| `actions/file_processor.py` | `tools/filesystem/documents.py` | Retained; 832 lines to be split by format. |
| `actions/code_helper.py`, `dev_agent.py` | `tools/developer/` | Retained; execution gated. |
| `actions/game_updater.py`, `flight_finder.py`, `youtube_video.py`, `send_message.py` | `tools/` leaves | Retained as-is. Working, self-contained, low priority. |
| `agent/planner.py`, `executor.py`, `error_handler.py` | `agent/planner/`, `agent/execution/` | Retained; tool list generated from the registry instead of hard-coded prose. |
| `agent/task_queue.py` | `agent/execution/` | Retained. Sound design. |
| `memory/memory_manager.py` | `memory/long_term/` | Retained as the semantic layer; episodic and retrieval added alongside. |
| `config/__init__.py`, `memory/config_manager.py` | `config/` | Merged into one typed settings object. |
| `core/prompt.txt` | `intelligence/prompts/` | Rewritten for VALENCE identity. |
| — | `events/`, `security/`, `audio/wakeword/`, `tests/` | New. |

---

## 3. Event architecture

The bus is the seam between subsystems. Publishers do not know subscribers.

```
   audio ──┐                                    ┌──► ui (renders)
   agent ──┼──►  EventBus  ──► subscribers ──┼──► audit log
   tools ──┤                                    ├──► memory (episodic)
providers ─┘                                    └──► metrics
```

Event vocabulary:

```
LISTENING_STARTED        TOOL_STARTED            RESPONSE_CHUNK
WAKEWORD_DETECTED        TOOL_COMPLETED          SPEAKING_STARTED
SPEECH_DETECTED          TOOL_FAILED             SPEAKING_STOPPED
TRANSCRIPTION_PARTIAL    APPROVAL_REQUESTED      CANCELLED
TRANSCRIPTION_FINAL      APPROVAL_GRANTED        ERROR
THINKING_STARTED         APPROVAL_DENIED         PROVIDER_DEGRADED
PLANNING_STARTED                                 OFFLINE / ONLINE
```

Every event carries a correlation id for the turn that produced it, so the
activity view and the audit log can reconstruct a complete interaction.

**Why this is prerequisite work.** Barge-in, the activity history, the state
machine, and eventually splitting the UI into its own process all depend on
subsystems not calling each other directly. Today `_execute_tool` in `main.py`
calls `self.ui.set_state("THINKING")` inline — the agent owns UI state. That
coupling is what the bus removes.

---

## 4. VALENCE state machine

State is explicit and singular. Illegal combinations — `IDLE` while audio is
playing, `LISTENING` while muted — become unrepresentable.

```
                      ┌──────────► OFFLINE ◄──────────┐
                      │                                │
  IDLE ──wake──► LISTENING ──speech──► HEARING ──end──► THINKING
    ▲                 ▲                                     │
    │                 │                              ┌──────┴──────┐
    │                 │                              ▼             ▼
    │                 │                          PLANNING      RESPONDING
    │                 │                              │             │
    │                 │                              ▼             │
    │                 │                           ACTING           │
    │                 │                              │             │
    │                 │                    ┌─────────┴───────┐     │
    │                 │                    ▼                 ▼     ▼
    │                 └──── deny ─── WAITING_FOR_APPROVAL   SPEAKING
    │                                      │                  │
    └──────────────── timeout ─────────────┴──────────────────┘
                                                              │
                            any state ──failure──► ERROR ─────┘
```

*(current)* Today these are bare strings passed to `ui.set_state()` with no
transition rules and no `PLANNING`, `ACTING`, `WAITING_FOR_APPROVAL`, or
`OFFLINE` state at all.

---

## 5. Voice pipeline

```
 microphone
     │  16 kHz PCM
     ▼
 ┌─────────┐   always-on, local, cheap
 │ wakeword│   "Valence" / "Hey Valence"
 └────┬────┘
      │ activated ──────────────────────────► conversation session opens
      ▼                                        (no wake word needed for
 ┌─────────┐                                    follow-up turns until the
 │   VAD   │  local endpointing                 session idle-timeout)
 └────┬────┘
      ▼
 ┌─────────┐
 │   STT   │  streaming, partial + final
 └────┬────┘
      ▼
 ┌──────────────┐    ┌──────────┐    ┌──────────┐
 │ orchestrator │───►│  tools   │───►│ response │
 └──────────────┘    └──────────┘    └────┬─────┘
                                          │ token stream
                                          ▼
                                   ┌─────────────┐
                                   │  sentence   │  first complete sentence
                                   │  splitter   │  goes to TTS immediately
                                   └──────┬──────┘
                                          ▼
                                   ┌─────────────┐
                                   │     TTS     │──► speaker
                                   └─────────────┘
                                          ▲
                          barge-in ────────┘  user speech during playback
                                              cancels synthesis and the
                                              in-flight generation
```

**Modes:** always-listening · push-to-talk · keyboard-activated · muted ·
in-conversation. The microphone state is always visible in the UI.

**Barge-in requires a design change.** *(current)* The mic callback is gated by
`_is_speaking`, so while VALENCE talks the microphone is deliberately deaf.
That is the simplest possible echo suppression and it works, but it makes
interruption structurally impossible. The replacement keeps the mic open and
uses acoustic echo cancellation plus a VAD threshold to distinguish the user
from playback, cancelling synthesis on a confirmed user turn.

**Measurement before optimisation.** Wake-word latency, time to first
transcription, time to first token, and time to first audio are instrumented as
part of the pipeline, not estimated. No latency claim appears in documentation
without a recorded measurement behind it.

---

## 6. Intelligence layer

A provider is an interface, not an import.

```
                    ┌──────────────────┐
   task class ─────►│      Router      │  configuration-driven
                    └────────┬─────────┘
                             │
      ┌──────────┬───────────┼───────────┬──────────┐
      ▼          ▼           ▼           ▼          ▼
   Gemini   OpenRouter    OpenAI    Anthropic     Local
                                               (Ollama etc.)
```

| Task class | Wants | Falls back to |
|---|---|---|
| `conversation` | lowest latency, native audio | any text provider |
| `reasoning` | strongest planning model | conversation model |
| `vision` | multimodal | none — feature reports unavailable |
| `embedding` | cheap, local-preferred | none — semantic search degrades to metadata search |
| `private` | local model only | **never falls back to cloud** |

Providers are registered only when credentials exist. A provider with no key is
absent, not broken — `doctor` reports it and routing skips it. `private` is the
one class that must never silently escalate to a cloud provider; if no local
model is configured, the operation fails closed.

*(current)* Two SDKs are used directly with no abstraction: `google-genai` for
the Live session, and the retired `google-generativeai` package inside the
planner, executor, and error handler. Consolidating on `google-genai` is
Phase 3 work.

---

## 7. Tool execution pipeline

```
  model emits tool call
          │
          ▼
  ┌───────────────┐   name exists? arguments match schema?
  │   Registry    │   ── no ──► structured error back to the model
  └───────┬───────┘             (never a fallback to code execution)
          ▼
  ┌───────────────┐   LEVEL 0–1  ─────────────────────────┐
  │  Permission   │   LEVEL 2    ─► policy decides         │
  │     gate      │   LEVEL 3–4  ─► WAITING_FOR_APPROVAL   │
  └───────┬───────┘                    │                   │
          │                            ▼                   │
          │                     user confirms  ────────────┤
          │                     user denies ──► abort      │
          ▼                                                ▼
  ┌───────────────┐   timeout · cancellation · stdout/stderr capture
  │   Execution   │
  └───────┬───────┘
          ▼
  ┌───────────────┐
  │  Audit log    │   timestamp · request · tool · level · status ·
  └───────┬───────┘   duration · error · approval — never secrets
          ▼
   typed result ──► model ──► natural-language response
```

Each tool declares: name, description, parameter schema, **permission level**,
handler, timeout, error behaviour, and result schema. One declaration — the
model-facing schema is generated from it, so `main.py`'s `TOOL_DECLARATIONS`,
the `_execute_tool` dispatch chain, and the planner's hard-coded tool list
collapse into a single source of truth.

**The unknown-tool fallback is removed.** *(current)*
`agent/executor.py:250` responds to an unrecognised tool name by generating and
executing arbitrary Python. In the target, an unknown name is a validation
error returned to the model.

---

## 8. Security architecture

### Permission levels

| Level | Meaning | Examples | Default |
|---|---|---|---|
| **0** | Read-only | time, weather, list files, read calendar, system state | execute |
| **1** | Reversible | open app, play music, open URL, volume | execute |
| **2** | Modification | create folder, move file, create event, edit document | policy |
| **3** | Sensitive | send email, delete file, delete event, install software, kill process | **confirm** |
| **4** | Critical | destructive shell, credential changes, disk operations, financial | **confirm, or unavailable** |

The gate is one function. Tools declare their level; they do not implement their
own policy. *(current)* There is no gate at all — `shutdown`, `delete`, and
`send_message` execute on the model's word alone.

### Command safety

Arbitrary LLM-generated shell or Python execution is never implicit. Where it is
genuinely useful — `dev_agent`, `code_helper`, and the executor's
`generated_code` path — it runs behind: an allowlist of operations, argument
validation, dangerous-pattern rejection, a timeout, captured output, an audit
entry, and an approval prompt **that shows the code before it runs**.

`STOP VALENCE` — spoken, typed, or via a prominent UI Stop button — cancels the
in-flight tool workflow and any pending synthesis from any state.

### Secrets

Environment variables and the OS credential store; never source, never commit.
`.gitignore` and `.env.example` are in place. Windows Credential Manager
(via DPAPI) replaces plaintext `config/api_keys.json` in a later phase, with the
existing file kept readable for backward compatibility.

### Data boundaries

Screen and camera capture are explicit, indicated on screen while active, and
never continuous by default. The camera is disabled unless configured. Local
files are not uploaded to a cloud provider without a specific user-initiated
reason.

---

## 9. Memory architecture

```
  ┌─────────────────┐  current turn + recent turns, in process
  │  Working memory │  bounded, never persisted wholesale
  └────────┬────────┘
           │ selective promotion
           ▼
  ┌─────────────────┐  "we fixed this Git problem yesterday"
  │ Episodic memory │  timestamped interaction records
  └────────┬────────┘
           │ consolidation
           ▼
  ┌─────────────────┐  preferences, common folders, workflows,
  │ Semantic memory │  people, projects — stable facts
  └─────────────────┘
  ┌─────────────────┐  context bound to a repository or project
  │ Project memory  │
  └─────────────────┘
           │
           ▼
  ┌─────────────────┐  relevance scoring, recency weighting,
  │    Retrieval    │  metadata filters, optional embeddings
  └─────────────────┘
```

Every entry carries a timestamp, a source, and a confidence. Entries are
editable, deletable, and expirable. Memory is **selective** — not every
utterance is stored.

*(current)* Only the semantic layer exists, as a flat `long_term.json` with six
categories and a 2,200-character cap that discards the oldest entries when full.
The two-stage extraction gate (cheap relevance check before expensive
extraction) is a good design and is carried forward.

---

## 10. UI architecture

Not a chat window. A command environment that happens to include a transcript.

```
 ┌──────────────────────────────────────────────────────────────┐
 │  status bar — state · mic · provider · online/offline        │
 ├────────────┬────────────────────────────────┬────────────────┤
 │            │                                │                │
 │  system    │       central visualiser       │   transcript   │
 │  panel     │    (reacts to VALENCE state)   │   + activity   │
 │            │                                │                │
 │  schedule  │                                │   approvals    │
 │  tasks     │                                │   appear here  │
 │  media     │                                │                │
 ├────────────┴────────────────────────────────┴────────────────┤
 │  input · quick actions · STOP                                │
 └──────────────────────────────────────────────────────────────┘
```

**Modes:** Dashboard (full workspace) · Compact (small floating indicator) ·
Overlay (transparent layer over the desktop, hotkey-toggled).

**The visualiser reflects state, not decoration.** Idle is slow ambient motion;
listening is audio-reactive; thinking is a bounded processing animation; acting
indicates tool activity; speaking is output-reactive; error is a distinct,
subtle state.

**Rules.**

- The UI subscribes to events. It never calls a tool or a provider.
- Animation never blocks audio, inference, tools, or network. Heavy work stays
  off the UI thread. Repaints pause when the window is hidden.
- Raw chain-of-thought is never displayed. Concise execution summaries are.
- Progressive disclosure — panels appear when they have something to say.

**Visual identity is original.** *(current)* The interface is explicitly styled
as Marvel's J.A.R.V.I.S. — window title `J.A.R.V.I.S — MARK XXXIX`, the subtitle
"Just A Rather Very Intelligent System", and an arc-reactor HUD. VALENCE needs
its own identity: premium, minimal, high-contrast, calm, data-rich without
clutter. The upstream project's license and attribution are preserved
regardless (see §12).

---

## 11. Configuration

One typed settings object, sourced with clear precedence:

```
  defaults  ◄─  config file  ◄─  .env  ◄─  environment  ◄─  CLI flags
   (lowest)                                                  (highest)
```

Categories: `assistant` · `voice` · `models` · `privacy` · `permissions` ·
`memory` · `integrations` · `ui` · `logging` · `directories` · `developer`.

**Identity is configuration.** `assistant.name = "Valence"` lives in one place.
Renaming the assistant must never require touching application logic.
*(current)* The name is hard-coded across 19 files, including a tool literally
named `shutdown_jarvis`, and the honorific "sir" appears in 12 modules.

Backward compatibility: the existing `config/api_keys.json` remains a valid
source, so current installations keep working without reconfiguration.

---

## 12. Attribution

VALENCE is derived from [`FatihMakes/Mark-XXXIX-OR`](https://github.com/FatihMakes/Mark-XXXIX-OR),
licensed **Creative Commons BY-NC 4.0** (personal and non-commercial use only).
That license and its attribution are preserved. Renaming the assistant-facing
product to VALENCE does not remove or alter upstream authorship credit.
