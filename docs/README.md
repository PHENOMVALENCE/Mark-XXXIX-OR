# VALENCE — Documentation

VALENCE is a voice-first personal operating layer for Windows 11, built
progressively from the [Mark-XXXIX-OR](https://github.com/FatihMakes/Mark-XXXIX-OR)
project (CC BY-NC 4.0, attribution preserved).

## Start here

| Document | Answers |
|---|---|
| **[VISION.md](VISION.md)** | **Why** — what VALENCE is for, what it refuses to be, the principles that decide arguments |
| **[STATUS.md](STATUS.md)** | **Where we are** — what is done with evidence, what remains, what to do next |
| [ARCHITECTURE.md](ARCHITECTURE.md) | **How** — target design, pipelines, permission model, per-module migration mapping |
| [ROADMAP.md](ROADMAP.md) | **In what order** — phases with exit criteria, and what is blocked on credentials |
| [AUDIT.md](AUDIT.md) | **What we started with** — the Phase 0 assessment of the upstream code |

New to the project? Read VISION, then STATUS. That is enough to be useful.
Picking up work? STATUS §6 says exactly where to resume.

## Current position

**Phases 0 and 1 complete.** Audit done, install path repaired, secrets
protected, configuration and logging layers built, `valence.doctor` added, worst
security hole closed. 96 tests passing.

**Blocked on:** a Gemini API key. Nothing has been verified against a live API
yet — see [STATUS.md §2](STATUS.md).

## Running it

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\playwright install
cp .env.example .env
```

Add your API keys to `.env`, then check the environment:

```bash
python -m valence.doctor
```

Start the assistant:

```bash
python main.py
```

Run the tests:

```bash
pytest
```

Python 3.11 or 3.12. Native wheels for `pyaudio`, `pycaw`, and `win10toast` are
unreliable on 3.13+.

## Working agreements

- All work happens on `codex/master-changes`. `main` stays stable.
- A commit is one understandable change, conventionally named.
- No phase begins until the previous one's exit criteria are met and shown.
- Nothing is described as working until it has been run. Documentation states
  what was verified **and what was not, and why**.
- Upstream license and attribution are preserved in every change.
