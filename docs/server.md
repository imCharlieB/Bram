# BRAM Server

In this version the server watches and logs. It sends no messages and controls nothing. It does not replace certified alarms.

Everyday setup happens on the config page. These commands are for running the server and for rescue.

    bram-server [--data DIR] COMMAND

| Command | Does |
|---|---|
| `run` | Start the server |
| `pair --name NAME` | Print a one-time code for a Home Assistant, valid 10 minutes |
| `reset-login` | Remove a forgotten config page login. Restart the server, then set it up again |
| `houses` | List paired houses |
| `unpair HOUSE_ID` | Remove a house |
| `log [HOUSE_ID]` | Print the audit log, including what BRAM would have said. The ID is optional with one house |

| Option | Meaning | Default |
|---|---|---|
| `--data` | Where the key, certificate, and database live; give it before the command | `data` |
| `--host` | Address to listen on (`run`) | all |
| `--port` | Port to listen on (`run`) | 8765 |
| `--json` | Print full records (`log`) | off |
| `--name` | Your name for the house (`pair`) | required |

## Docker

The image is built by GitHub for 64-bit Intel/AMD machines. `edge` is the latest development version.

    docker compose up -d

To build it yourself, use `docker compose -f compose.yaml -f compose.build.yaml up -d --build`.

### Portainer

**Stacks > Add stack > Repository**. URL `https://github.com/imCharlieB/Bram`, reference `refs/heads/main`, compose path `compose.yaml`. Deploy, then continue with the config page.

## Config page

1. Open `https://SERVER:8765`. Your browser warns because the server made its own certificate; continue only on your own network.
2. Create the owner login. Setup is open for 15 minutes after the server starts, until a login exists. If it has closed, restart the container. Do this promptly: whoever reaches the page first in that time can create the login. If someone else did, use `reset-login` below.
3. Follow **Getting started** on the page.

| Page | For |
|---|---|
| Overview | Status and the latest log entries |
| Homes | Connect or remove a Home Assistant |
| Model | Choose the model |
| Personality | Choose and try a personality |
| Log | Everything BRAM recorded, with filters |
| Profile | Username, password, and signed-in devices |

 **Try it** sends your model one invented sentence and nothing about your home. It cannot control anything, change what BRAM may do, or approve actions.

- Only models on your own network are accepted, and models that Ollama runs in the cloud are refused.
- If the model is already loaded, BRAM keeps its context size and unload time so other users are not affected.
- Pairing, removing a home, changing the model, and changing the username or password ask for the password again.
- Sessions end after 30 minutes idle or 12 hours.
- Five wrong passwords from one address, or 20 in all, lock sign-in for 15 minutes. Resetting the login signs everyone out.
- BRAM does not send messages yet, so the saved personality only affects **Try it** for now.

## Pairing

1. On the config page, enter a name under **Connect a Home Assistant** and press **Get code**.
2. In Home Assistant: **Settings > Devices & services > Add integration > BRAM**. Enter the server's address, port, and the code.
3. Open BRAM's options and choose what it may see. Nothing is shared until you do.

Supported: people, locks, lights, and motion, occupancy, presence, leak, smoke, door, window, garage door, and gate entities.

## Device page

**Settings > Devices & services > BRAM** shows whether the server is connected, plus one **Sees ...** sensor per chosen entity. Each shows what the server believes, so you can turn on a light and watch it change. *Unknown* means BRAM cannot tell; *unavailable* means it is not connected.

BRAM does not store light, motion, or presence activity. Home Assistant's own history records the **Sees** sensors like any other sensor.

## Security

- Traffic is encrypted. The integration accepts only the server that made the code.
- Codes and tokens are stored on the server as hashes. Home Assistant stores its token in its own configuration.
- Keep the data folder private: it contains the server's key. Deleting it means pairing again.
- Do not expose the port to the internet.
