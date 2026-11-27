# Changes

## Unreleased

## 0.49.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Connect your router: on BRAM's page, **Settings > Router**, with a read-only API key. BRAM then sees every device on every network and VLAN, which Home Assistant alone cannot, and the router's firmware updates, for the security check. OPNsense for now. BRAM only reads, and the router's certificate is pinned. See [Connect your router](docs/security-check.md#connect-your-router).
- The docs say plainly that Home Assistant only sees its own network.

## 0.48.0

Update BRAM in HACS, then restart Home Assistant. The server has no change; updating it too keeps the versions the same.

- The security check now also tells you about a new device on your network, from Home Assistant's own network discovery and any router integration, urgent if everyone is away; a new Zigbee, Z-Wave, Matter, Thread, or HomeKit device paired; Z-Wave locks without S2 security; a router update waiting or guest Wi-Fi on; and apps with protection off or ports open. It first learns what is already there.
- It runs every 10 minutes instead of every hour. See [Security check](docs/security-check.md).

## 0.47.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Teach BRAM a camera. Under **Settings > Cameras**, describe what each camera sees in your own words, with its picture now beside the box. Camera windows on Home and camera messages on your phone ask **Does it matter?**, and on Home you can say what it was, such as "the neighbor in his driveway". Your model gets both with every picture from that camera, so it learns your home. Your answers are under **What you taught BRAM**, each with **Forget**. They teach only; nothing is held back. See [Teach BRAM a camera](docs/cameras.md#teach-bram-a-camera).
- **Not news** is replaced by **Does it matter?**. What you already marked stays under **Not news**.

## 0.46.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- The BRAM camera card is a list, newest first, under Today, Yesterday, and older days: an icon, what happened, the time and camera, your model's words, and Frigate's picture. Choose how many with `count`, 1 to 20.
- Fewer messages: two routine messages at once are one, where it took three. A routine message waits 20 seconds for others coming up with it. Important ones, such as unlocked at night or open while everyone is away, never wait.

## 0.45.1

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Names come from Home Assistant first: the name you gave the entity, then the name you gave its device, then the name Home Assistant shows. BRAM uses a room and type only when there is no real name at all.
- Home no longer shows a card when motion ends.

## 0.45.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Camera messages on your phone have **Not news**, beside **Stop these**. It keeps BRAM quiet about the same kind of thing on that camera in the same Frigate zones, as on Home, and is listed under **Settings > Cameras > Not news**. **Stop these** still stops that kind of message from that camera altogether.

## 0.44.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Camera windows on Home open only for events BRAM told you about, or held for quiet hours. Everything else only updates **Looking at**.
- **Not news**: on a camera window, say an event is not news and what it is, such as "the neighbors' driveway". BRAM stops telling you, on Home and on your phone, about the same kind of thing on that camera in the same Frigate zones, and your model uses what you wrote. Undo under **Settings > Cameras > Not news**.
- The camera docs explain drawing a zone in Frigate over only your own driveway, the surest way to leave out the neighbors.

## 0.43.1

Update the BRAM Server (pull the new image). Home Assistant needs no update.

- Camera windows on Home no longer pile up: a new camera event replaces the last camera window.
- The version shows next to BRAM's name at the top of every page.

## 0.43.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Ask a camera: "Is anyone on the porch?" in chat, Assist, or Telegram. BRAM takes that camera's picture now and your model answers from it. Only cameras with **Describe** on can be asked. See [Ask a camera](docs/cameras.md#ask-a-camera).
- The BRAM camera card for dashboards: Frigate's picture of the latest event with what happened and your model's description. Add a card and search for **BRAM camera**; nothing to install. See [the card](docs/cameras.md#the-bram-camera-card).
- One message instead of several: night and away messages that come due together, such as two windows open when everyone leaves, arrive as one, such as "Everyone I track is away, and these are open or unlocked: My window and Mom's window."

## 0.42.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Cameras, part 4: your own model can describe each event in a sentence or two. Turn on **Describe** for a camera under **Settings > Cameras**; it is off for every camera until you do, and pictures go only to a model on your own network. The words show in the event's window on Home, in **Looking at**, and in a phone message when they are ready in time. A slow model never holds a message back. See [Descriptions](docs/cameras.md#descriptions-from-your-model).

## 0.41.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Cameras: a person at a door that is open or unlocked, and a car. A car is told only if it stays at least 30 seconds in the zones you choose, such as the driveway, so one driving past is left out.
- Set up each camera under **Configure > Watching > Cameras > Set up one camera**: the doors and locks it looks at, which Frigate zones count, picked from Frigate's own zones, and which messages it sends. With zones, a person on the sidewalk is not at your door.
- **Configure > Watching > Cameras** is now a small menu: **What to tell me** and **Set up one camera**.

## 0.40.5

Update the BRAM Server (pull the new image).

- The version on Home turns amber only when the two halves differ in features, such as 0.40 and 0.41, not for a fix on one side.

## 0.40.4

Update the BRAM Server (pull the new image). Home Assistant needs no update, but stay on 0.40 there.

- Home shows what is running at the top: the server's version and BRAM's in Home Assistant, in amber when they differ.
- The cards that say what just happened look like the alert windows, with the room on a tab, and take turns in four places around the brain so they never cover each other.

## 0.40.3

Update BRAM in HACS, then restart Home Assistant. The server has no change; updating it too keeps the versions the same.

- Night can follow your bedtime: under **Configure > Watching > Locks, doors, and windows > Night hours**, choose helpers or sensors that are on while someone is asleep. It is night while any of them is on, as well as during your night hours. See [Night hours](docs/watching.md#night-hours).

## 0.40.2

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Alert windows on Home look like the command center's screens: see-through, cut corners, a glowing edge, corner brackets, a label tab, and a framed picture. The newest is open and older ones fold to their title.
- Fixed: camera windows and **Looking at** had no picture when snapshots are off in Frigate, which is Frigate's default. BRAM now uses the event's thumbnail, or else the camera's latest frame. Phone messages use the thumbnail too.
- Camera names read the way people say them: `RoofCamera` is shown as **Roof camera**.

## 0.40.1

Update BRAM in HACS, then restart Home Assistant. The server has no change; updating it too keeps the versions the same.

- Names: a device name that ends in part of a hardware address, such as `HLK-LD2410 65B2 Motion`, is shown as its room and type, such as **Master Bedroom motion**. The name people use is now used everywhere: messages, the daily summary, problems, settings lists, and BRAM's device page, not only on BRAM's page.

## 0.40.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Camera messages: a person while everyone is away, a person at night, a person Frigate does not know, and packages, for the cameras BRAM watches. Turn them on under **Configure > Watching > Cameras** in Home Assistant. With the Frigate integration installed, each message shows Frigate's picture. The same thing on a camera is told once in 30 minutes, and one person passing several cameras is one message. **Stop these** works per camera. See [Cameras](docs/cameras.md#what-it-tells-you).

## 0.39.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Cameras, part 2: BRAM's server tells Home Assistant about each event on the cameras it watches, ready for camera messages. BRAM adds no camera entities; the Frigate integration already has them. With more than one home, choose which one the cameras belong to under **Settings > Cameras**; no other home is told.

## 0.38.4

Update the BRAM Server (pull the new image). Home Assistant needs no update.

- Fixed: temperature sensors outside, such as a back yard or porch sensor, were counted in the inside average on Home and in History. They now count as outside, and are used for the outside temperature when no weather entity is shared. Past readings are shown the right way too.

## 0.38.3

Update the BRAM Server (pull the new image). Home Assistant needs no update.

- Home is a command center: alerts open as windows over the brain. Red ones (safety, and findings that matter most) stay until you close them; others close by themselves. Each has its buttons, and a camera's has its picture.
- While something needs you, red or amber rings keep going out from the brain. While BRAM thinks about an answer, arcs sweep around it.
- A **Monitors** screen on Home shows each monitor up or down, and a monitor going down opens a window.
- **Looking at** shows the latest picture from your cameras and each camera's last event.
- A short break in reaching Frigate is no longer shown as an error; three failed looks in a row, about 30 seconds, are.

## 0.38.2

Update the BRAM Server (pull the new image). Home Assistant needs no update.

- Fixed: connecting Frigate failed with "could not be reached" after the login worked, because only the first part of Frigate's reply was read. Pictures were cut short the same way.

## 0.38.1

Update the BRAM Server (pull the new image). Home Assistant needs no update.

- Connecting Frigate says exactly what went wrong, such as nothing answering at that address and port, or the login port needing `https://`. An address typed without `http://` or `https://` is tried both ways. See [If it cannot connect](docs/cameras.md#if-it-cannot-connect).

## 0.38.0

Update the BRAM Server (pull the new image). Home Assistant needs no update for this one.

- Cameras, part 1: connect Frigate under **Settings > Cameras** and choose which cameras BRAM watches. It reads only, and never changes Frigate. Frigate's login port works with a view-only Frigate user, and its certificate is pinned. Each watched camera's latest event shows under Settings and in a Cameras card on Home, and a camera Frigate gets no picture from says so. Rules and phone messages come next. See [Cameras](docs/cameras.md).
- The plan now covers what BRAM is: the brain of the house that monitors and protects it. Added: security checks to match and go past Home Generative Agent, rules suggested from what BRAM sees, memory across chats, and cloud models for anyone who wants them.

## 0.37.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- BRAM notices what you do. When you keep hiding the same finding, or are told about it often and never act, it suggests **Stop these** or **Less often** on the review page in Home Assistant, opened from one phone message. Only routine messages, never safety. Nothing changes until an administrator answers.
- Docs: a new guide, [Using BRAM day to day](docs/guide.md); a clearer README; every page checked against BRAM itself, with setting names as you see them; new screenshots of the review page, a closer look on Home, and the History page; and the [camera plan](docs/cameras.md) for your approval.

## 0.36.0

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- Suggestions have their own review page in the Home Assistant app instead of Repairs. Your phone gets a message that opens it, showing the evidence and each setting now and after. Only a Home Assistant administrator can answer.
- **Hide** takes a finding off the list until it happens again; then it is back. Hidden findings are under **Show > Hidden**.

## 0.35.4

Update BRAM in HACS and restart Home Assistant. Update the BRAM Server (pull the new image) too to keep the versions together.

- Weather entities are offered under **Thermostats, temperature, humidity, and weather**, so the outside temperature is easy to share.
- **Back** in BRAM's Devices and Watching menus returns to the main settings.

## 0.35.3

Update the BRAM Server (pull the new image). Update BRAM in HACS too to keep the versions together.

- Home: a printer whose integration is failing is no longer listed under Needs you. Problems with Home Assistant reports failed integrations, if you turned it on.
- Home: Climate says to share a weather entity when it has no outside temperature.

## 0.35.2

Update both: BRAM in HACS (then restart Home Assistant) and the BRAM Server (pull the new image).

- **Locks, doors, windows, and motion** settings are grouped: Locks, Doors and windows, While everyone is away, and Night hours. Your choices are kept.
- Home: **Story** under Needs you opens that finding with its story, not just the Findings list.

## 0.35.1

Update BRAM in HACS and restart Home Assistant. Update the BRAM Server (pull the new image) too to keep the versions together.

- BRAM's blueprints appear in Home Assistant by themselves, under **Settings > Automations & scenes > Blueprints**. Nothing to import. A blueprint you changed is never replaced.

## 0.35.0

Update BRAM in HACS and restart Home Assistant. The server is unchanged, but update it in Portainer too to keep the versions together.

- New watches, each off until you turn it on under **Configure > Watching**:
  - **Locks, doors, windows, and motion**: open at night, open while heating or cooling, and motion while everyone is away.
  - **Temperature and humidity** (new page): too hot, too cold, near freezing, and humid, with your own limits in your home's unit, and sensors to leave out.
- Two blueprints: **BRAM scheduled check** asks BRAM a yes-or-no question on a schedule and tells you only on yes; **BRAM house summary** sends how the home is doing at a time you choose. See [Blueprints](docs/blueprints.md).
- The plan lists more camera features and blueprints.

## 0.34.1

Update both: BRAM in HACS and the BRAM Server (pull the new image).

- Tapping a BRAM phone message opens it on BRAM's page, under Findings, with its story and buttons, instead of Home Assistant's home page.

## 0.34.0

Update both: BRAM in HACS and the BRAM Server (pull the new image).

- Learning reads its quiet nights and door times from BRAM's history instead of keeping its own notes, so there is one record. It needs **Keep history** on. Nights already in history count, so a suggestion can come without another two-week wait. Notes Learning kept before are dropped.
- Docs: 3D printers start switched off.

## 0.33.0

Update both: BRAM in HACS and the BRAM Server (pull the new image).

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
