# How BRAM works

This describes what is built today. See the [Roadmap](roadmap.md) for what is not.

## The parts

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

## Pairing

The config page makes a one-time code holding the server certificate's fingerprint and a secret. The integration connects only to a server with that certificate, trades the secret for a token, and uses the token from then on. The server keeps only hashes of codes and tokens.

## Live state

On connecting, the integration sends a snapshot, then each change, and a heartbeat every 30 seconds. After 90 seconds of silence, or a lost connection, every device is *unknown* until a fresh snapshot. Unknown is never treated as safe, locked, closed, dry, or empty. State is not stored on disk.

The server sends back what it believes, for the device page, and answers to Assist questions. It may also ask three read-only questions: history and problems, answered only if the owner turned them on, and pictures of shared devices. The integration refuses anything else.

## Alerts

| | Home alerts | Server messages |
|---|---|---|
| Run in | Home Assistant | BRAM Server |
| About | Leak, smoke, silent safety sensors, locks and doors, lost server | Lost Home Assistant, monitors |
| Reach | HA app | Telegram, ntfy |
| Need a model | No | No |

Wording is fixed. Safety alerts repeat until acknowledged, up to a limit, and ignore quiet hours, limits, and stopped messages. Open alerts survive restarts. A failing channel does not hold up another. Details: [Alerts and messages](messages.md).

## Chat

1. A question arrives from the page, Assist, or Telegram.
2. The server builds a report of live devices, monitors, and recent events. Assist questions get only their own home, without monitors.
3. If the question is about history or problems, plain rules decide what to look up in Home Assistant. The model cannot ask for anything.
4. The model answers in the owner's personality.
5. On the page, matching sensor readings are shown under the answer.

Names and other text in the report are cleaned and marked as data. One question is answered at a time. Conversations are kept in memory for 30 minutes of silence, up to 12 messages, and never written to disk.

## Model

Ollama on the owner's network. Public addresses and Ollama's cloud models are refused. If the model is already loaded, its context size and unload time are kept, so other users are not affected.

## Storage

One SQLite file in the server's data folder holds settings, the hashed login, paired homes, open alerts, and an append-only log. The log holds no conversations. The Telegram token is stored there in plain form, so protect the folder.

Home Assistant stores the connection token, options, and open alerts.
