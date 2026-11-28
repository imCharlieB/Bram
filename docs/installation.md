# Installing

Getting BRAM running: the server, the Home Assistant integration, and connecting them.

On this page: [Installing](#installing-1) · [BRAM Server](#bram-server)

## Installing

BRAM is in early development. It watches and sends alerts; it cannot control anything, and it does not replace certified alarms.

### What you need

| Item | Notes |
|---|---|
| Home Assistant 2026.8 or later, with HACS | |
| A 64-bit Intel/AMD machine with Docker | Best separate from Home Assistant, so each can report the other failing |
| The Home Assistant app on your phone | For home alerts |
| A model in Ollama | Optional. Only chat and [blueprints](chat.md#blueprints) need it; alerts never do. See [Testing your model](how-it-works.md#testing-your-model) |

No database is needed. A version that runs as a Home Assistant app (add-on) is not built yet.

### 1. Start the server

**Portainer:** Stacks > Add stack > Repository.

| Field | Value |
|---|---|
| Repository URL | `https://github.com/imCharlieB/Bram` |
| Reference | `refs/heads/main` |
| Compose path | `compose.yaml` |

**Docker Compose:**

    git clone https://github.com/imCharlieB/Bram.git
    cd Bram
    docker compose up -d

This starts BRAM on port 8765 and ntfy on port 2586. If you do not want ntfy, remove that service. To add hearing and speaking, see [Voice](chat.md#voice). Never forward either port on your router.

### 2. Create your login

Open `https://SERVER:8765`, with **https**. Your browser warns because the server makes its own certificate; continue only on your own network. Choose a username and a password of at least 12 characters.

Do this right away. Setup closes 15 minutes after the server starts, and until then whoever opens the page first can create the login. If it has closed, restart the container.

### 3. Add the integration

1. HACS > three dots > **Custom repositories**. Add `https://github.com/imCharlieB/Bram` as an **Integration**.
2. Download BRAM, then restart Home Assistant.

### 4. Connect them

1. On BRAM's page: **Settings > Connect a Home Assistant > Get code**.
2. In Home Assistant: **Settings > Devices & services > Add integration > BRAM**. Enter the server's address, port 8765, and the code. It works once, for 10 minutes.
3. Open BRAM's options (**Configure > Quick setup**): pick your phone, put anything you do not want to share under **Leave these out**, and **Submit**. For more choices, see [Devices](settings.md#devices) and [Every setting](settings.md#every-setting). Nothing is shared until you do.
4. Open BRAM's device page. **BRAM Server** should say **Connected**. Turn on a light you chose and watch its line change.

### 5. Choose a model (optional)

**Settings > Model**: under **Where your model runs**, keep **On your own network** and enter your Ollama address, such as `http://HOST:11434`, press **Find models**, then **Save model**. Without your own model, choose a cloud provider instead (OpenAI, Anthropic, Google Gemini, or another OpenAI-compatible service), enter its API key, press **Find models**, pick one, and **Save cloud model**. Then pick a personality and press **Try it**.

With a cloud model, your questions and what BRAM shares about your home to answer them go to that company. Camera pictures go only if you turn on **Let the cloud model see camera pictures**. Safety alerts never use a model.

### 6. Set up alerts and watching

Quick setup turns on a few lock and door rules. To choose devices, turn on more watches, and keep history, follow [Using BRAM day to day](guide.md#using-bram-day-to-day). For every message and button, see [Alerts and messages](watching.md#alerts-and-messages).

### 7. Connect your router (optional)

To see every device on every network and VLAN in the security check: on BRAM's page, **Settings > Router**. OPNsense for now. Step by step: [Connect your router](watching.md#connect-your-router).

### 8. Connect cameras (optional)

With [Frigate](https://frigate.video), on BRAM's page: **Settings > Cameras**, enter Frigate's address, **Connect**, and turn on the cameras to watch. Then turn on camera messages in Home Assistant. Step by step: [Cameras in the guide](guide.md#cameras).

### Updating

| Part | How |
|---|---|
| Server | Download the new `ghcr.io/imcharlieb/bram-server` image and recreate the container, however you run Docker. Docker Compose: `docker compose pull`, then `docker compose up -d`. Portainer: recreate the container with **Re-pull image** on. Unraid, Synology, and others: their own update or re-pull button. Without re-pulling, Portainer keeps the old image |
| Integration | HACS: update BRAM, then restart Home Assistant |

Keep both on the same version; BRAM warns on its page and in Home Assistant's Repairs when they differ. The server's is at the bottom of BRAM's home page; the integration's is on its device page. Your login, pairing, and settings are kept in the `bram-data` volume; do not delete it. See [Changes](../CHANGELOG.md).

### Avoiding the browser warning (optional)

If you run a reverse proxy with a trusted certificate, point it at `https://SERVER:8765`, ignore the upstream certificate, and pass the original host name. Keep it reachable only from your own network or VPN. Home Assistant should keep connecting directly to port 8765. Create your login before adding the proxy. Behind a proxy, wrong passwords from anyone count together toward the lockout.

### Problems

| Problem | Try |
|---|---|
| Page does not load | Use `https`; check the server's firewall for port 8765 |
| Setup has timed out | Restart the container and reload |
| Someone else created the login, or you forgot it | In the container console run `bram-server --data /data reset-login`, then restart it |
| Too many attempts | Wait 15 minutes |
| Home Assistant cannot connect | Check the address and that Home Assistant can reach port 8765; get a new code |
| Home shows Not connected | Wait up to 5 minutes; then search Home Assistant's log for `bram` |
| Lights or motion sensors are missing from the list | Update the integration and restart Home Assistant |
| A line on the device page says Unknown | That device is not reporting to Home Assistant |
| Every line is Unavailable | The server is not connected |
| Find models fails | The server must be able to reach Ollama on port 11434 |
| Portainer fails to build | Update your copy; the image is now downloaded, not built |
| Logo is missing in Home Assistant | Refresh with Ctrl+F5 |
| HACS shows no icon | Not something BRAM can fix; the icon shows in Home Assistant |
| Configure pages are blank after an update | Refresh the browser with Ctrl+F5 |
| No test message | Choose a phone in **Configure > Messages**; allow notifications for the Home Assistant app |
| An AC has no run times | It must report what it is doing, such as *cooling*, not only its mode |
| Anything else | [Open an issue](https://github.com/imCharlieB/Bram/issues) with both version numbers. Remove addresses, tokens, and names first |

## BRAM Server

The server watches and, if you turn it on, sends messages. It controls nothing. It does not replace certified alarms.

Everyday setup happens on the config page. These commands are for running the server and for rescue.

    bram-server [--data DIR] COMMAND

| Command | Does |
|---|---|
| `run` | Start the server |
| `pair --name NAME` | Print a one-time code for a Home Assistant, valid 10 minutes |
| `reset-login` | Remove a forgotten config page login and its second factor. Restart the server, then set it up again |
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

To set it up, see [Installing](installation.md#installing-1) and [Alerts and messages](watching.md#alerts-and-messages).

### Config page

| Page | For |
|---|---|
| Home | [What BRAM is doing](guide.md#brams-home-page): watching, decisions, what needs you, and [chat](chat.md#chat) |
| Messages | Telegram, ntfy, and monitors |
| Settings | Homes, model, personality, and [voice](chat.md#voice) |
| Findings | [What BRAM found](guide.md#findings) and its story |
| History | [What devices did](guide.md#history-and-trends), heating and cooling, and space used |
| Log | Everything BRAM recorded, with filters |
| Profile | Username, password, second factor, and signed-in devices |

The page cannot control anything, change what BRAM may do, or approve actions. **Try it** sends your model one invented sentence and nothing about your home.

- Only models on your own network are accepted, and models that Ollama runs in the cloud are refused.
- If the model is already loaded, BRAM keeps its context size and unload time so other users are not affected.
- Pairing, removing a home, changing the model, and changing the username or password ask for the password again.
- Sessions end after 30 minutes idle or 12 hours.
- Five wrong passwords from one address, or 20 in all, lock sign-in for 15 minutes. Resetting the login signs everyone out.
- **Second factor:** **Profile > Second factor > Set up**. Scan the code with any authenticator app, enter what it shows, and save the eight recovery codes. Signing in then needs your password and a code. It also signs out every other device. Your phone and the server must have the right time.
- Lost your phone: sign in with a recovery code, turn the second factor off, and set it up again. Lost those too: use `reset-login`.
- Alerts use fixed wording, so personality affects only chat and **Try it**.

### Security

- Traffic is encrypted. The integration accepts only the server that made the code.
- Codes and tokens are stored on the server as hashes. Home Assistant stores its token in its own configuration.
- Keep the data folder private: it contains the server's key. Deleting it means pairing again.
- Do not expose the port to the internet.
