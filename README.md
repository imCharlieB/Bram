<p align="center">
  <img src="https://raw.githubusercontent.com/imCharlieB/Bram/main/custom_components/bram/brand/icon%402x.png" alt="BRAM" width="160">
</p>

<h1 align="center">BRAM</h1>
<p align="center"><b>Butler, Reconnaissance &amp; Automation Manager</b><br>
A self-hosted agent for your home that reaches out, instead of waiting to be asked.</p>

[![CI](https://github.com/imCharlieB/Bram/actions/workflows/ci.yml/badge.svg)](https://github.com/imCharlieB/Bram/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-26c6be.svg)](LICENSE)

## What BRAM will be

- **Butler**: talk to your home, with risky actions always needing your approval
- **Reconnaissance**: notices what matters and tells the right person
- **Your model**: Ollama first, others later, with no cloud required
- **Your rules**: safety limits enforced by code, not by asking the model nicely
- **Your personality**: from professional to unhinged
- **Optional memory**: on, off, or per person

## What works today

- Encrypted pairing between Home Assistant and the BRAM Server
- You choose exactly which entities BRAM sees; nothing by default
- A device page showing what BRAM believes, live
- Leak, smoke, and silent-sensor alerts through the Home Assistant app, even if the server is down
- Optional Telegram and ntfy messages when Home Assistant or a monitored device is lost
- Chat with BRAM on its page, in Assist, and in Telegram (with voice notes) if you turn it on; it saves nothing and controls nothing
- Optional hold-to-talk and spoken answers with your own Whisper and Piper
- A config page for setup, messages, model, personality, and the log

## Status

> **Early development.** This version watches and can send alerts; it cannot control anything. It is not a substitute for certified smoke, CO, or security alarms.

| Milestone | Status |
|---|---|
| M0 Model connection, benchmark, test fakes | Built |
| M1 Connect to Home Assistant, log only | Built |
| M2 Reach out | Built |
| M3 Chat and control | Chat built; control planned |
| M4 Optional memory | Planned |
| M5 Watchdog | Planned |
| M6 Learning | Planned |
| M7 Identity | Planned |
| M8 Trainer | Planned |

## Documentation

**[All documentation](docs/README.md)**

| Start | Features | How it works |
|---|---|---|
| [Installing](docs/installation.md) | [Watching your home](docs/watching.md) | [Architecture](docs/architecture.md) |
| [Devices](docs/devices.md) | [Alerts and messages](docs/messages.md) | [Security](docs/security.md) |
| [Every setting](docs/settings.md) | [Monitors](docs/monitors.md) | [What BRAM stores](docs/data.md) |
| [Roadmap](docs/roadmap.md) | [Chat](docs/chat.md) | [Hard rules](HARD_RULES.md) |
| [Changes](CHANGELOG.md) | [Voice](docs/voice.md) | [Server commands](docs/server.md) |
| | [Personality](docs/personality.md) | [Development](docs/development.md) |

MIT licensed. See [LICENSE](LICENSE).
