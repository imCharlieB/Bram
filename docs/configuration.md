# Configuration

How to configure each part, and what each uses. For a plain list, see [Every setting](settings.md).

## Models and engines

| Job | Provider | Default | Purpose | Status |
|---|---|---|---|---|
| Chat | Ollama | None; you choose | Answers on the page, Assist, and Telegram | Built |
| Chat | OpenAI-compatible, OpenAI, Anthropic, Gemini | | Same | Planned, off by default |
| Alerts | None | Fixed text | Leak, smoke, locks, doors, monitors, summary | Built; never uses a model |
| History and problems | None | Code | Looks up and measures; chat words the answer | Built |
| Hearing | Whisper (Wyoming) | `base-int8`, English | Hold to talk, Telegram voice notes | Built |
| Speaking | Piper (Wyoming) | `en_US-lessac-medium` | Spoken answers | Built |
| Vision | Ollama model with vision | Same as chat | Describe Frigate events | Planned |
| Memory search | Ollama embedding model | None | Find memories by meaning | Planned; keyword search without it |
| Summaries of long chats | Same as chat | | Keep long chats short | Planned |
| Learning | Code, worded by the chat model | | Suggested times and patterns | Planned |
| Backup model | Another local Ollama model | None | When the first fails | Planned |

### Models tried

| Model | Where | Tools | Vision | Recall | Speed | Notes |
|---|---|---|---|---|---|---|
| `gemma4:26b-a4b-it-qat` | Apple silicon laptop, 32 GB | 21/21 | 9/9 | 6/6 | About 60 tokens/s; chat answers in about 1 s | Small smoke test; see [Testing your model](benchmark.md) |

Any local Ollama chat model can be tried. Bigger models usually follow instructions better. Test yours and compare.

### Chat details

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

## Home Assistant

**Settings > Devices & services > BRAM > Configure**

| Page | Use it to |
|---|---|
| Recommended setup | Turn on what most people want, on one page |
| BRAM's suggestions | Share the important things BRAM cannot see yet |
| Add devices quickly | Share many at once, by type and **area** |
| What BRAM can see | Add or remove one by one |
| Phone alerts and quiet hours | Choose phones, quiet hours, daily summary, and the fallback |
| Watch locks and doors | Choose rules, night hours, and left-open time |
| What chat may look up | Allow history and problems |

On the device page: **Mood**, **Visit**, **Send test message**, and **Allow stopped messages**.

## BRAM's page

| Page | Use it to |
|---|---|
| Home | See how things are, chat, and change the mood |
| Messages | Set up Telegram, ntfy, and [monitors](monitors.md) |
| Settings | Connect homes; choose the model, personality, and [voice](voice.md) |
| Log | See what BRAM noticed, sent, and changed |
| Profile | Change your login and sign out other devices |

## Docker

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
