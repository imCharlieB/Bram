# Every setting

## In Home Assistant

**Settings > Devices & services > BRAM > Configure**

| Page | Setting | Default |
|---|---|---|
| Recommended setup | Phones, suggested devices, night, left open, offline, history, 8 AM summary | All on, if you submit it |
| BRAM's suggestions | What it would add | |
| Add devices quickly | Types and areas to search | |
| What BRAM can see | People, locks and doors, safety, motion, lights, switches and fans, media, voice assistants, climate, anything else | None |
| Which room people are in | A room sensor for each person | Found automatically if possible |
| Phone alerts and quiet hours | Phones that get everything | None |
| | Phones that get safety alerts only | None |
| | Quiet from, quiet until | Off |
| | Daily summary at | Off |
| | Use Telegram and ntfy after 5 unanswered minutes | Off |
| Watch locks and doors | Unlocked at night | Off |
| | Open or unlocked while away | Off |
| | Left open | Off |
| | Offline | Off |
| | Night starts, night ends | 10 PM, 6 AM |
| | Left open minutes | 10 |
| What chat may look up | History of the devices BRAM can see | Off |
| | Home Assistant problems | Off |

Quiet hours here affect only Home Assistant's messages.

## On BRAM's page

| Where | Setting | Default |
|---|---|---|
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
| Profile | Look: Command or Classic, and the Command color, in this browser | Command, cyan |
| | Username, password, signed-in devices | |

These ask for your password again: homes, model, Telegram, ntfy, voice, username, and password.

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
