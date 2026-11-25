# BRAM Server

In this version the server watches and logs. It sends no messages and controls nothing. It does not replace certified alarms.

    bram-server [--data DIR] COMMAND

| Command | Does |
|---|---|
| `run` | Start the server |
| `pair --name NAME` | Print a one-time code for a Home Assistant, valid 10 minutes |
| `houses` | List paired houses |
| `unpair HOUSE_ID` | Remove a house; restart the server afterward |
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
    docker compose exec bram bram-server --data /data pair --name Home

To build it yourself, use `docker compose -f compose.yaml -f compose.build.yaml up -d --build`.

### Portainer

1. **Stacks > Add stack > Repository**. URL `https://github.com/imCharlieB/Bram`, reference `refs/heads/main`, compose path `compose.yaml`. Deploy.
2. **Containers > bram > Console**, connect with `/bin/sh`, and run `bram-server --data /data pair --name Home`.

## Pairing

1. Run `bram-server pair --name Home`, using the same `--data` as the running server.
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
