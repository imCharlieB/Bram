# Changes

## Unreleased

## 0.34.0

Update both: BRAM in HACS and the server in Portainer.

- Learning reads its quiet nights and door times from BRAM's history instead of keeping its own notes, so there is one record. It needs **Keep history** on. Nights already in history count, so a suggestion can come without another two-week wait. Notes Learning kept before are dropped.
- Docs: 3D printers start switched off.

## 0.33.0

Update both: BRAM in HACS and the server in Portainer.

- **Stop these** and **Less often** on BRAM's page: under Needs you on Home and beside findings, whenever your phone was given them. Home Assistant accepts only a button it offered for that message, once. Acknowledge stays on the phone only.

## 0.32.4

- History: while it is off, the History page starts with a large **Start keeping history** button, and the Keep history switch is larger.
- Home: with history off, Climate shows **Turn on history**.
- Home: click a side screen's tab to fold it to just the tab. The browser remembers which are folded.

## 0.32.3

- Home: the 3D printers screen shows only printers that are printing or paused. A printer whose integration is failing is still under Needs you.
- Home: the left side's scroll bar is on its outer edge, away from the brain.
- Home: the side screens sit flat instead of leaning in, so they are easier to read, and the dock's round buttons are all one size. Speak answers lights up when on, with no checkbox.
- 3D printers: only the printers you switch on in **Configure > 3D printers** are watched, shown on Home, or mentioned. A printer starts off. **After updating, switch on the printers you want.**

## 0.32.2

- Home: on a shorter screen, each side scrolls when its screens do not all fit, instead of running off the bottom.
- Home: Speak answers is a round switch in the dock, so the dock stays on one line.

## 0.32.1

- Home: a 3D printers screen again, shown only while a print is running or paused, or when a printer has a problem: progress, time left, file, and temperatures against target.
- Home: each finding under Needs you has **Story**, which opens Findings, and **Hide**, which takes it off the list without changing what is sent to your phone.
- Home: click a system on the orbit, or the House, System, 3D printers, Climate, or What I did screen, and a closer look opens over the brain: every lock and door, each thermostat and room sensor, who is home, each room and what is in it, every printer, what is not reporting, and every message today with why. Escape or Close puts it away.
- The sign-in page shows BRAM's name larger, with what it stands for.

## 0.32.0

- A new Home page: BRAM's brain of light in the middle with your home's systems orbiting it. When something happens, that system flashes and a pulse runs into the brain. Screens down both sides lean in and turn flat when you point at them: Today, House (your rooms from Home Assistant's areas, lit where someone moves, amber where something is open), System, Watching, Looking at, Climate, Needs you, I noticed, and What I did, each saying why.
- BRAM's words appear under the brain as it says them, with what it is doing: watching, listening, thinking, or speaking. With voice on, the ring around the brain follows the real sound.
- I noticed: a room sensor that reads warmer or cooler than its thermostat over the week.
- A 3D printer whose integration cannot start is shown as failing, under Needs you. One that was removed or ignored is no longer shown.

## 0.31.0

- A new Home page built around what BRAM is doing: what it is watching, with live countdowns; what it told you or held back, and why; what needs you; and the day's climate, printers, and its own health. When something happens, a card appears beside BRAM's core and drifts away, and the core pulses. Its rings show who is home, climate running, a print, and nights learned, with the words beside them.
- BRAM keeps a short note each time it holds a message back, with why: quiet hours, already told this month, or the same problem still going.
- Home Assistant tells the server what is counting down, such as a door open for 7 of its 10 minutes, a print's end, and when night starts.

## 0.30.0

- BRAM's options in Home Assistant are six pages instead of ten: Quick setup, Devices, Messages, Watching, Server access, and Learning, each with a line saying what it is for. Every switch says what it does when on.
- Home: readings across the top (outside, inside, climate running, printing, home, open), 3D printers with progress rings and temperature meters, turning gauges, and a calmer radar that names only what is on, the chosen sector, and what you point at.

## 0.29.0

- One set of rules decides how often every routine message reaches your phone: each time, once until fixed, or a reminder at most once a month. Maintenance wording, such as lubricate, clean, filter, or firmware, makes it a reminder from any device.
- A **Less often** button, from the third time in a week, sends that message at most once a day. Nothing becomes quieter unless you tap it.
- Safety alerts, and locks and doors at night or while away, are never held back.

## 0.28.6

- Printer messages are graded: a maintenance reminder is sent once a month at most, and a problem that comes and goes is told once, then again only after a day fixed. Everything still shows in Findings.

## 0.28.5

- Left open can cover doors, windows, and garage doors separately. Turn windows off if you sleep with them open; open while everyone is away still covers them.

## 0.28.4

- A shared thermostat, water heater, or appliance brings its other readings, such as hot water left or compressor health. Select it on Home to see them; chat knows them.
- An entity deleted in Home Assistant is dropped instead of showing unknown forever. One already gone is listed in Findings.
- Problems: a device whose own alert or error count is above 0, or whose health reading drops below 50%.

## 0.28.3

- Water heaters, valves, vacuums, mowers, and humidifiers have their own section, Appliances. A water heater shows its mode and setting.
- An entity renamed in Home Assistant keeps being watched under its new name instead of showing unknown.
- A 3D printer removed or disabled in Home Assistant leaves BRAM's Home page.
- People show only in the People panel on Home, not again in Active now, the radar, or Sectors.

## 0.28.2

- An entity you disable in Home Assistant is no longer watched or shown as unknown. BRAM follows at once, and lists it in Findings.
- Names that repeat the device name, or use underscores, read normally.

## 0.28.1

- Names with serial numbers in them, such as `H2D_0947AJ612800457`, show as the model, or the room and type, instead. Names you set in Home Assistant come first.
- A printer's problem shows what the printer says, such as a Bambu HMS message.

## 0.28.0

- Choose which 3D printers BRAM watches: BRAM > Configure > 3D printers.
- Fixed: emptying the list in Recommended setup or BRAM's suggestions shared everything in it anyway. Both pages now list what will be shared, with **Leave these out** for anything you do not want.

## 0.27.1

- Clearer wording on the Learning page in Home Assistant, with what each choice does.
- BRAM's History page shows how many nights are noted and any suggestion waiting.

## 0.27.0

- 3D printers, found by themselves: Bambu Lab, Moonraker, OctoPrint, PrusaLink, and similar. Progress, time left, and temperatures on Home; told when a print ends, pauses, or a heater is left on; each print remembered if history is on. Watches only. Off until you turn it on.

## 0.26.0

- BRAM finds problems with Home Assistant by itself: failed integrations, repeating errors, repairs, low batteries, offline devices, stuck sensors, broken automations, old backups, and a full disk. Told once, and again when fixed. Off until you turn it on.
- Configure: "What chat may look up" is now "What BRAM may look into", and "Watch locks, doors, and security" is "What BRAM watches for".

## 0.25.1

- The HACS page explains what BRAM does, how to install and use it, what to ask, and what to try when something is wrong, with pictures.

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
