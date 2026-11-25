# Changes

## Unreleased

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
