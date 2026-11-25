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
- A log of leak and smoke messages it *would* send

## Status

> **Early development.** This version only watches and logs; it sends no alerts and cannot control anything. It is not a substitute for certified smoke, CO, or security alarms.

| Milestone | Status |
|---|---|
| M0 Model connection, benchmark, test fakes | Built |
| M1 Connect to Home Assistant, log only | Built |
| M2 Reach out | Planned |
| M3 Control | Planned |
| M4 Optional memory | Planned |
| M5 Watchdog | Planned |
| M6 Learning | Planned |
| M7 Identity | Planned |
| M8 Trainer | Planned |

## Documentation

- [Installing](docs/installation.md)
- [BRAM Server](docs/server.md)
- [Testing your model](docs/benchmark.md)
- [Safety rules](HARD_RULES.md)
- [Design](SPEC.md)
- [Development](docs/development.md)
- [Changes](CHANGELOG.md)

MIT licensed. See [LICENSE](LICENSE).
