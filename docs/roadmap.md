# Roadmap

Plans may change. Every item must follow the [Hard rules](../HARD_RULES.md).

## Built

Pairing, live state, home alerts, Telegram and ntfy messages, monitors, config page, chat, Assist, voice, personalities.

## 1. Watchdog rules and questions

| Feature | Notes |
|---|---|
| Lock unlocked at night | Night hours set by the owner |
| Door or window open while everyone tracked is away | Unknown people count as maybe home |
| Door left open too long | Time set by the owner |
| Lock, alarm, or camera unavailable | |
| "When did the back door last open?" | Reads Home Assistant's history for shared devices only |
| Daily digest | Optional, at a chosen time |
| Grouped messages | Several routine messages become one; safety alerts are never grouped |
| Longer gaps for routine messages marked as false alarms | Never for safety alerts |

## 2. Security check: "Is my home secure?"

Read-only. Reports which checks could not run, and never says a home is safe.

| Area | Checks |
|---|---|
| Home Assistant | New admin accounts and tokens, old tokens, failed logins, locks or doors exposed to voice assistants, public webhooks, apps with exposed ports, login bypass, proxy mistakes |
| Network | Devices joining for the first time, router updates, UPnP, changed public address |
| Radios | Joining left open, new devices, weak Z-Wave security on locks, coordinator updates |

Network details are pseudonymized before any model sees them. No active scanning or attacks.

## 3. Control

| Feature | Notes |
|---|---|
| Second factor for the config page | Before any control |
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

Usual patterns and what departs from them, appliances left on, unusual power use, and suggested rules and automations. Suggestions can be previewed and do nothing until approved.

## 8. Identity and trainer

Opt-in face and voice recognition for personalization only, then the optional trainer.
