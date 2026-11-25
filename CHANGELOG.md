# Changes

## Unreleased

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
