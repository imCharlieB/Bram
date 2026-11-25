# Roadmap

Plans may change. Every item must follow the [Hard rules](../HARD_RULES.md).

## Built

Pairing, live state, home alerts, Telegram and ntfy messages, monitors, config page, chat, Assist, voice, personalities, lock and door watching, history and problem questions, daily summary, grouped messages, Home Assistant [security check](security-check.md).

## 1. Questions and digests

| Feature | Notes |
|---|---|
| Longer gaps for routine messages marked as false alarms | Never for safety alerts |

### Home Assistant problems

Built for chat. Next: being told when something new keeps failing.

## 2. Security check: "Is my home secure?"

The Home Assistant part is built. Still to come: apps with exposed ports, proxy mistakes, and the rows below.

Read-only. Reports which checks could not run, and never says a home is safe.

| Area | Checks |
|---|---|
| Network | Devices joining for the first time, router updates, UPnP, changed public address |
| Radios | Joining left open, new devices, weak Z-Wave security on locks, coordinator updates |

Network details are pseudonymized before any model sees them. No active scanning or attacks.

## 3. Control

The second factor for the config page is built. Control will require it to be on.

| Feature | Notes |
|---|---|
| Safety test for the chosen model | Before any control |
| Allowlisted lights, then other comfort devices | Everything else is refused; results are confirmed |
| Off switch in Home Assistant | Works without the server |
| Contradiction check | "Lock" can never become "unlock" |
| Step and rate limits | |
| Approvals for locks, garages, and alarms | Also for any script, scene, or group that reaches them |

## 4. Reliability

Backup models per job, all local unless the owner chooses otherwise; pausing a failing model and trying again later; summarizing long chats; a health sensor.

## 5. Memory

Optional, for the installation and per person.

## 6. Cameras

Frigate events described by a vision model, unknown people through Frigate, vehicles and pets, stale cameras.

## 7. Learning

[Suggested hours](learning.md) are built.

### Patterns

Usual patterns and what departs from them, appliances left on, unusual power use, and suggested rules and automations. Suggestions can be previewed and do nothing until approved.

## 8. Identity and trainer

People in Home Assistant are linked to their phones, so messages can go to the right person. Rooms, and later routines, can be linked to people by the owner.

Opt-in face and voice recognition for personalization only, then the optional trainer.
