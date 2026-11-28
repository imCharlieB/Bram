# Settings

Every setting, and how to choose what BRAM can see.

On this page: [Every setting](#every-setting) · [Configuration](#configuration) · [Devices](#devices)

## Every setting

### In Home Assistant

**Settings > Devices & services > BRAM > Configure**

| Page | Setting | Default |
|---|---|---|
| Quick setup | Phones that get everything | Your phone, if there is only one |
| | Leave these out: suggested devices not to share | None |
| | Unlocked at night, left open, offline, problems with Home Assistant, history of what it can see, daily summary at 8 AM | All on, if you submit it |
| | Tell me about 3D printers, if any are found | On, if you submit it. Each printer still starts off |
| Devices > Suggestions | What it would add, and what to leave out | |
| Devices > Add by type and room | Look for: types; only in these areas | People, locks and doors, safety, motion; everywhere |
| Devices > Choose one by one | People, locks and doors, safety sensors, motion and presence, lights, switches and fans, media players and speakers, voice assistants, thermostats, temperature, humidity, and weather, water heaters, valves, and appliances, anything else | None |
| Devices > People's rooms | Override the sensor BRAM found | Usually not needed |
| Messages | Phones that get everything | None |
| | Phones that get safety alerts only | None |
| | Quiet from, quiet until | Off |
| | Daily summary at | Off |
| | Also use Telegram and ntfy if nobody answers a safety alert in 5 minutes | Off |
| Watching > Home Assistant and security | Watch Home Assistant for problems | Off; on in Quick setup |
| | Run the security check every hour | Off |
| Watching > Cameras > What to tell me | A person while everyone is away, at an open or unlocked door, or at night; a person Frigate does not know; a package; a car | Off |
| | Not again on the same camera for | 30 minutes |
| Watching > Cameras > Set up one camera | Doors and locks it looks at; Frigate zones that count; its messages | None; whole picture; all |
| Watching > Locks, doors, and windows: Locks | Unlocked at night | Off; on in Quick setup |
| | A lock or door sensor goes offline | Off; on in Quick setup |
| Doors and windows | Left open | Off; on in Quick setup |
| | Left open means this many minutes | 10 |
| | Count doors, count windows, count garage doors and gates | On |
| | Open at night | Off |
| | Open while heating or cooling | Off |
| While everyone is away | A lock unlocked, or a door or window open | Off |
| | Motion | Off |
| Night hours | Night starts, night ends | 10 PM, 6 AM |
| | Friday and Saturday night starts, ends | Empty: same as other nights |
| | Also night while any of these is on: helpers or sensors that are on while someone is asleep | None |
| Watching > Temperature and humidity | Too hot, too cold, near freezing, humid | Off |
| | Too hot above, too cold below, near freezing below | 85, 55, 38 °F (29, 13, 3 °C) |
| | Humid above | 70% |
| | Leave out these sensors | None |
| Watching > 3D printers | Watch 3D printers | Off; on in Quick setup if any are found |
| | One switch for each printer | Off: only printers you switch on are watched or shown |
| Server access | History of shared devices | Off; on in Quick setup |
| | Home Assistant problems | Off |
| | Security check | Off |
| Learning | Learning is on | Off |
| | Undo the last change I approved, erase what BRAM has learned | |
| | Nightly checks you approved, each to keep or remove | None |
| | Told when left on while everyone is away, each to keep or remove | None |

Quiet hours here affect only Home Assistant's messages.

### On BRAM's page

**Settings** and **Messages** show one section at a time, with tabs across the top.

| Where | Setting | Default |
|---|---|---|
| History | Keep history (**Start keeping history** while it is off) | Off |
| | Most space to use | 2048 MB |
| Home | Mood | Professional |
| Messages > Monitors | What to watch | None |
| Messages > Telegram | Turned on, bot token, linked account | Off |
| | Let me chat here | Off |
| | Quiet hours | Off |
| Messages > ntfy | Turned on, addresses, topic | Off |
| | Quiet hours | Off |
| Settings > Homes | Connected Home Assistants | None |
| Settings > Model | Ollama address, model, context size | None, 8192 |
| Settings > Personality | Mode, custom style | Professional |
| Settings > Voice | Hearing, speaking, voice name | Off |
| Settings > Memory | On or off; what BRAM remembers, each with Change and Delete; Forget everything | Off |
| Settings > Router | OPNsense address, API key and secret | None |
| Settings > Cameras | Frigate address, and a Frigate username and password for its login port | None |
| | Watch, for each camera | Off |
| | Describe, for each watched camera: its event pictures go to your own model | Off |
| Settings > Cameras, each camera | Describe what it sees, in your words, for your model | Empty |
| Settings > Cameras > What you taught BRAM | Your answers to Does it matter?, each with Forget | None |
| Settings > Cameras > Not news | What you said was not news before 0.47, each with Tell me again | None |
| Profile | Look: Command or Classic, and the Command color, in this browser | Command, cyan |
| | Username, password, signed-in devices | |

These ask for your password again: homes, model, Telegram, ntfy, voice, connecting or disconnecting Frigate or the router, turning Describe or memory on or off, forgetting everything, username, and password.

### Limits that cannot be changed

| Limit | Value |
|---|---|
| Safety reminders | 11, over about 5 hours |
| Routine messages a day | 10 each from Home Assistant, Telegram, and ntfy; 20 for locks and doors |
| Monitors | 20, checked every minute |
| Chat message | 2,000 characters |
| Recording | 30 seconds |
| Session | 30 minutes idle, 12 hours in all |
| Wrong passwords | 5 per address, 20 in all, per 15 minutes |

## Configuration

How to configure each part, and what each uses. For a plain list, see [Every setting](settings.md#every-setting).

### Models and engines

| Job | Provider | Default | Purpose | Status |
|---|---|---|---|---|
| Chat | Ollama | None; you choose | Answers on the page, Assist, and Telegram | Built |
| Chat | OpenAI, Anthropic, Google Gemini, or another OpenAI-compatible service | Off | Same, for anyone without their own model | Built; off until you choose one |
| Alerts | None | Fixed text | Leak, smoke, locks, doors, monitors, summary | Built; never uses a model |
| History and problems | None | Code | Looks up and measures; chat words the answer | Built |
| Hearing | Whisper (Wyoming) | `base-int8`, English | Hold to talk, Telegram voice notes | Built |
| Speaking | Piper (Wyoming) | `en_US-lessac-medium` | Spoken answers | Built |
| Vision | The chat model, if it reads pictures | Off for each camera | Describe camera events, answer questions about a camera | Built; cloud models need their own picture switch |
| Memory search | Ollama embedding model | None | Find memories by meaning | Planned; keyword search today |
| Summaries of long chats | Same as chat | | Keep long chats short | Planned |
| Learning | None | Code | [Suggested night hours, left-open time, nightly checks, and things left on while away](watching.md#learning) | Built; never uses a model |
| Backup model | Another local Ollama model | None | When the first fails | Planned |

#### Models tried

| Model | Where | Tools | Vision | Recall | Speed | Notes |
|---|---|---|---|---|---|---|
| `gemma4:26b-a4b-it-qat` | Apple silicon laptop, 32 GB | 21/21 | 9/9 | 6/6 | About 60 tokens/s; chat answers in about 1 s | Small smoke test; see [Testing your model](how-it-works.md#testing-your-model) |

Any local Ollama chat model can be tried. Bigger models usually follow instructions better. Test yours and compare.

#### Chat details

| Setting | Value |
|---|---|
| Context | Your setting, or the size the model is already loaded with |
| Creativity (temperature) | 0.8 |
| Thinking | Off |
| Longest answer | 600 tokens |
| Remembered messages | 12, for 30 idle minutes |
| Devices described | 60, the most relevant first |
| Questions at once | 1 |
| Time allowed | 90 seconds; 60 from Assist |

### Home Assistant

**Settings > Devices & services > BRAM > Configure**

| Page | Has |
|---|---|
| Quick setup | Your phone and the main switches, on one page. Start here |
| Devices | **Suggestions**, **Add by type and room**, **Choose one by one**, **People's rooms**, and **Back** |
| Messages | Phones, quiet hours, daily summary, and the Telegram and ntfy fallback for safety alerts |
| Watching | **Home Assistant and security** ([problems](watching.md#problems-with-home-assistant) and the [security check](watching.md#security-check)), **Locks, doors, and windows** with night hours ([rules](watching.md#how-bram-watches-your-home)), **Temperature and humidity**, **3D printers** ([printers](watching.md#3d-printers)), and **Back** |
| Server access | What the BRAM Server may read: history, problems, and the security check |
| Learning | [Suggested hours](watching.md#learning), undo, or start over |

On the device page: **Mood**, **Visit**, **Send test message**, and **Allow stopped messages**.

### BRAM's page

| Page | Use it to |
|---|---|
| Home | [What BRAM is doing](guide.md#brams-home-page), what needs you, chat, and the mood |
| Messages | Set up Telegram, ntfy, and [monitors](watching.md#monitors-1) |
| Settings | Connect homes; choose the model, personality, and [voice](chat.md#voice) |
| Findings | [What BRAM found](guide.md#findings), whether you were told, and how it ended |
| History | [Turn history on](guide.md#history-and-trends), see trends, and clean up |
| Log | See what BRAM noticed, sent, and changed |
| Profile | Password, second factor, signed-in devices, and the look |

### Docker

| Service | Port | Needed | Reach it from |
|---|---|---|---|
| bram | 8765 | Yes | Home Assistant, your browser |
| ntfy | 2586 | No | Your phone |
| whisper | 10300 | No | BRAM; Home Assistant if you use it there |
| piper | 10200 | No | BRAM; Home Assistant if you use it there |

| Compose file | Contains |
|---|---|
| `compose.yaml` | bram, ntfy |
| `compose.voice.yaml` | whisper, piper |
| `compose.full.yaml` | All four |

| Variable | Default |
|---|---|
| `BRAM_WHISPER_MODEL` | `base-int8` |
| `BRAM_WHISPER_LANGUAGE` | `en` |
| `BRAM_PIPER_VOICE` | `en_US-lessac-medium` |

### Moving around

Home Assistant's settings windows have no back button. In BRAM's **Devices** and **Watching** menus, choose **Back** to return to the main settings. Saving a page closes the window; open **Configure** again for the next one.

## Devices

BRAM sees only the devices you choose. Choosing one does not let BRAM control it.

### A device's other readings

For a shared thermostat, fan, water heater, valve, vacuum, mower, or humidifier, BRAM also reads the other sensors on the same device, such as hot water left or compressor health. Chat knows them. Unknown values and text that is not meant to be read are left out.

### Renamed in Home Assistant

If you change an entity's ID in Home Assistant, BRAM follows it.

### Deleted in Home Assistant

An entity you delete in Home Assistant is dropped from what BRAM watches, and noted in Findings. One that was already gone when BRAM started is listed in Findings for you to remove.

### Turned off in Home Assistant

An entity you disable in Home Assistant is no longer watched or shown, even if it is shared, and comes back if you enable it again. Findings lists each one, so a safety sensor is not dropped without you knowing.

### Names

BRAM uses Home Assistant's names everywhere: messages, the daily summary, BRAM's page, its settings lists, and its device page. In this order: the name you gave the entity in Home Assistant; the name you gave its device, with the entity's own part, such as **MasterBedMotion Motion**; then the name Home Assistant shows. Only when none of those is a real name, just a serial number or part of a hardware address, such as `HLK-LD2410 65B2 Motion`, does BRAM say its room and type instead, such as **Master Bedroom motion**. To choose a name, rename the device or entity in Home Assistant.

### Devices > Suggestions

**Configure > Devices > Suggestions** lists what matters most and BRAM cannot see yet: people, locks and doors, safety sensors, and a motion sensor for each area without one. Put anything you do not want under **Leave these out**, and **Submit**. Nothing is shared until you do. These come from simple rules, not a model.

### Devices > Add by type and room

**Settings > Devices & services > BRAM > Configure > Devices > Add by type and room**

1. Under **Look for**, choose types, such as locks and doors. People, locks and doors, safety sensors, and motion are chosen to start.
2. Under **Only in these areas**, choose areas, or leave empty for the whole home.
3. BRAM lists what it found. Put anything you do not want under **Leave these out**, and **Submit**.

It adds to what you already chose. It skips hidden devices, settings and health readings, and extra zones of the same presence sensor. Devices you add to Home Assistant later are not shared until you add them here.

### Choose one by one

**Configure > Devices > Choose one by one** lists every choice by type. Remove one there to stop sharing it; its line disappears from BRAM's device page.

The **Devices** menu ends with **Back**, which returns to BRAM's main settings.

### What BRAM understands

| Type | Home Assistant devices | BRAM says |
|---|---|---|
| People | `person` | home, away |
| Locks | `lock` | locked, unlocked |
| Doors and windows | Door, window, opening, and garage door sensors; door, garage, gate, and window covers | open, closed |
| Safety sensors | Moisture, smoke, carbon monoxide, gas, heat, safety, and tamper sensors | leak or dry; detected or clear |
| Motion | Motion, occupancy, presence, and moving sensors | detected, clear |
| Lights | `light` | on, off |
| Switches and fans | `switch`, `fan` | on, off |
| Media players and speakers | `media_player` | on, off or idle |
| Voice assistants | `assist_satellite` | in use, idle |
| Thermostats, temperature, humidity, and weather | `climate`, temperature and humidity sensors, and `weather` | The mode and readings. A shared weather entity, such as `weather.home`, gives the outside temperature on Home and in History |
| Water heaters, valves, and appliances | `water_heater`, `valve`, `vacuum`, `lawn_mower`, `humidifier` | Its state; a valve is open or closed, and a water heater shows its mode and setting |
| Anything else | Other sensors, alarm panels, sirens, updates, helpers, and more; choose one by one | Its state as Home Assistant shows it; no alerts |

"How long" restarts when Home Assistant restarts. BRAM also sees, for shared devices only: their room, how long they have been that way, brightness, position, battery, what a media player is playing and how loud, what a thermostat is doing, and the picture Home Assistant shows for a person or media player. It never gets a person's coordinates, or pictures from outside Home Assistant. Pictures are kept in memory only.

Asking chat about the past, with **History of shared devices** on, covers everything here except thermostats and readings, such as temperatures. [BRAM's own history](guide.md#history-and-trends) keeps readings too. A state BRAM does not recognize is *unknown*.

### Location

| What | Where it comes from |
|---|---|
| A device's room and floor | Its area in Home Assistant; set areas and floors there |
| Whether a room is occupied | The motion and presence sensors in that area. Clear only if all of them say so |
| The room a person is in | Found by itself: room sensors on their devices, or a sensor with their name whose value is one of your areas, such as *Alex Room*. **Configure > Devices > People's rooms** overrides it |
| A named place, such as Work | The person's zone in Home Assistant |

Coordinates are never shared. If a room is not known, BRAM says only home or away. On Home, the **House** screen shows your rooms from Home Assistant's areas.

### What to add first

1. **Everyone who lives there.** Otherwise "away" is wrong.
2. **Outside doors and locks**, for [watching](watching.md#how-bram-watches-your-home).
3. **Safety sensors**, for alerts.
4. **Motion sensors and lights**, so chat answers well and future learning has something to learn from.

### The device page

**BRAM Server** shows the connection. Each chosen device has a line with what the server believes. *Unavailable* means the server is not connected.

**Visit** opens BRAM's page. **Mood** changes BRAM's [personality](chat.md#personality).

| Button | Does |
|---|---|
| Send test message | Sends to your chosen phones |
| Allow stopped messages | Undoes every **Stop these** and **Less often**, and what BRAM learned by itself about telling you less |
