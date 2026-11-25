# What BRAM stores

BRAM has no account, cloud service, or telemetry.

## On the BRAM Server

One SQLite file, plus a key and certificate, in the data folder.

| Stored | Why | Protected by |
|---|---|---|
| Login | Sign in | Password is salted and hashed |
| Paired homes | Recognize your Home Assistant | Tokens are hashed |
| Settings, monitors | | |
| Telegram token and account number | Send messages | **Plain**; protect the folder |
| ntfy topics | Send messages | **Plain** |
| Open and past alerts | Reminders after a restart | |
| Log | What happened and why | Entries cannot be changed or deleted through BRAM |

The log holds events such as connections, sign-ins, alerts, and messages sent, including device names. It has no size limit yet.

## In Home Assistant

The connection token, BRAM's options, open alerts, stopped messages, and which device types it has seen. If the hourly security check is on, the ids of known administrators and tokens (never the tokens) and the findings already told. If [learning](learning.md) is on, one line for each of the last 60 days. Home Assistant's own history records the lines on BRAM's device page like any other sensor.

## Kept only in memory

| What | Until |
|---|---|
| Live device state | The connection drops or the server restarts |
| Pictures of people and media | Restart, or 60 newer ones |
| Conversations | Cleared, 30 idle minutes, sign-out, or restart |
| Recordings | Turned into text |
| Sessions | Sign-out, expiry, or restart |

## What leaves your network

| Feature | Sends | Default |
|---|---|---|
| HA app messages | Alert text, through Home Assistant's push service | When you choose phones |
| Telegram | Messages, and chat if turned on | Off |
| Everything else | Nothing | |

Whisper and Piper download their models when first started. Docker and HACS download updates.

## Deleting it

Remove the integration in Home Assistant, then delete the stack and its `bram-data` volume. To forget one home, use **Remove** under **Settings > Homes**; its log entries remain.
