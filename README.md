<p align="center">
  <img src="https://raw.githubusercontent.com/imCharlieB/Bram/main/custom_components/bram/brand/icon%402x.png" alt="BRAM" width="160">
</p>

<h1 align="center">BRAM</h1>
<p align="center"><b>Butler, Reconnaissance &amp; Automation Manager</b><br>
A self-hosted agent for your home that reaches out, instead of waiting to be asked.</p>

<p align="center">
<a href="https://github.com/imCharlieB/Bram/releases/latest"><img src="https://img.shields.io/github/v/release/imCharlieB/Bram?color=26c6be" alt="Latest release"></a>
<a href="https://github.com/imCharlieB/Bram/actions/workflows/ci.yml"><img src="https://github.com/imCharlieB/Bram/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<a href="https://github.com/imCharlieB/Bram/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-26c6be.svg" alt="License: MIT"></a>
</p>

BRAM watches the devices you choose, tells your phone when something matters, remembers what happened, and talks with you using your own model. It finds problems by itself, without being asked. It runs on your own network, and no cloud is required.

![BRAM's Home page](https://raw.githubusercontent.com/imCharlieB/Bram/main/docs/images/home.jpg)

> **Early development.** BRAM watches, tells, and talks. **It cannot control anything yet**, and it does not replace certified smoke, CO, or security alarms.

[What it does](#what-it-does) · [What you need](#what-you-need) · [Install](#install) · [First days](#first-days) · [Status](#status) · [Update](#update) · [Problems](#problems) · [Documentation](#documentation)

## What it does

| | |
|---|---|
| **Safety alerts** | Leak, smoke, CO, gas, and heat. Repeats until someone acknowledges. Runs in Home Assistant, so it works with the server or model down |
| **Silent sensors** | Tells you when a safety sensor stops reporting. Unknown is never treated as safe |
| **Locks, doors, and windows** | Unlocked at night, open while away, left open, open at night, open while heating or cooling, offline |
| **Motion and comfort** | Motion while everyone is away. Too hot, too cold, near freezing, and humid, with your own limits |
| **Problems with Home Assistant** | Failed integrations, repeating errors, low batteries, offline devices, stuck sensors, broken automations, old backups |
| **3D printers** | Found by itself: progress, time left, temperatures. Told when a print finishes, fails, or pauses, or a heater is left on |
| **Security check** | New devices on every network and VLAN, with your OPNsense router connected, new paired Zigbee and Z-Wave devices, weak Z-Wave locks, router updates, app ports, new admins and tokens, failed sign-ins, locks exposed to voice assistants, public webhooks, offline cameras, and more |
| **Findings** | One list of everything it found, with the story of each |
| **History and trends** | Temperatures, and every heating and cooling run with its settings. Compares each thermostat with the room's own sensor |
| **Learning** | Suggests better night hours from BRAM's history, and fewer messages about what you keep hiding. Nothing changes until you approve |
| **Cameras** | Connects to Frigate, read only. Tells you about a person while everyone is away, at an open or unlocked door, at night, or not known to Frigate; packages; and cars that stay in your driveway, with Frigate's picture. Zones and doors for each camera |
| **Chat and voice** | On its page, in Assist, and in Telegram, answering from live state with the facts listed underneath. Hold to talk and spoken answers, with your own Whisper and Piper |
| **Personality** | Professional, friendly, dry, minimal, unhinged, or your own |
| **Blueprints** | A yes-or-no check on a schedule, and a house summary, as automations you keep in Home Assistant |
| **Outside Home Assistant** | Telegram or ntfy if Home Assistant, Ollama, Frigate, or another device goes down |

Everything that shares or stores more is off until you turn it on.

| Findings | History |
|---|---|
| ![Findings](https://raw.githubusercontent.com/imCharlieB/Bram/main/docs/images/findings.jpg) | ![History](https://raw.githubusercontent.com/imCharlieB/Bram/main/docs/images/history.jpg) |
| **A closer look on Home** | **Suggestions, in Home Assistant** |
| ![A closer look](https://raw.githubusercontent.com/imCharlieB/Bram/main/docs/images/home-closer.jpg) | ![The review page](https://raw.githubusercontent.com/imCharlieB/Bram/main/docs/images/review.jpg) |

## What you need

| | |
|---|---|
| Home Assistant 2026.8 or later, with HACS | For this integration |
| A 64-bit Intel or AMD machine with Docker | For the **BRAM Server**. Best on a different machine, so each can report the other failing |
| The Home Assistant app on your phone | For home alerts |
| A chat model | Optional. Your own in [Ollama](https://ollama.com), or a cloud one: OpenAI, Anthropic, Google Gemini, or any OpenAI-compatible service. Only chat, descriptions, and blueprints need it; alerts never do |

## Install

BRAM has two halves. HACS installs the integration; the server runs in Docker.

1. **Start the server** with Docker. With Docker Compose, as below. In Portainer: **Stacks > Add stack > Repository**, with repository `https://github.com/imCharlieB/Bram`, reference `refs/heads/main`, and compose path `compose.yaml`. Other Docker tools: use [compose.yaml](compose.yaml) as the guide.

   ```
   git clone https://github.com/imCharlieB/Bram.git
   cd Bram
   docker compose up -d
   ```

2. **Create your login.** Open `https://SERVER:8765` right away, with **https**. The browser warns because the server makes its own certificate. Setup closes 15 minutes after the server starts; if it has closed, restart the container.
3. **Add the integration.** HACS > three dots > **Custom repositories** > add `https://github.com/imCharlieB/Bram` as an **Integration**. Download **BRAM** and restart Home Assistant.
4. **Pair them.** On BRAM's page: **Settings > Connect a Home Assistant > Get code**. In Home Assistant: **Settings > Devices & services > Add integration > BRAM**. Enter the server's address, port `8765`, and the code.
5. **Run Quick setup.** **BRAM > Configure > Quick setup**: pick your phone, put anything you do not want to share under **Leave these out**, and **Submit**. Nothing is shared until you do.
6. **Check it.** BRAM's device page says **Connected**. Press **Send test message**; it should reach your phone.

[Full install instructions](https://github.com/imCharlieB/Bram/blob/main/docs/installation.md#installing-1)

## First days

**[Using BRAM day to day](https://github.com/imCharlieB/Bram/blob/main/docs/guide.md#using-bram-day-to-day)** walks you through the rest, in order:

- Choose devices in **Configure > Devices**. Share a weather entity for the outside temperature.
- Turn on watches in **Configure > Watching**: Home Assistant and security, locks, doors, and windows, temperature and humidity, and 3D printers. Printers start switched off.
- Use the buttons on phone messages, and see what BRAM is doing on its Home page.
- Press **Start keeping history** on BRAM's History page, so it has trends and something to learn from.
- Choose a model under **Settings > Model** to chat.

## Status

| | Works today | Planned |
|---|---|---|
| **Watch and tell** | Safety alerts, silent sensors, locks, doors, windows, motion while away, temperature and humidity, phone messages with buttons, quiet hours, daily summary, Telegram, ntfy, monitors | Severity for every finding, safety acknowledge from BRAM's page |
| **Find problems** | Home Assistant health, 3D printers, the security check with new devices on every network and VLAN | Power and energy, poor air |
| **Remember** | Findings with their stories, history and trends, heating and cooling runs, prints; memory of what you ask it to remember, for each person, and your conversation, if you turn it on | Search by meaning |
| **Learn** | Suggested night hours and left-open time, nightly checks for what is often left open, things left on while away, fewer messages about what you keep hiding; all approved on a review page | Usual routines, automations it drafts |
| **Talk** | Chat on its page, in Assist, and in Telegram; voice; personalities; blueprints; your own model or a cloud one | Speakers in rooms |
| **Explain** | | Likely causes and what to do |
| **Control and fix** | Nothing. BRAM cannot control anything | Lights, one-tap repairs, then locks with your approval |
| **Cameras and people** | Frigate events, camera messages with pictures, zones and doors for each camera, descriptions from your own model, asking a camera in chat, a dashboard card | The right message to the right person, faces |

[The whole plan](https://github.com/imCharlieB/Bram/blob/main/docs/roadmap.md)

## Privacy and safety

- It sees only the entities you choose. The server cannot call a Home Assistant service.
- The model has no tools. Alerts use fixed wording and no model.
- Models, speech, and history stay on your network. Home Assistant app messages use its push service, and Telegram is optional.
- Never forward BRAM's ports on your router.

[Security](https://github.com/imCharlieB/Bram/blob/main/docs/how-it-works.md#security) · [What BRAM stores](https://github.com/imCharlieB/Bram/blob/main/docs/how-it-works.md#what-bram-stores) · [Hard rules](https://github.com/imCharlieB/Bram/blob/main/HARD_RULES.md)

## Update

| Part | How |
|---|---|
| Integration | HACS > update BRAM > restart Home Assistant |
| Server | Download the new `ghcr.io/imcharlieb/bram-server` image and recreate the container, however you run Docker. Docker Compose: `docker compose pull`, then `docker compose up -d`. Portainer: recreate the container with **Re-pull image** on. Unraid, Synology, and others: their own update or re-pull button |

Update both and keep them on the same version; BRAM warns you when they differ. [Changes](https://github.com/imCharlieB/Bram/blob/main/CHANGELOG.md)

## Problems

| Problem | Try |
|---|---|
| Page does not load | Use `https` and port 8765; check the server's firewall |
| Setup is closed | Restart the container and reload |
| Configure pages are blank after an update | Refresh the browser with Ctrl+F5 |
| Not connected | Check the address, and that both halves are updated |
| No test message | Choose a phone in **Messages**; check the app's notification permission |
| Anything else | See [more problems](https://github.com/imCharlieB/Bram/blob/main/docs/installation.md#problems), or [open an issue](https://github.com/imCharlieB/Bram/issues) with both version numbers. Remove addresses, tokens, and names first |

## Documentation

**[All documentation](https://github.com/imCharlieB/Bram/blob/main/docs/README.md)**

| Page | What is in it |
|---|---|
| [Installing](https://github.com/imCharlieB/Bram/blob/main/docs/installation.md) | The server, the integration, connecting them, updating |
| [Using BRAM](https://github.com/imCharlieB/Bram/blob/main/docs/guide.md) | Day to day: the Home page, Findings, History |
| [What BRAM tells you](https://github.com/imCharlieB/Bram/blob/main/docs/watching.md) | Watching, messages, problems, printers, monitors, security, learning |
| [Cameras](https://github.com/imCharlieB/Bram/blob/main/docs/cameras.md) | Frigate, camera messages, teaching a camera, the dashboard card |
| [Chat and voice](https://github.com/imCharlieB/Bram/blob/main/docs/chat.md) | Chat, memory, voice, personality, blueprints |
| [Settings](https://github.com/imCharlieB/Bram/blob/main/docs/settings.md) | Every setting, configuration, devices |
| [How BRAM works](https://github.com/imCharlieB/Bram/blob/main/docs/how-it-works.md) | Architecture, security, what BRAM stores |
| [Plan](https://github.com/imCharlieB/Bram/blob/main/docs/roadmap.md) | What is built and what comes next |
| [Changes](https://github.com/imCharlieB/Bram/blob/main/CHANGELOG.md) | Every release |

MIT licensed. See [LICENSE](https://github.com/imCharlieB/Bram/blob/main/LICENSE).
