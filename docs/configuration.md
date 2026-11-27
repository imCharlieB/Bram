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
| Learning | None | Code | [Suggested night hours and left-open time](learning.md) | Built; never uses a model. Patterns and suggested rules are planned |
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

| Page | Has |
|---|---|
| Quick setup | Your phone and the main switches, on one page. Start here |
| Devices | **Suggestions**, **Add by type and room**, **Choose one by one**, **People's rooms**, and **Back** |
| Messages | Phones, quiet hours, daily summary, and the Telegram and ntfy fallback for safety alerts |
| Watching | **Home Assistant and security** ([problems](problems.md) and the [security check](security-check.md)), **Locks, doors, and windows** with night hours ([rules](watching.md)), **Temperature and humidity**, **3D printers** ([printers](printers.md)), and **Back** |
| Server access | What the BRAM Server may read: history, problems, and the security check |
| Learning | [Suggested hours](learning.md), undo, or start over |

On the device page: **Mood**, **Visit**, **Send test message**, and **Allow stopped messages**.

## BRAM's page

| Page | Use it to |
|---|---|
| Home | [What BRAM is doing](home.md), what needs you, chat, and the mood |
| Messages | Set up Telegram, ntfy, and [monitors](monitors.md) |
| Settings | Connect homes; choose the model, personality, and [voice](voice.md) |
| Findings | [What BRAM found](findings.md), whether you were told, and how it ended |
| History | [Turn history on](history.md), see trends, and clean up |
| Log | See what BRAM noticed, sent, and changed |
| Profile | Password, second factor, signed-in devices, and the look |

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

## Moving around

Home Assistant's settings windows have no back button. In BRAM's **Devices** and **Watching** menus, choose **Back** to return to the main settings. Saving a page closes the window; open **Configure** again for the next one.
