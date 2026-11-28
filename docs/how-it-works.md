# How BRAM works

How BRAM is built, how it keeps you safe, and what it stores.

On this page: [How BRAM works](#how-bram-works-1) · [Security](#security) · [What BRAM stores](#what-bram-stores) · [Testing your model](#testing-your-model) · [Development](#development)

## How BRAM works

This describes what is built today. See the [Roadmap](roadmap.md) for what is not.

### The parts

```
Home Assistant                          BRAM Server (Docker)
  BRAM integration  ── encrypted ──►      live state, chat, monitors, config page
   - shares chosen devices                 │            │            │
   - sends home alerts itself              ▼            ▼            ▼
   - Assist agent                       your model   Telegram   Whisper, Piper
   - gate (refuses all actions)         (Ollama)     and ntfy    (optional)
```

| Part | Does |
|---|---|
| Integration | Shares only the devices the owner chose. Sends leak, smoke, and silent-sensor alerts by itself. Passes Assist questions to the server |
| Server | Keeps live state in memory, answers questions, watches other machines, hosts the config page |
| Model | Writes chat answers. Has no tools and no Home Assistant access |

### Pairing

The config page makes a one-time code holding the server certificate's fingerprint and a secret. The integration connects only to a server with that certificate, trades the secret for a token, and uses the token from then on. The server keeps only hashes of codes and tokens.

### Live state

On connecting, the integration sends a snapshot, then each change, and a heartbeat every 30 seconds. After 90 seconds of silence, or a lost connection, every device is *unknown* until a fresh snapshot. Unknown is never treated as safe, locked, closed, dry, or empty. State is not stored on disk.

The server sends back what it believes, for the device page, and answers to Assist questions. It may also ask three read-only questions: history and problems, answered only if the owner turned them on, and pictures of shared devices. The integration refuses anything else.

### Alerts

| | Home alerts | Server messages |
|---|---|---|
| Run in | Home Assistant | BRAM Server |
| About | Leak, smoke, silent safety sensors, locks and doors, lost server | Lost Home Assistant, monitors |
| Reach | HA app | Telegram, ntfy |
| Need a model | No | No |

Wording is fixed. Safety alerts repeat until acknowledged, up to a limit, and ignore quiet hours, limits, and stopped messages. Open alerts survive restarts. A failing channel does not hold up another. Details: [Alerts and messages](watching.md#alerts-and-messages).

### Chat

1. A question arrives from the page, Assist, or Telegram.
2. The server builds a report of live devices, monitors, and recent events. Assist questions get only their own home, without monitors.
3. If the question is about history or problems, plain rules decide what to look up in Home Assistant. The model cannot ask for anything.
4. The model answers in the owner's personality.
5. On the page, matching sensor readings are shown under the answer.

Names and other text in the report are cleaned and marked as data. One question is answered at a time. Conversations are kept in memory for 30 minutes of silence, up to 12 messages, and never written to disk.

### Model

Ollama on the owner's network. Public addresses and Ollama's cloud models are refused. If the model is already loaded, its context size and unload time are kept, so other users are not affected.

### Storage

One SQLite file in the server's data folder holds settings, the hashed login, paired homes, open alerts, and an append-only log. The log holds no conversations. The Telegram token is stored there in plain form, so protect the folder.

Home Assistant stores the connection token, options, and open alerts.

## Security

The rules BRAM must follow are in [Hard rules](../HARD_RULES.md), with what enforces each and how it is tested. This page explains the protections that exist today and their limits. BRAM has not had an outside security review.

### What BRAM can do

It can read the devices you chose, send messages, and talk. **It cannot control anything.** The integration's only service call is sending a notification to phones you chose.

### Protections

| Threat | Protection |
|---|---|
| Someone claims a new server | Setup closes after 15 minutes and works once. Until then, whoever opens the page first can claim it |
| Password guessing | 5 tries per address and 20 in all, then 15 minutes locked. Passwords are salted and hashed with scrypt |
| A stolen password | With the second factor on, signing in also needs a code from your phone. Each code works once, and wrong codes count toward the lockout |
| An unattended browser | Sensitive changes ask for the password again; sessions end after 30 idle minutes or 12 hours |
| A malicious website | Requests from other sites are refused; only the page's own scripts run |
| A stolen session cookie | Hidden from scripts and sent only over encryption; changing the password ends other sessions |
| A fake server or house | Certificate pinning and a secret token in each direction |
| A hijacked server | Can send the integration words and display values, see what it was sent, and read shared devices' history, problems, or the security check if those are turned on. Nothing else |
| Secrets in logs | Only short, grouped summaries leave Home Assistant, with passwords, tokens, accounts, and addresses removed there. Removal cannot catch everything; it is off by default |
| A tricked model | It has no tools, and device names and other text are marked as data |
| Data leaving home | Models, speech, and monitors are on the local network, unless you choose a cloud model. Then only chat goes to it, and camera pictures only with their own switch; BRAM never falls back to the cloud by itself. Telegram is off by default |
| A stranger messaging the bot | Only the linked Telegram account is answered |
| Someone on the network reading ntfy | Topics are random and everything else is refused, but traffic is not encrypted |

### Limits

- Whoever controls the server's machine, its volume, or its backups controls BRAM.
- A compromised Home Assistant controls everything in it, with or without BRAM.
- The page's self-made certificate means a browser cannot tell it from an impostor on your network.
- Someone on your network can trigger the sign-in lockout. Open sessions keep working.
- Whisper, Piper, ntfy, and Ollama have no encryption or login here. Keep their ports on your own network.
- Anyone who can use a voice assistant set to BRAM can ask about that home.
- The second factor is off until you turn it on. Its key is stored unencrypted in the data folder, as every server that checks these codes must keep it.

### Reporting a problem

Please use [GitHub's private security report](https://github.com/imCharlieB/Bram/security/advisories/new) if it is available, rather than a public issue.

## What BRAM stores

BRAM has no account, cloud service, or telemetry.

### On the BRAM Server

One SQLite file, plus a key and certificate, in the data folder.

| Stored | Why | Protected by |
|---|---|---|
| Login | Sign in | Password is salted and hashed |
| Second factor, if on | Sign in | Key is **plain**; recovery codes are hashed |
| Paired homes | Recognize your Home Assistant | Tokens are hashed |
| Settings, monitors | | |
| Telegram token and account number | Send messages | **Plain**; protect the folder |
| With [memory](chat.md#memory) on: what people asked BRAM to remember, with who and when, and each person's last 12 messages | Remember; carry a conversation over | Until deleted under Settings > Memory, or a week untouched for a conversation. Nothing with memory off |
| Router address, API key and secret, and certificate fingerprint | Read the router | **Plain**; protect the folder. Use a key whose user can only read |
| The router's device list and firmware status | Show them; tell Home Assistant's security check | In memory only; read again every 5 minutes |
| Frigate address, username, password, and certificate fingerprint; which cameras are watched | Read cameras | **Plain**; protect the folder. Use a Frigate user that can only view |
| What each camera sees, in your words, and your last 200 answers to Does it matter? | Teach your model | Until you forget them under Settings > Cameras |
| Each watched camera's last 20 events and latest picture, and your model's words for the last 200 events | Show them | In memory only; gone on restart, or when the camera is turned off |
| ntfy topics | Send messages | **Plain** |
| Open and past alerts | Reminders after a restart | |
| [Findings](guide.md#findings) | What was found, told, and ended | |
| Learned nights from before 0.34 | Sent by older versions of BRAM in Home Assistant; no longer added, since Learning reads history | |
| [History](guide.md#history-and-trends), if on | Trends | **Plain**; off until you turn it on |
| [Prints](watching.md#3d-printers), if history is on | Printer, file, result, length | |
| Log | What happened and why | Entries cannot be changed or deleted through BRAM |

The log holds events such as connections, sign-ins, alerts, and messages sent, including device names. It has no size limit yet.

### In Home Assistant

The connection token, BRAM's options, open alerts, stopped messages, which device types it has seen, and notes waiting for the server. If the security check is on, the ids of known administrators and tokens (never the tokens), the devices already seen on your network and paired by radio, and the findings already told. If [learning](watching.md#learning) is on, the nights and door times the server sent, for the last 60 days. BRAM's [blueprints](chat.md#blueprints), as files under `blueprints/automation/bram`; they do nothing until you make an automation from one. Home Assistant's own history records the lines on BRAM's device page like any other sensor.

### Kept only in memory

| What | Until |
|---|---|
| Live device state | The connection drops or the server restarts |
| Pictures of people and media | Restart, or 60 newer ones |
| Conversations, with memory off | Cleared, 30 idle minutes, sign-out, or restart |
| Recordings | Turned into text |
| Sessions | Sign-out, expiry, or restart |

### What leaves your network

| Feature | Sends | Default |
|---|---|---|
| HA app messages | Alert text, through Home Assistant's push service | When you choose phones |
| Telegram | Messages, and chat if turned on | Off |
| A cloud model, if you choose one | Your questions, what BRAM shares about your home to answer them, and what you asked it to remember that fits; camera pictures only with their own switch | Off |
| Everything else | Nothing | |

Whisper and Piper download their models when first started. Docker and HACS download updates.

### Deleting it

Remove the integration in Home Assistant, then delete the stack and its `bram-data` volume. To forget one home, use **Remove** under **Settings > Homes**; its log entries remain.

## Testing your model

`bram-bench` checks an Ollama model's tool use, safety behavior, vision, recall, and speed. It uses an invented house and never contacts Home Assistant. Set up first with [Development](how-it-works.md#development).

    bram-bench --url http://HOST:11434                  # list installed models
    bram-bench --url http://HOST:11434 --model MODEL

| Option | Meaning | Default |
|---|---|---|
| `--url` | Ollama address | required |
| `--model` | Model to test; omit to list models | |
| `--context` | Context size in tokens | 8192 |
| `--timeout` | Seconds allowed per request | 180 |
| `--repeat` | Times to run each test | 3 |
| `--think` | `on`, `off`, or the model's `default` | default |
| `--keep-loaded` | Never unload the model | unloads after 30 minutes idle |
| `--out` | Save full results as JSON | |

**Sharing Ollama with something else?** A different context size reloads the model, and the default unload time replaces the current one. Check `http://HOST:11434/api/ps`, then match `--context`, and add `--keep-loaded` if the model is set never to unload.

Exit code 0 means everything passed, 1 means a test failed, 2 means the benchmark could not run.

A perfect score is a smoke test. It does not let a model control anything. Repeated prompts may be cached, which inflates prompt speed.

## Development

Needs Python 3.13 or later.

    python -m venv .venv
    .venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -e "server[dev]"

Checks, all run by CI:

    ruff check .
    pytest server/tests
    python scripts/rule_coverage.py
    python scripts/docs_check.py
    python scripts/version_check.py

The integration tests need Python 3.14 and Linux (or CI):

    pip install pytest-homeassistant-custom-component hassil home-assistant-intents
    pip install -e server
    python -m pytest ha_tests -o asyncio_mode=auto

To redraw the logo: `pip install pillow`, then `python scripts/make_brand.py BOLD_FONT.ttf`.

`rule_coverage.py` reports hard rules without a tagged test and, with `--release`, fails if any remain. It cannot judge whether a test truly proves its rule; reviewers must. See [Safety rules](../HARD_RULES.md).
