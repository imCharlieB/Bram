# BRAM Server

The server watches and, if you turn it on, sends messages. It controls nothing. It does not replace certified alarms.

Everyday setup happens on the config page. These commands are for running the server and for rescue.

    bram-server [--data DIR] COMMAND

| Command | Does |
|---|---|
| `run` | Start the server |
| `pair --name NAME` | Print a one-time code for a Home Assistant, valid 10 minutes |
| `reset-login` | Remove a forgotten config page login. Restart the server, then set it up again |
| `houses` | List paired houses |
| `unpair HOUSE_ID` | Remove a house |
| `log [HOUSE_ID]` | Print the audit log, including what BRAM noticed and sent. The ID is optional with one house |

| Option | Meaning | Default |
|---|---|---|
| `--data` | Where the key, certificate, and database live; give it before the command | `data` |
| `--host` | Address to listen on (`run`) | all |
| `--port` | Port to listen on (`run`) | 8765 |
| `--json` | Print full records (`log`) | off |
| `--name` | Your name for the house (`pair`) | required |

The image is built by GitHub for 64-bit Intel/AMD machines; `edge` is the latest. To build it yourself, use `docker compose -f compose.yaml -f compose.build.yaml up -d --build`.

To set it up, see [Installing](installation.md) and [Alerts and messages](messages.md).

## Config page

| Page | For |
|---|---|
| Home | How everything is right now, and [chat](chat.md) |
| Messages | Telegram, ntfy, and monitors |
| Settings | Homes, model, personality, and [voice](voice.md) |
| Log | Everything BRAM recorded, with filters |
| Profile | Username, password, and signed-in devices |

The page cannot control anything, change what BRAM may do, or approve actions. **Try it** sends your model one invented sentence and nothing about your home.

- Only models on your own network are accepted, and models that Ollama runs in the cloud are refused.
- If the model is already loaded, BRAM keeps its context size and unload time so other users are not affected.
- Pairing, removing a home, changing the model, and changing the username or password ask for the password again.
- Sessions end after 30 minutes idle or 12 hours.
- Five wrong passwords from one address, or 20 in all, lock sign-in for 15 minutes. Resetting the login signs everyone out.
- Alerts use fixed wording, so personality affects only chat and **Try it**.

## Security

- Traffic is encrypted. The integration accepts only the server that made the code.
- Codes and tokens are stored on the server as hashes. Home Assistant stores its token in its own configuration.
- Keep the data folder private: it contains the server's key. Deleting it means pairing again.
- Do not expose the port to the internet.
