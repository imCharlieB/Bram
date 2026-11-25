# Installing

BRAM is in early development. It watches and sends alerts; it cannot control anything, and it does not replace certified alarms.

## What you need

| Item | Notes |
|---|---|
| Home Assistant 2026.8 or later, with HACS | |
| A 64-bit Intel/AMD machine with Docker | Best separate from Home Assistant, so each can report the other failing |
| The Home Assistant app on your phone | For home alerts |
| A model in Ollama | Optional for now; see [Testing your model](benchmark.md) |

No database is needed. The HA App version is not built yet.

## 1. Start the server

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

This starts BRAM on port 8765 and ntfy on port 2586. If you do not want ntfy, remove that service. To add hearing and speaking, see [Voice](voice.md). Never forward either port on your router.

## 2. Create your login

Open `https://SERVER:8765`, with **https**. Your browser warns because the server makes its own certificate; continue only on your own network. Choose a username and a password of at least 12 characters.

Do this right away. Setup closes 15 minutes after the server starts, and until then whoever opens the page first can create the login. If it has closed, restart the container.

## 3. Add the integration

1. HACS > three dots > **Custom repositories**. Add `https://github.com/imCharlieB/Bram` as an **Integration**.
2. Download BRAM, then restart Home Assistant.

## 4. Connect them

1. On BRAM's page: **Settings > Connect a Home Assistant > Get code**.
2. In Home Assistant: **Settings > Devices & services > Add integration > BRAM**. Enter the server's address, port 8765, and the code. It works once, for 10 minutes.
3. Open BRAM's options (**Configure > What BRAM can see**) and choose. Nothing is shared until you do.
4. Open BRAM's device page. **BRAM Server** should say **Connected**. Turn on a light you chose and watch its line change.

## 5. Choose a model (optional)

**Settings > Model**: enter `http://HOST:11434`, press **Find models**, then **Save model**. Pick a personality and press **Try it**.

## 6. Set up alerts

See [Alerts and messages](messages.md).

## Updating

| Part | How |
|---|---|
| Server | Portainer: recreate the bram container with **Re-pull image** on; without it, Portainer keeps the old one. Compose: `docker compose pull`, then `docker compose up -d` |
| Integration | HACS: update BRAM, then restart Home Assistant |

Keep both on the same version; BRAM warns on its page and in Home Assistant's Repairs when they differ. The server's is at the bottom of BRAM's home page; the integration's is on its device page. Your login, pairing, and settings are kept in the `bram-data` volume; do not delete it. See [Changes](../CHANGELOG.md).

## Avoiding the browser warning (optional)

If you run a reverse proxy with a trusted certificate, point it at `https://SERVER:8765`, ignore the upstream certificate, and pass the original host name. Keep it reachable only from your own network or VPN. Home Assistant should keep connecting directly to port 8765. Create your login before adding the proxy. Behind a proxy, wrong passwords from anyone count together toward the lockout.

## Problems

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
| Logo is missing | Refresh with Ctrl+F5. Needs Home Assistant 2026.3 or later |
