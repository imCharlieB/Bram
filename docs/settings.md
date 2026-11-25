# Every setting

## In Home Assistant

**Settings > Devices & services > BRAM > Configure**

| Page | Setting | Default |
|---|---|---|
| BRAM's suggestions | What it would add | |
| Add devices quickly | Types and areas to search | |
| What BRAM can see | People, locks and doors, leak and smoke, motion, lights | None |
| Phone alerts and quiet hours | Phones that get alerts | None |
| | Quiet from, quiet until | Off |
| | Use Telegram and ntfy after 5 unanswered minutes | Off |
| Watch locks and doors | Unlocked at night | Off |
| | Open or unlocked while away | Off |
| | Left open | Off |
| | Offline | Off |
| | Night starts, night ends | 10 PM, 6 AM |
| | Left open minutes | 10 |

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
| Profile | Username, password, signed-in devices | |

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
