# VALENCE — Intent and Purpose

*Why this project exists, what it is meant to become, and what it deliberately
is not.*

This is the document to read first. [ARCHITECTURE.md](ARCHITECTURE.md) says how,
[ROADMAP.md](ROADMAP.md) says in what order, [STATUS.md](STATUS.md) says where we
are. This one says **why**.

---

## 1. The thing being built

**VALENCE is a personal operating layer for a computer, driven by speech.**

Not a chatbot with a microphone bolted on. The distinction matters, and it
determines nearly every design decision that follows.

A chatbot receives text and returns text. Its world is the conversation. When you
ask it to open a file, it explains how to open a file.

An operating layer sits *between* the person and the machine. Its world is the
machine — the filesystem, the running applications, the calendar, the inbox, the
audio session, the screen. When you ask it to open a file, the file opens.

The target experience, stated plainly:

> You speak. The computer does the thing. You are not aware of which system did
> it.

When you say *"Valence, what am I doing tomorrow and do I have enough time to
study AI tonight?"*, something internally queries a calendar, reads the current
time, evaluates the gap, and forms an answer. You experience **one assistant**,
not an orchestration of Google Calendar, a clock, and a language model.

## 2. Why build it rather than use what exists

Existing assistants each give up something this project refuses to give up.

| | The gap |
|---|---|
| **Cloud assistants** (ChatGPT voice, Gemini Live) | Excellent conversation, no access to *your* machine. They cannot open your editor, find your file, or read your local project. |
| **OS assistants** (Cortana, Siri, Alexa) | Machine access, but shallow reasoning and a fixed, closed command vocabulary. |
| **Developer agents** (Claude Code, Copilot) | Deep reasoning and real machine access, but scoped to a repository and driven by typing. |

VALENCE is the intersection: **conversational depth, full machine access,
voice-first, and yours** — running on your hardware, under your rules, with your
data staying where you put it.

That intersection is why the project exists.

## 3. Principles

These are commitments, not aspirations. Where the code violates one, that is a
bug with a phase attached.

### Local-first

The filesystem, application control, OS state, command execution, caches,
indexes, memory metadata, and logs stay on the machine. Cloud services are used
where they add capability that genuinely cannot be had locally — advanced
reasoning, calendar and mail APIs, web research — and never as a default conduit
for local data.

Arbitrary local files are not uploaded to a model provider because it was
convenient.

### One intelligence, many backends

The user never needs to know whether an answer came from Gemini, a local model,
the Windows API, or a cached index. Providers are interchangeable and
configuration-driven. No single vendor is load-bearing.

### The model chooses the action, never the safety

A language model decides *which* tool to call. It never decides whether the
permission gate applies. Every side effect is a registered tool with a declared
risk level, and the gate is one function that all of them pass through.

This is the single most important principle in the project. The audit found the
upstream code executing model-written Python against the home directory with no
confirmation, reachable by a hallucinated tool name. That is precisely the class
of failure this principle exists to make structurally impossible.

### Degrade, do not fail

No provider, no network, no integration, and no microphone are each survivable
states with a clear indication — not crashes. A missing optional integration is
a normal condition, not a broken install.

### Do not claim what has not been run

No performance number appears without a measurement behind it. No feature is
described as working until it has been executed. Documentation states what was
verified *and what was not, and why*.

### Preserve what works

The upstream project contains real, working engineering. Structure is introduced
where it removes duplication or closes a security hole — never to satisfy a
diagram, and never by replacing a working implementation because another library
looks more fashionable.

## 4. What VALENCE is not

Naming the non-goals prevents scope drift more reliably than naming the goals.

- **Not a general-purpose autonomous agent.** It does not pursue objectives
  unattended. It responds, acts, reports, and stops.
- **Not a product.** It is a personal system, built for one machine and one
  person. No multi-tenancy, no accounts, no telemetry.
- **Not a cloud service.** Nothing is hosted. Nothing phones home.
- **Not a JARVIS clone.** The upstream project is styled as Marvel's J.A.R.V.I.S.
  VALENCE gets an original visual and verbal identity. The inspiration is
  acknowledged; the trade dress is not copied.
- **Not autonomous where it matters.** It will never send an email, complete a
  purchase, merge a pull request, or delete data on its own inference. Those
  require an explicit, informed yes.

## 5. The experience being aimed at

Three properties, in priority order.

**1. It responds.** Latency is a feature. A voice assistant that takes four
seconds to begin answering is not conversational, however good the answer is.
This drives streaming responses, sentence-level speech synthesis, barge-in, and
the requirement to instrument before optimising.

**2. It remembers, selectively.** *"What was I working on yesterday?"* should
work. *"We fixed this Git problem last week"* should be a thing it knows. But it
does not store every sentence forever — memory is curated, timestamped,
inspectable, and deletable.

**3. It is trustworthy.** The user knows what it did and can find out why. Every
action is logged. Sensitive actions are confirmed. Screen and camera capture are
visible while active. `STOP VALENCE` always works, from any state.

## 6. How this project is being built

The specification describes a very large system. It is being built in phases,
each with stated exit criteria, on a development branch, with `main` kept stable.

Three rules govern the work:

1. **Audit before modifying.** The first deliverable was an assessment of what
   the upstream code actually does — verified by execution — not a rewrite.
2. **A commit is one understandable change.** Small, coherent, conventionally
   named.
3. **No phase begins until the previous one is verified.** Exit criteria are
   recorded, met, and shown.

Current position: **Phases 0 and 1 complete.** See [STATUS.md](STATUS.md).

## 7. Attribution

VALENCE is derived from
[`FatihMakes/Mark-XXXIX-OR`](https://github.com/FatihMakes/Mark-XXXIX-OR),
licensed **Creative Commons BY-NC 4.0** — personal and non-commercial use only.
That license and its attribution are preserved in full. Renaming the
assistant-facing product does not remove upstream authorship credit, and this
project inherits the non-commercial restriction.
