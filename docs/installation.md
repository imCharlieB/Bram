# Installing

BRAM is in early development. It watches and sends alerts; it cannot control anything, and it does not replace certified alarms.

## What you need

| Item | Notes |
|---|---|
| Home Assistant 2026.8 or later, with HACS | |
| A 64-bit Intel/AMD machine with Docker | Best separate from Home Assistant, so each can report the other failing |
| The Home Assistant app on your phone | For home alerts |
| A model in Ollama | Optional. Only chat and [blueprints](blueprints.md) need it; alerts never do. See [Testing your model](benchmark.md) |

No database is needed. A version that runs as a Home Assistant app (add-on) is not built yet.

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
3. Open BRAM's options (**Configure > Quick setup**): pick your phone, put anything you do not want to share under **Leave these out**, and **Submit**. For more choices, see [Devices](devices.md) and [Every setting](settings.md). Nothing is shared until you do.
4. Open BRAM's device page. **BRAM Server** should say **Connected**. Turn on a light you chose and watch its line change.

## 5. Choose a model (optional)

**Settings > Model**: enter `http://HOST:11434`, press **Find models**, then **Save model**. Pick a personality and press **Try it**.

## 6. Set up alerts and watching

Quick setup turns on a few lock and door rules. To choose devices, turn on more watches, and keep history, follow [Using BRAM day to day](guide.md). For every message and button, see [Alerts and messages](messages.md).

## 7. Connect your router (optional)

To see every device on every network and VLAN in the security check: on BRAM's page, **Settings > Router**. OPNsense for now. Step by step: [Connect your router](security-check.md#connect-your-router).

## 8. Connect cameras (optional)

With [Frigate](https://frigate.video), on BRAM's page: **Settings > Cameras**, enter Frigate's address, **Connect**, and turn on the cameras to watch. Then turn on camera messages in Home Assistant. Step by step: [Cameras in the guide](guide.md#cameras).

## Updating

| Part | How |
|---|---|
| Server | Download the new `ghcr.io/imcharlieb/bram-server` image and recreate the container, however you run Docker. Docker Compose: `docker compose pull`, then `docker compose up -d`. Portainer: recreate the container with **Re-pull image** on. Unraid, Synology, and others: their own update or re-pull button. Without re-pulling, Portainer keeps the old image |
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
| Logo is missing in Home Assistant | Refresh with Ctrl+F5 |
| HACS shows no icon | Not something BRAM can fix; the icon shows in Home Assistant |
| Configure pages are blank after an update | Refresh the browser with Ctrl+F5 |
| No test message | Choose a phone in **Configure > Messages**; allow notifications for the Home Assistant app |
| An AC has no run times | It must report what it is doing, such as *cooling*, not only its mode |
| Anything else | [Open an issue](https://github.com/imCharlieB/Bram/issues) with both version numbers. Remove addresses, tokens, and names first |
