# Plan

Every feature, what is built, and the order for the rest. Nothing gets built unless it is on this page, and each phase needs the owner's approval before it starts. Everything follows the [Hard rules](../HARD_RULES.md).

BRAM's job: **notice** what is happening, **remember** it, **explain** what is wrong, **tell** the right person, and **fix** what it is allowed to fix.

| Mark | Meaning |
|---|---|
| ✅ | Built |
| 🟡 | Partly built |
| ⬜ | Not built |

## The order

| Phase | Result | Depends on |
|---|---|---|
| [1. One record](#1-one-record) | Everything BRAM finds, says, and does is in its database, kept safely | |
| [2. Find](#2-find) | BRAM finds problems by itself, without being asked | 1 |
| [3. Explain](#3-explain) | Each problem comes with what happened, a likely cause, and what to do | 1, 2 |
| [4. Control and fix](#4-control-and-fix) | Lights, then repairs with a tap, then other devices, then locks | 1, 3 |
| [5. Memory](#5-memory) | It remembers you and corrections, if you want | 1 |
| [6. Cameras](#6-cameras) | It knows what cameras saw | 2 |
| [7. Learning](#7-learning) | It learns what is normal and suggests rules and automations | 1, 2, 5 |
| [8. People](#8-people) | The right message to the right person | 5, 6 |
| [9. Models and trainer](#9-models-and-trainer) | Backups, other providers, then training | 5 |
| [10. Speakers](#10-speakers) | BRAM speaks in rooms | 8 |

## Working today

| Feature | Status | More |
|---|---|---|
| Pairing, live state, rooms, people, media, pictures | ✅ | [Devices](devices.md) |
| Recommended setup and suggestions | ✅ | [Configuration](configuration.md) |
| Leak, smoke, CO, gas, and heat alerts that repeat until acknowledged | ✅ | [Watching](watching.md) |
| Lock and door rules, silent sensors | ✅ | [Watching](watching.md) |
| Home Assistant security check, hourly or when asked | ✅ | [Security check](security-check.md) |
| HA phone app, Telegram, ntfy | ✅ | [Messages](messages.md) |
| Quiet hours, daily limits, Stop these, grouping, daily summary | ✅ | [Messages](messages.md) |
| Monitors for things outside Home Assistant | ✅ | [Monitors](monitors.md) |
| Chat on the page, in Assist, and in Telegram | ✅ | [Chat](chat.md) |
| Chat looks up history, errors, batteries, and updates **only when asked** | ✅ | [Chat](chat.md) |
| Whisper and Piper | ✅ | [Voice](voice.md) |
| Personalities | ✅ | [Personality](personality.md) |
| Suggested night hours | ✅ | [Learning](learning.md) |
| Command center page, second factor | ✅ | [Security](security.md) |

## 1. One record

Today the server's database logs connections, sign-ins, monitors, what the server noticed, and Telegram and ntfy messages. Since 0.24 it also holds findings, phone messages, and learned hours. Home Assistant errors are not kept yet; that is phase 2.

| Feature | Status |
|---|---|
| Server database and append-only log | ✅ |
| Every finding in one list: what, where, first seen, last seen, how often, told, acknowledged, fixed | ✅ [Findings](findings.md) |
| Home Assistant sends its findings and phone messages to that list, and catches up after a disconnect | ✅ |
| Findings page: open, fixed, and ignored, with the story of each | ✅ |
| History of shared devices, off until you turn it on (rule E10) | ✅ [History](history.md) |
| Climate: every run of heating, cooling, and fan, with start, end, target, mode, preset, inside and outside temperature | ✅ |
| Readings: temperature, humidity, air quality, power, energy, and water | ✅ |
| Past readings brought in from Home Assistant's own statistics, so trends do not start from nothing | ✅ |
| Learning reads quiet nights and door times from history, the one record; Home Assistant keeps none of its own (0.34) | ✅ |
| Size limit and total size on the page | ✅ |
| Each thermostat compared with the room's other temperature sensors | ✅ |
| Size by device, and [cleaning up](#cleaning-up) by asking you or when you say so | ✅ |
| Safe to copy while running, and a check at startup that it is not damaged | ✅ |
| Delete a device's, person's, or home's history | ✅ |

Done when: every message BRAM sends can be traced to a stored finding, a restart loses nothing, a copy taken while running opens cleanly, and BRAM can answer "how long did the AC run each day last week, and at what setting?" from its own data.

### Size

Measured: 38 bytes for a reading, 55 for an event. Assuming 100 readings averaged every 5 minutes and 5,000 events a day:

| Kept | Suggested | Size |
|---|---|---|
| Readings every 5 minutes | 1 year | 400 MB |
| Readings every hour | Always | 33 MB a year |
| Events, such as doors, motion, and people | 2 years | 200 MB |
| Heating and cooling runs | Always | Under 1 MB a year |
| Findings and log | Always | A few MB a year |
| **Limit** | 2 GB, or what you set | |

Nothing is thrown away just for being old. The times above are only what BRAM suggests when it asks.

### Cleaning up

| How | What happens |
|---|---|
| BRAM asks | At 80% of the limit it lists what is biggest and least used, with sizes, such as "Hall motion: 140 MB, never used for a finding." You choose **Delete**, **Shorten**, **Keep**, or **Ask in 30 days** |
| You tell it | "Delete motion from before June" or "stop keeping the garage temperature", in chat or on the page |

- Code works out exactly what matches, how many entries, how much space, and what trends would be lost. Nothing goes until you confirm that exact list on the page. The model never deletes anything.
- Shorten turns 5-minute readings into hourly ones, so trends survive.
- If the limit is reached with no answer, only the oldest 5-minute readings are shortened to hourly, and you are told. Hourly readings, heating and cooling runs, and findings are never removed without you.
- The log of what BRAM did cannot be deleted (rule A11).

### Backups and secrets

BRAM does not make its own backups; back up the machine or volume it runs on. The database uses SQLite's write-ahead log, so a snapshot of the whole volume can be recovered. Such a backup holds the Telegram token, ntfy topics, and second-factor key, so encrypt it. BRAM does not encrypt these itself, because its key would sit in the same backup.

## 2. Find

BRAM looks by itself. Plain rules decide what is a problem. One finding per problem, told once, told again when fixed, with Stop these.

### Home Assistant health

| Finds | Status |
|---|---|
| Integration failed to start or keeps retrying | ✅ [Problems](problems.md) |
| The same error repeating | ✅ |
| New repairs | ✅ |
| Low batteries, and phone battery low at night | ✅ |
| Devices or whole integrations gone offline; temperature and humidity sensors stuck on one value | ✅ |
| Automations that could not be loaded or name devices that do not exist | ✅ |
| Automations that fail when they run | 🟡 as a repeating error |
| Backups old, disk almost full, database size | ✅ |
| Memory | ⬜ |
| Updates waiting | ✅ listed only |

### Home

| Finds | Status |
|---|---|
| Unlocked at night; open or unlocked while away; left open; offline | ✅ |
| Motion while away | ✅ 0.35 |
| Motion at night while away | ⬜ |
| Open at night; open while heating or cooling | ✅ 0.35 |
| Several things open at once | ⬜ |
| Alarm off when everyone left, or not matching who is home | ⬜ |
| Too hot, too cold, humid, near freezing | ✅ 0.35 |
| Poor air | ⬜ |
| Appliance left on; power, water, or energy far from usual | ⬜ |

### Security

| Finds | Status |
|---|---|
| New admins and tokens, old tokens, failed sign-ins, login bypass | ✅ |
| Locks exposed to voice assistants, webhooks, offline locks and cameras, UPnP set up, Zigbee joining | ✅ |
| Apps with open ports or protection off, HA Cloud remote access, sign-in blocking misconfigured | ⬜ |
| New Zigbee, Z-Wave, Bluetooth, or Matter device; Z-Wave joining open; weak Z-Wave security; coordinator updates | ⬜ |
| New device on the network, with Trust; unconfigured discovered devices | ⬜ |
| Router update, changed public address, new port opened, guest Wi-Fi left on, router protection off, unusual data use | ⬜ |

### 3D printers

Read from the printer's own integration. One printer is one device with a section of its own on Home.

| Feature | Status |
|---|---|
| Printer found automatically: printing, paused, idle, off, with progress, time left, and file name | ✅ [3D printers](printers.md) |
| Nozzle, bed, and chamber temperatures against target | ✅ |
| Told when finished, failed, paused, or asking for attention | ✅ |
| Told when out of filament | 🟡 as paused or a problem |
| Heater on while idle, or temperature far below target: routine warning, and never a substitute for a smoke alarm | ✅ |
| Printer offline during a print; off when idle is normal | ✅ |
| Smoke or heat sensor in the printer's room named in the alert | ⬜ |
| Each print remembered: file, length, result, filament | ✅ |
| Power used by a print | ⬜ |
| Picture of the print, then the vision model looking for failed prints (phase 6) | ⬜ |
| Pause a print with one tap; never start one or heat anything (phase 4) | ⬜ |

### Outreach

| Feature | Status |
|---|---|
| Severity for every finding; quiet hours by severity | ⬜ |
| Exclude a device from one rule | 🟡 Stop these only |
| From Home and Findings: **Less often** and **Stop these**, the same buttons the phone was given, checked by Home Assistant | ✅ 0.33.0 |
| From Home: **Acknowledge** a safety alert, with the second factor (rule C4) | ⬜ |
| Longer gaps for what you mark as a false alarm; never for safety | ⬜ |
| Daily summary built from the findings list | 🟡 current states only |
| Optional model triage: may lower the priority of routine findings, never hide safety | ⬜ |

Done when: a failed integration, a dead battery, and a repeating error are each reported without being asked.

## 3. Explain

| Feature | Status |
|---|---|
| History of shared devices, 10 days | ✅ when asked |
| Each finding checked against history: how often, since when, what changed just before | ⬜ |
| Likely cause, worded by the model and marked as a guess | ⬜ |
| What to do, from a fixed list per problem | ⬜ |
| Ask about a finding: "why?", "what changed?", "has it happened before?" | ⬜ |
| Energy and usage reports | ⬜ |
| Longer history and totals, from phase 1 | ⬜ |

## 4. Control and fix

Needs the owner's go-ahead and the second factor on. Everything not on the list is refused in code.

| Step | Feature | Status |
|---|---|---|
| 4.1 | Off switch in Home Assistant; limits; every action logged; results confirmed; "lock" can never become "unlock" | ⬜ |
| 4.2 | Safety test the chosen model must pass, again whenever it changes | ⬜ |
| 4.3 | Lights you pick | ⬜ |
| 4.4 | Fixes with one tap: reload an integration, turn an automation back on, dismiss a solved repair | ⬜ |
| 4.5 | Fans, climate, media, scenes you pick | ⬜ |
| 4.6 | Fixes you allow without a tap, one kind at a time | ⬜ |
| 4.7 | Locks, garages, and alarms by a tap on your phone; PIN optional | ⬜ |
| | Streaming replies | ⬜ |

## 5. Memory

Optional, for the installation and per person.

| Feature | Status |
|---|---|
| Facts, preferences, and corrections, with who said it and when | ⬜ |
| See, correct, and delete memories | ⬜ |
| Promised follow-ups that survive a restart | ⬜ |
| Search by word, then by meaning with an embedding model | ⬜ |
| Long chats shortened instead of forgotten | ⬜ |

## 6. Cameras

| Feature | Status |
|---|---|
| Frigate events: people, vehicles, pets, packages | ⬜ |
| Ask what a camera sees; a vision model describes it | ⬜ |
| Person near an open or unlocked door; person while away; motion with no camera activity | ⬜ |
| Picture in the message; repeats of the same scene combined | ⬜ |
| Camera stale, offline, or disabled | 🟡 offline |
| Unknown person, through Frigate's face recognition | ⬜ |
| One summary per event: frames while the event lasts, unchanged frames dropped, frames with a person always kept, then the vision model sums it up | ⬜ |
| Tell only when unusual: the same scene (a parked car, an empty porch) is not told again, the same person not within 30 minutes; a cooldown per camera and across cameras | ⬜ |
| Recognized people for each camera, as a Home Assistant sensor, with names from Frigate | ⬜ |
| Last event picture for each camera, as a Home Assistant image, with its summary | ⬜ |
| Scheduled camera checks, such as "any packages on the porch?" every hour, told only when the answer is yes | ⬜ |

Blueprints keep these in Home Assistant, where you can see and change them:

| Blueprint | Does | Status |
|---|---|---|
| BRAM scheduled check | On a schedule, asks BRAM a question, such as "any packages on the porch?", and tells your phone only when the answer is yes | ✅ 0.35, see [Blueprints](blueprints.md) |
| BRAM house summary | On a schedule, asks BRAM for the state of the home, cameras included, and sends it | ✅ 0.35, cameras when they come |
| BRAM camera event | When a camera's recognized people or last event changes, sends the picture, the summary, and the names | ⬜ |
| BRAM finding router | When BRAM finds something, runs a script you choose for that kind of finding. Anything that unlocks, opens, or disarms still needs your approval by a tap (rules A3, A15) | ⬜ |

## 7. Learning

| Feature | Status |
|---|---|
| Suggested hours, with approval and undo | ✅ |
| Usual values by hour and weekday, and what departs from them | ⬜ |
| Thermostat against room sensor over time: drift, a room that lags, and which one to trust | ⬜ |
| Climate trends: run time against outside temperature and setting, a system working harder than it used to, what each setting costs in run time, suggested settings | ⬜ |
| Usual arrivals, lockup, and routines | ⬜ |
| Suggested rules, previewed against past days before approval | ⬜ |
| Describe an automation; BRAM drafts it, checks every device exists, shows it, and installs it only after approval | ⬜ |
| Switch a suggested rule off, back on, or repair it | ⬜ |

## 8. People

| Feature | Status |
|---|---|
| Safety-only phones | ✅ |
| Person linked to phone; who gets which kind of message | ⬜ |
| Room-aware delivery; escalate to someone else | ⬜ |
| Opt-in face and voice, for personalization only | ⬜ |

## 9. Models and trainer

| Feature | Status |
|---|---|
| Ollama, with a benchmark | ✅ |
| A model per job: chat, vision, triage, summary, search | ⬜ |
| Backup model; stop using one that fails, and try again later | ⬜ |
| OpenAI-compatible, OpenAI, Anthropic, Gemini; off by default | ⬜ |
| Web search and other tools through MCP; off by default | ⬜ |
| BRAM's own health: model, database, rules, last check | 🟡 connection and versions |
| Trainer, with approved examples only | ⬜ |

## 10. Speakers

| Feature | Status |
|---|---|
| Speak through a satellite or any media player, then restore what was playing | ⬜ |
| Two-way conversation where the satellite supports it | ⬜ |

## Not doing

| Not doing | Instead |
|---|---|
| A PIN for ordinary things | Tap; PIN optional for locks and garages |
| Active network scanning | Reads what Home Assistant and the router already report |
| A model that decides safety alerts | Plain rules and fixed words |
| Model calls that choose and run fixes by themselves | The gate allows or refuses |
| A separate database app | SQLite inside the server; Postgres possible later |
| WhatsApp, a custom phone app | HA app, Telegram, ntfy |

## Decided

| Question | Answer |
|---|---|
| Order | As above |
| Reload an integration after a tap | Yes; rule A8 allows it |
| Learned hours in the server's database | Yes |
| Backups | By whatever backs up the server's machine |
| How long to keep things | Depends on size; BRAM asks what to remove, or the owner says |
