# BRAM Specification

Butler, Reconnaissance & Automation Manager

Status: **APPROVED 2026-11-24**. Subject to [HARD_RULES.md](HARD_RULES.md).

## 1. What BRAM is

A self-hosted Home Assistant agent that anyone can install. It answers and controls (Butler), watches (Reconnaissance), and learns. Its defining trait: **it reaches out to people**, rather than only replying.

BRAM is original work. Other projects may inform its feature list, but their code is not copied. Nothing about a particular house, person, or device is hard-coded.

## 2. Architecture

```
House A: HA + BRAM integration ─┐
House B: HA + BRAM integration ─┼── BRAM Server ── model provider (owner's choice)
Open WebUI / other tools ───────┘        │
                                         └── direct push (ntfy first), not through HA
```

| Part | Runs | Responsibilities |
|---|---|---|
| **BRAM integration** | Inside each HA; installed by HACS | Event feed, gate, approvals, Assist conversation agent, HA delivery, critical alerts, off switch, config UI |
| **BRAM Server** (`bram-core`) | HA App or Docker Compose | World model, initiative, model adapters, memory, outreach, reflection, HA-down alerts |
| **Model provider** | Anywhere | Chat, tools, vision, optional embeddings |
| **Trainer** (optional) | Machine with a suitable GPU | One-off LoRA/QLoRA runs |
| **Voice ID** (optional) | With the server | Speaker recognition; personalization only |

One owner may connect several houses to one server. Different owners run separate servers; there is no central service.

Full watchdog coverage requires the server on a different machine from HA, plus an off-site heartbeat to detect power or internet loss.

### Connectors

Home Assistant is the first connector, not a dependency of the server core. Chat-only connectors (Open WebUI, phone, Telegram) may be added. Any connector that can control something must have its own gate under the same hard rules. Home Assistant stays the only controllable system through M5.

### Packaging

One server image, two packages: an HA App (HA OS/Supervised) and Docker Compose (any machine). The HA integration is installed separately through HACS. SQLite is inside the server; no database app is needed.

### Server modules
- **Senses**: normalized events from HA and Frigate.
- **World model**: presence, openings, devices, confidence, and explicit unknowns.
- **Safety engine**: deterministic rules and fixed-text alerts.
- **Initiative**: decides whether anything is worth saying.
- **Brain**: our own tool loop with bounded rounds and timeouts.
- **Outreach**: channel choice, delivery, replies, escalation.
- **Memory**: facts, observations, guesses, conversations, open threads, audit.
- **Reflection**: scheduled habit statistics and proposals.

## 3. Requirements

| Item | Requirement |
|---|---|
| Home Assistant | 2026.8 or later (to be confirmed during M0) |
| HACS | Recommended; manual install supported |
| Database | SQLite, built in. Only the server writes to it. Postgres + pgvector may be added later behind the storage interface |
| Model provider | At least one. Ollama first, then OpenAI-compatible, OpenAI, Anthropic, Gemini |
| Frigate | Optional event source |
| STT / TTS | Whatever the owner's Assist pipeline uses. Built-in providers are a later option |
| GPU | Not required by BRAM itself |

## 4. Features

| Feature | BRAM design | Milestone |
|---|---|---|
| Proactive outreach | Section 5 | M2 |
| Personality modes | Section 5, Personality modes; wording only | M3 |
| Conversational control | Assist conversation agent; every action through the gate | M3 |
| Streaming replies | Word-by-word where HA supports it; success is claimed only after confirmation | M3 |
| Long-term memory (optional) | Section 6 | M4 |
| Safety and anomaly rules | Leaks, smoke, openings, unknown person, offline security devices; deterministic | M2 basic, M5 full |
| Camera and image analysis | A camera or Frigate detects; a vision model describes; section 7 | M5 |
| HA security audit | Read-only checks such as new admins, tokens, and exposed locks; reports checks it could not run | M5 |
| Habit learning | Section 8 | M6 |
| Automation drafting | Draft, validate, show, approve; rule A9 | M6 |
| Internet search and extra tools | MCP, off by default; rules D2 and D3 | M6 |
| Face recognition | Frigate's results first; external service optional | M7 |
| Voice recognition | Optional CPU model | M7 |
| Built-in STT / TTS | Only if the Assist pipeline proves insufficient | Later |
| Trainer | Section 9 | M8 |

The fuller feature list and current order are in [docs/roadmap.md](docs/roadmap.md), which the owner extended on 2026-11-25 with watchdog rules, history questions, digests, network and radio checks, and backup models.

## 5. Reaching out

**Triggers:** an event, a schedule, a promised follow-up, or an expected thing that did not happen.

```
candidate → policy (code) → compose (model, fixed-text fallback) → deliver → reply → act / snooze / remember
```

- **Policy** weighs urgency, usefulness, confidence, and interruptibility. Outcomes: silent, digest, message, speak, escalate.
- **Where:** a room speaker only if the person is confirmed in that room and the message is not personal; otherwise their phone.
- **Replies:** notification buttons first; two-way voice on satellites that support it.
- **Open threads:** promised follow-ups are stored and survive restarts.
- **Tact:** ignored or dismissed topics become less frequent. Safety alerts are exempt.
- **Defaults:** quiet hours on, a few useful messages a day, only the owner contacted until others opt in.
- **Cost control:** rules decide before any model call; similar events are batched; daily model budget.

Safety alerts use a separate path that skips policy and composition.

### Settings

| Where | What |
|---|---|
| Home Assistant, BRAM's options | Entities, tiers, HA phone and speaker delivery, and **quiet hours for Home Assistant delivery only** |
| BRAM config page, on the server | Model, people, personality, memory, other connectors and their own quiet hours, audit log |

Each connector owns its own quiet hours; they never affect another connector or any safety alert. First-run setup lets the owner create the login in a browser, with no code, for 15 minutes after the server starts and only until a login exists. Sensitive changes ask for the password again. A second factor is required before any control feature ships (M3). Normal setup never needs a command line. The config page is encrypted, locks out repeated failures, and cannot lower a tier or approve an action: those stay in Home Assistant.

### Personality modes

Chosen by the owner and changeable at any time. A mode changes wording only.

| Mode | Style |
|---|---|
| Professional (default) | Brief and polite |
| Friendly | Warm and casual |
| Dry | Deadpan and sarcastic |
| Minimal | As few words as possible |
| Unhinged | Full cussing, no holds barred |
| Custom | The person's own description |

- Modes never change permissions, approvals, facts, limits, or when BRAM speaks. Custom text is style only and is treated as data.
- Safety alerts, approval requests, and PIN prompts always use their fixed text.
- The owner's chosen mode applies everywhere BRAM talks: its page, Assist, speakers, and Telegram. Per-person modes may come with M7.
- Unhinged may roast the person who chose it. It does not use slurs, threats, or sexual content about real people, and does not target anyone else in the home.
- How far a mode goes depends on the chosen model. The setup screen shows a sample.

## 6. Memory

**Optional (rule E10).** The owner chooses during setup, and each person can opt out. Two separate stores:

| Store | Holds | Can be off? |
|---|---|---|
| Operational | Settings, permissions, consent, "stop telling me" choices, pending alerts, audit log without conversation text | No |
| Memory | Conversations, facts, preferences, observations, habits, open threads | **Yes** |

With memory off: control, live-state answers, outreach, and safety alerts work. The current conversation is kept in RAM until it ends. Preference recall, promised follow-ups, habit learning, tact learning, and trainer examples are unavailable, and BRAM says so if asked.

With memory on:

- SQLite with keyword search. Semantic search is added when an embedding model is configured.
- Types: told fact, preference, correction, observation, guess, open thread.
- Every record has house, person, source, time, confidence, and expiry.
- Raw observations expire; told facts stay until corrected or deleted.
- Original text is kept so the search index can be rebuilt after an embedding change.
- Consistent backup copies; optional API access for Open WebUI and other tools, scoped per person.

## 7. Models

Providers implement one adapter: messages + tools + optional images in; text or tool requests out. Setup tests tool calling, structured output, images, and context size, and turns off what fails. Owners may use one model for everything or one per job.

Image text is data. Image detail can enrich an alert but not hold it back.

## 8. Reflection and learning

Code computes statistics such as arrival windows and lockup times from compact daily summaries. The model only puts the results into words. Output is a proposal with evidence count and expiry, shown to the owner for approval.

## 9. Trainer

Optional, and off by default. It does not run inside Ollama, which serves models but does not train them.

`approved examples → train → merge → convert → load as a new model → test → owner promotes or keeps the old one`

Backends: Unsloth for NVIDIA, MLX-LM running natively on Apple Silicon. The full path must be proven with a small run for each supported model family.

## 10. Milestones

Each milestone ends with its rule tests passing and the owner's approval.

| | Milestone | Done when |
|---|---|---|
| M0 | **Prove it** | Model benchmark for tools, vision, speed, and context; HA version checked; repo, CI, and a fake HA and fake model for tests |
| M1 | **Link** | Pairing, event feed, world model, audit; gate refuses everything; logs what it *would* say |
| M2 | **Reach out** | Phone and speaker messages, replies, basic safety alerts, HA-down alert through ntfy |
| M3 | **Butler** | Conversation, Tier 1 control, then Tier 3 approval |
| M4 | **Memory** | Corrections, preferences, and open threads recalled and deletable |
| M5 | **Watchdog** | Frigate, vision, anomaly rules, audit, escalation; two weeks log-only first |
| M6 | **Learning** | Approved habits, automation drafts, optional search |
| M7 | **Identity** | Opt-in face and voice personalization |
| M8 | **Trainer** | One verified model trained, tested, promoted, and rolled back |

## 11. Decisions

1. Tier 3: the owner approves by a tap on their phone, with an optional PIN per device, and can delegate per person and device.
2. MIT license.
3. Contact channels, each chosen per person:

| Channel | To people | From people | Milestone |
|---|---|---|---|
| HA phone app (main) | Push, buttons, critical alerts | Buttons, Assist chat and voice | M2/M3 |
| Speakers, kiosk, voice satellites | Speech, display | Voice where there is a microphone | M2/M3 |
| ntfy (optional) | HA lost, non-HA monitors | Acknowledge and snooze buttons only, never commands | M2 |
| Telegram (optional) | HA lost, non-HA monitors; photos in M5 | Buttons in M2, chat in M3 | M2/M3 |
| SMS / call (optional) | Last-resort escalation | None | Later |

Voice is optional, and no particular hardware is assumed. BRAM is a conversation agent in the owner's own Assist pipelines, so replies go wherever each pipeline already sends them. For outreach, each room can be set to: none (default), its voice satellite, or any media player, for homes where the microphone and speaker are different devices. After speaking through a media player BRAM restores what was playing where the player supports it, and rule E4 applies. Two-way outreach needs a satellite that can start a conversation; otherwise the follow-up goes to the phone.

WhatsApp and a custom phone app are not planned. Outside services are off by default, with private details and photos switched separately. Tier 3 approval happens only through the HA app, with an optional PIN.
