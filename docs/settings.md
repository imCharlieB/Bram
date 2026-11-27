# Every setting

## In Home Assistant

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
| Watching > Cameras | A person while everyone is away, a person at night, a person Frigate does not know, a package | Off |
| | Not again on the same camera for | 30 minutes |
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

Quiet hours here affect only Home Assistant's messages.

## On BRAM's page

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
| Settings > Cameras | Frigate address, and a Frigate username and password for its login port | None |
| | Watch, for each camera | Off |
| Profile | Look: Command or Classic, and the Command color, in this browser | Command, cyan |
| | Username, password, signed-in devices | |

These ask for your password again: homes, model, Telegram, ntfy, voice, connecting or disconnecting Frigate, username, and password.

## Limits that cannot be changed

| Limit | Value |
|---|---|
| Safety reminders | 11, over about 5 hours |
| Routine messages a day | 10 each from Home Assistant, Telegram, and ntfy; 20 for locks and doors |
| Monitors | 20, checked every minute |
| Chat message | 2,000 characters |
| Recording | 30 seconds |
| Session | 30 minutes idle, 12 hours in all |
| Wrong passwords | 5 per address, 20 in all, per 15 minutes |
