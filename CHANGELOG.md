# Changes

## Unreleased

## 0.25.0

- Clean up history: see what each device uses, then shorten, delete, or stop keeping it. Nothing goes until you confirm the exact list.
- Ask in chat, such as "delete hall motion readings older than 90 days". Chat only makes the list.
- BRAM asks when its history is 80% full.

## 0.24.0

- Findings: one list of everything BRAM found, with how often, whether you were told, and when it ended. Covers phone messages, lock and door rules, safety, security, and monitors.
- Home Assistant catches the server up after a disconnect.
- Chat knows what is open.
- Learned nights are copied into the server's database.

## 0.23.0

- BRAM can keep history in its own database: readings, every heating and cooling run with its settings, and device changes. Off until you turn it on under History.
- Brings in hourly averages Home Assistant already keeps, if history sharing is on.
- Compares each thermostat with the other temperature sensors in its room.
- The radar shows the room a person is in, as the People panel does.
- Ask how long heating or cooling ran. The page has a History section, with the space used.

## 0.22.1

- Security check: a token is reported by age. It said "not used", which Home Assistant does not record.
- Security check: UPnP wording no longer claims the router allows it, and cameras on 3D printers are left out.
- Chat answers a security question with what was found first.
- The chat scroll bar matches the page.

## 0.22.0

- Optional second factor for signing in to BRAM's page: authenticator app codes, with recovery codes.

## 0.21.0

- BRAM can suggest better night hours and left-open time from your activity, for you to approve in Repairs. Off by default.
- Friday and Saturday nights can have their own night hours.
- Removing BRAM from Home Assistant deletes everything it kept there.

## 0.20.0

- Ask "Is my home secure?" for a read-only check of Home Assistant, and optionally be told when it finds something new. Both are off by default.
- Three or more routine phone messages at once become one. Safety alerts are never grouped.

## 0.19.0

- The command look covers every page, including sign-in.

## 0.18.1

- Devices on the command deck are larger, with icons and names, and open their details when clicked.

## 0.18.0

- Rooms need no setup: BRAM reads each room's presence from its own sensors in Home Assistant, and finds a person's room sensor by name.

## 0.17.1

- Choose the sensor that says which room each person is in.

## 0.17.0

- Location: floors, the room a person is in, and named places such as Work. The command deck can be arranged by type or by room.

## 0.16.0

- Richer devices: people's photos, what is playing, brightness, battery, room, and how long, on the deck and in chat.
- Getting started and BRAM's reactions show on the command deck.

## 0.15.0

- A real command deck: a full-screen live map of the house with gauges, sectors, activity, and an event log, in four colors.

## 0.14.1

- Choose phones that get safety alerts only.

## 0.14.0

- Command look for BRAM's home page, with alerts and every shared device live. Choose Classic in Profile for the old look.
- Safety sensors now include carbon monoxide, gas, heat, safety, and tamper.
- Any other sensor can be shared for chat.

## 0.13.0

- BRAM can also see media players, voice assistants, thermostats, temperature, humidity, switches, and fans.
- A configuration guide with every model, engine, port, and file.

## 0.12.0

- Voice setup in one button: BRAM finds Whisper and Piper, you choose and hear a voice, and test both. It explains what to do if they are missing.
- Recommended setup in Home Assistant: one page with sensible choices.
- Mood on the device page, and a Visit button that opens BRAM's page.
- The out-of-date warning ignores small fixes.

## 0.11.0

- Daily summary on your phone at a time you choose. Off until set.
- History answers use lengths worked out by code, and show the recorded changes under the answer.

## 0.10.0

- Chat can look up history ("when was the back door last opened?") and Home Assistant problems ("any errors?"). Both are off until you turn them on.

## 0.9.0

- BRAM's suggestions: what it most needs to see and cannot yet.
- Add devices quickly: BRAM finds what it understands by type and area, and you choose what to share.
- A documentation index, and pages for devices, settings, monitors, personality, watching, and stored data.

## 0.8.0

- Watch locks and doors: unlocked at night, open or unlocked while everyone is away, left open, or offline. All off until you turn them on.
- Guides to how BRAM works, security, and the roadmap.
- Approvals will be a tap on your phone; a PIN is optional.

## 0.7.0

- BRAM can be chosen as a conversation agent in Home Assistant's Assist. It answers only about that home and cannot control anything.
- Telegram voice notes, if chat and hearing are set up.

## 0.6.3

- BRAM warns, on its page and in Home Assistant's Repairs, when the server and Home Assistant sides are different versions.
- Home Assistant options are split into a short menu with grouped choices, and device page names are plain.
- Device page names stay right after Home Assistant restarts.

## 0.6.2

- Monitors show their type and why they are not answering, and the type must be chosen.

## 0.6.1

- Frigate monitors work whether or not you type `https://`.

## 0.6.0

- Voice: hold to talk on the home page, and spoken answers, through your own Whisper and Piper. Off until set up.
- ntfy setup by QR code or link, and topics short enough to type. Press **New secret topic** to get a short one.
- Frigate monitors work with the login port, 8971.
- Optional stacks: `compose.full.yaml` with everything, or `compose.voice.yaml` with only Whisper and Piper.

## 0.5.0

- Chat with BRAM on its home page. It answers from live state, shows the sensor readings it should match, cannot control anything, and saves nothing.
- Optional chat through Telegram, off by default.
- **Allow stopped messages** button in Home Assistant.
- New monitors are checked as soon as they are added.
- Step-by-step guides for installing and for alerts.

## 0.4.0

- Leak, smoke, and silent-sensor alerts from Home Assistant to your phone, with reminders until acknowledged and quiet hours in BRAM's options. They work without the server.
- Telegram and ntfy messages when Home Assistant is lost, or a monitored Ollama, Frigate, or device stops answering. Both are off until you turn them on.
- Messages page with quiet hours, test messages, and stopped messages.
- A livelier home page and a shorter menu.
- ntfy is part of the Docker stack.

## 0.3.0

- The config page has a menu, an overview, its own log page with filters, and a profile for your username, password, and signed-in devices.

## 0.2.0

First versioned release. Early development: watches and logs only.

- Hard rules, design, and user documentation.
- Ollama model connection and `bram-bench`.
- M1: encrypted one-time pairing, read-only Home Assistant integration, `bram-server`, and Docker Compose.
- Prebuilt server image, Portainer instructions, clean shutdown, and immediate container logs.
- Lights and motion can be chosen, and the BRAM device page shows what BRAM believes about each entity.
- Log: readable times, optional house ID, and a notice when a safety sensor recovers.
- Logo, a fuller HACS page, and an icon for each kind of entity.
- First-run setup page, and pairing from the config page; no command line needed.
- Config page: status, log, local model, and personality with a live sample.
- House state with explicit unknowns, append-only audit log, and a log-only watcher.
- Test fakes, rule coverage check, and documentation check.
