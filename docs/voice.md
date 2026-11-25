# Voice

Optional. Hold a button to talk to BRAM on its home page, and let it read its answers aloud. It uses Whisper to hear and Piper to speak, through the Wyoming protocol that Home Assistant also uses. Everything stays on your network.

## Choose where they run

| You have | Do this |
|---|---|
| Nothing yet, and want one stack | Use `compose.full.yaml` instead of `compose.yaml` |
| Nothing yet, and want a separate stack | Add a stack from `compose.voice.yaml` |
| Whisper or Piper already, with Wyoming | Use their addresses; add nothing |

In Portainer these are the **Compose path** of a stack from `https://github.com/imCharlieB/Bram`. To move to the full stack, keep the same stack name so your data volume is kept, and redeploy with the new path. If Portainer will not change the path, add the voice stack instead.

Their models are downloaded on first start, so allow a few minutes. Optional stack settings (environment variables):

| Setting | Meaning | Default |
|---|---|---|
| `BRAM_WHISPER_MODEL` | Bigger hears better but slower: `tiny-int8`, `base-int8`, `small-int8` | `base-int8` |
| `BRAM_WHISPER_LANGUAGE` | Language you speak | `en` |
| `BRAM_PIPER_VOICE` | Voice | `en_US-lessac-medium` |

## Set it up

On BRAM's page, **Settings > Voice**:

| Field | With `compose.full.yaml` | Separate stack or your own |
|---|---|---|
| Hearing (Whisper) | `whisper:10300` | `SERVER:10300` |
| Speaking (Piper) | `piper:10200` | `SERVER:10200` |
| Voice name | Leave empty for the default | Leave empty for the default |

**Save**, then **Test voice**. Either one can be left empty.

## Use it

On the home page, hold **Hold to talk** (or hold Space or Enter on it), speak, and let go. Check **Speak answers** to hear them. Your browser asks for the microphone the first time.

- BRAM listens only while you hold the button, for up to 30 seconds.
- Sound is not stored. What you said is handled like typed text.
- A voice never approves anything.
- A close microphone works far better than one across a room with a TV on.

Home Assistant can use the same Whisper and Piper: add the **Wyoming Protocol** integration twice, with ports 10300 and 10200. A small Whisper model may hear worse than Home Assistant Cloud across a room, so compare before switching.

## Security

Wyoming has no login or encryption. Keep ports 10300 and 10200 on your own network and never forward them.

## Problems

| Problem | Try |
|---|---|
| No microphone button | Set up Hearing in Settings |
| Microphone was not allowed | Allow it in the browser for BRAM's page; use `https` |
| The speech server did not answer | Wait for the first download; check the address and port |
| Slow or wrong words | Try another `BRAM_WHISPER_MODEL`; move closer |
