# Cameras

> **Built,** part by part; the last parts came in 0.43. More rules may come; [the order](#the-order-it-will-be-built) shows what is done.

**Who talks to Frigate:** only BRAM's server. It reads Frigate's events, names, and pictures, and decides what matters. Home Assistant is told only what BRAM needs for its phone messages.

BRAM watches your cameras through [Frigate](https://frigate.video). Frigate already finds people, cars, animals, and packages, and with face recognition on, who someone is. BRAM adds what Frigate does not: it knows the rest of your home (who is home, what is open or unlocked, night hours), so it can tell you what matters and stay quiet about what does not. A vision model on your own network can describe what happened in a sentence.

Nothing about cameras is on until you turn it on, camera by camera. Pictures go to a model only for cameras you choose, and to a cloud model only if you turn that on separately (rules E1 and E2).

## How it works

```
Frigate sees a person, car, animal, or package
  → BRAM reads the event from Frigate (it only reads; it never changes Frigate)
  → Is this camera turned on in BRAM?
  → What else is true: everyone away? door open or unlocked? night? who did Frigate recognize?
  → A fixed rule decides whether it matters
  → If you chose it for this camera, the model describes the event in one or two sentences
  → Told to your phone with the picture, unless it is the same as one told recently
```

The decision is code, not the model. The model's words only describe; they never decide whether you are told, and a slow model never holds a message back (rule C6).

## What it tells you

Turn these on in Home Assistant: **Settings > Devices & services > BRAM > Configure > Watching > Cameras > What to tell me**. They cover the cameras you turned on under **Settings > Cameras** on BRAM's page.

| Rule | When | Default |
|---|---|---|
| A person while everyone is away | Frigate sees a person, and everyone BRAM can see is away. Ignores quiet hours | Off |
| A person at a door that is open or unlocked | A person on a camera, while a door or lock linked to that camera is open or unlocked. Ignores quiet hours | Off |
| A person at night | A person in your night hours, set under **Locks, doors, and windows**, or while your asleep helper is on. Ignores quiet hours | Off |
| A person Frigate does not know | A person Frigate did not name. Only useful with face recognition on in Frigate; without it, every person is unknown | Off |
| A package | Frigate sees a package | Off |
| A car | A car that stays at least 30 seconds, in the zones you choose for that camera, such as the driveway. A car driving past is never told | Off |
| Camera offline | Frigate or a camera stops reporting | In the [security check](security-check.md), and on BRAM's page |

A person Frigate knows is named in the message, such as "Alex at front door, and everyone I track is away."

### Set up one camera

**Configure > Watching > Cameras > Set up one camera**, then choose the camera:

| Setting | Does |
|---|---|
| Doors and locks this camera looks at | For a person at a door that is open or unlocked. A door or lock that is unavailable never counts as open |
| Frigate zones that count | Picked from the zones in Frigate's settings for that camera, such as porch or driveway. With zones chosen, a person or car outside them is left out, so a person on the sidewalk is not at your door and a car on the street is not in your driveway. Empty: the whole picture counts |
| Messages from this camera | Which of the messages you turned on this camera sends. All, unless you choose |

A camera you have not set up sends every message you turned on, for its whole picture.

## Fewer messages

### Your own driveway, not the neighbors'

Frigate sees everything in the picture, so a person in the neighbors' driveway is still "a person". Two ways to fix that, best first:

1. **Draw a zone in Frigate** over only your own driveway, porch, or path (Frigate's settings, the camera, **Zones**). Then in BRAM, under **Set up one camera**, choose that zone under **Frigate zones that count**. Anything outside it is never told.
2. **Not news.** When a camera window opens on Home about something that is not news, select **Not news**, say what it is, such as "the neighbors' driveway", and **Keep quiet**. BRAM stops telling you, on Home and on your phone, about the same kind of thing on that camera in the same Frigate zones; an event in no zone matches only others in no zone. What you wrote goes to your model, so its descriptions use it. They are listed under **Settings > Cameras > Not news**, each with **Tell me again**.

- **Same thing, once.** A person or package already told about on that camera is not told again for 30 minutes. Change it with **Not again on the same camera for**.
- **One moment, once.** One person walking past several cameras within 2 minutes is one message.
- **Quiet hours** hold a stranger or a package, noted in Findings, but not a person while away or at night.
- **Stop these** on the message stops that kind on that camera, such as people at the front door. **Less often**, **Allow stopped messages**, and suggestions from what you do work as for other messages. See [How often BRAM tells you](how-often.md).
- At most 30 camera messages a day.

## The message

The camera, who Frigate recognized, what is true in the rest of the home, and the zones, such as "Someone at front door, and it's night. In porch." With the [Frigate integration](https://docs.frigate.video/integrations/home-assistant) installed in Home Assistant, it shows Frigate's picture of the event: its snapshot, or its smaller thumbnail when snapshots are off for that camera in Frigate. Turn snapshots on in Frigate for a better picture. Tap it to open the finding on BRAM's page. Coming: your model's description, such as "A delivery driver left a box on the porch."

## Descriptions from your model

Your own model can describe each event in a sentence or two, such as "A delivery driver sets a box by the door and walks back to a white van."

1. Choose a model that can read pictures under **Settings > Model** on BRAM's page. Many can; if yours cannot, the cameras page says so.
2. Under **Settings > Cameras**, turn on **Describe** for each camera you want described, and enter your password. It is off for every camera until you do.

Only the event's picture goes to the model, and only for those cameras. The model must be on your own network; no picture goes to a cloud model. One picture is described at a time, and only for events from the last 5 minutes.

The words appear in the event's window on Home, in **Looking at**, and under **Settings > Cameras**. A phone message includes them only if they are ready when the message goes out: a slow model never holds a message back, and the words never decide whether you are told. Turning **Watch** off for a camera also turns off **Describe** and drops its words.

## On BRAM's page

| Where | Shows |
|---|---|
| Home, **Looking at** | The latest picture from the cameras BRAM watches, and each camera's last event ✅ |
| Home, over the brain | A window with the picture and **Not news**, only for an event BRAM told you about or held for quiet hours; one window for all cameras ✅ |
| Settings > Cameras | Each camera, with its switch and last event ✅ |
| Findings | Each camera event BRAM told you about, with its story |

## In Home Assistant

BRAM adds no camera entities. If you use the [Frigate integration](https://docs.frigate.video/integrations/home-assistant), Home Assistant already has each camera, its pictures, and Frigate's sensors; BRAM would only repeat them.

What BRAM adds is what Frigate does not have:

- **Phone messages** that decide what matters, using the rest of your home. Their picture comes from the Frigate integration when it is installed.
- **The BRAM camera card** for your dashboards: Frigate's picture of the latest event, what happened, and your model's description.

### The BRAM camera card

It comes with BRAM; there is nothing to install. Edit a dashboard, **Add card**, and search for **BRAM camera**, or add it in YAML:

```yaml
type: custom:bram-camera-card
camera: front_door
```

`camera` is the camera's name in Frigate. Leave it out to show whichever camera saw something last. `title` changes the heading. The picture comes from the Frigate integration; without it, the card shows the words only. It updates every 10 seconds, and only shows: it changes nothing. If it does not appear in the list after updating BRAM, refresh the browser.

## Ask a camera

In chat, on BRAM's page, in Assist, or in Telegram: "Is anyone on the porch?" or "What's in the driveway?" BRAM finds the camera by its name, or by one of its Frigate zones, takes its picture now, and your model answers from it, saying it is what the picture shows. If you have one camera that can be asked, "Any packages on the camera?" works too.

Only cameras with **Describe** on can be asked, since the picture goes to your model. The picture is not kept with the chat. The scheduled check [blueprint](blueprints.md) can ask, for example, "Is there a package on the porch?" every hour, and tell your phone only when the answer is yes.

## Connect Frigate

On BRAM's page, **Settings > Cameras**:

1. Enter Frigate's address.
   - `http://HOST:5000` is Frigate's port with no login. Use it if BRAM's server is on the same trusted network.
   - `https://HOST:8971` is Frigate's login port. Make a Frigate user that can only view (Frigate, Settings, Users, role **viewer**) and enter its username and password. BRAM trusts Frigate's certificate the first time and refuses to connect if it changes, so the password only goes to your Frigate. If you renew Frigate's certificate, select **Connect** again.
2. Select **Connect** and enter your BRAM password.
3. Under **Which cameras BRAM watches**, turn on **Watch** for each camera.

BRAM checks Frigate every 10 seconds. A camera you add in Frigate shows up within 10 minutes. Each watched camera shows its latest event under Settings and in **Looking at** on Home, with Frigate's snapshot, or its thumbnail when snapshots are off in Frigate, or else the camera's latest frame. If Frigate stops getting a picture from a camera, it says so, and never treats it as nothing there. Turning a camera off drops its events and picture from BRAM. **Disconnect** forgets the address, login, and choices.

Only an address on your own network is accepted. If you type the address without `http://` or `https://`, BRAM tries both.

### If it cannot connect

The message under **Connect** says what went wrong:

| Message | Try |
|---|---|
| Nothing answered at HOST:PORT | The address or port is wrong, or the port is closed. With the Frigate app in Home Assistant, port 5000 is off until you set it under the app's **Configuration > Network**; 8971 is on |
| No reply in time | A firewall between BRAM's server and Frigate, or the wrong address |
| Use https:// | That is Frigate's login port; type `https://HOST:8971` |
| Answered, but not like Frigate | Another program is on that port |
| Did not accept that username and password | Check the Frigate user; a viewer is enough |
| Asks for a login | That port needs a Frigate user |

BRAM's server runs in Docker, so `localhost` there means the container itself. Use Frigate's address on your network, such as `192.168.1.20`.

## Settings

On BRAM's page, **Settings > Cameras**:

| Setting | Detail | Default |
|---|---|---|
| Frigate address | Such as `http://HOST:5000`, or the login port `https://HOST:8971` with a Frigate user that can only view | None |
| Each camera | Watch events | Off |
| In Home Assistant, Configure > Watching > Cameras > What to tell me | Each rule above, and **Not again on the same camera for** | Off; 30 minutes |
| In Home Assistant, Configure > Watching > Cameras > Set up one camera | Its doors and locks, the Frigate zones that count, and its messages | None; whole picture; all |
| Describe | For each watched camera: the event's picture goes to your own model to be put into words | Off |
| Cloud model may see pictures | Only if you also use a cloud model | Off |
| Keep pictures | The latest event per camera, or the last 7 days | Latest only |

## What it never does

- It never turns off, moves, or changes a camera, recording, or Frigate setting.
- It never treats an unknown or offline camera as "nothing there" (rule B2).
- It never sends a picture anywhere you did not choose.
- It is not a security system and does not call anyone (rule C5).

## The order it will be built

| Part | What you get | Status |
|---|---|---|
| 1. Connect Frigate | The address and cameras on BRAM's page; each camera's switch | ✅ 0.38 |
| 2. Events | Each camera's latest event and picture on BRAM's page; Home Assistant told of each event, for messages | ✅ 0.39 |
| 3. Rules and messages | Person while away, at an open or unlocked door, at night, or unknown; packages; cars that stay in a zone; with Frigate's picture, same-thing-once, one message across cameras, and settings for each camera | ✅ 0.41 |
| 4. Descriptions | Your own model describes events, for the cameras you choose | ✅ 0.42 |
| 5. Ask a camera | Chat questions and scheduled checks about what a camera sees | ✅ 0.43 |
| 6. Camera card | A dashboard card with Frigate's picture and BRAM's description | ✅ 0.43 |
