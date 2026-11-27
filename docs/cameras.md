# Cameras

> **Being built.** Part 1, connecting Frigate, works now, and BRAM's page shows each camera's latest event. The rules, messages, and Home Assistant entities below are coming; [the order](#the-order-it-will-be-built) shows what is done.

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

## What it will tell you

| Rule | When | Default |
|---|---|---|
| Person while everyone is away | Frigate sees a person on a camera you chose, and everyone BRAM can see is away | Off |
| Person at an open or unlocked door | A person near a door that is open or unlocked; you link each camera to its doors | Off |
| Person at night | A person in your night hours | Off |
| Someone Frigate does not know | Face recognition is on in Frigate and the face is not one it knows | Off |
| Package delivered | Frigate sees a package that stays | Off |
| Car arrived | A car stops in a zone you choose, such as the driveway | Off |
| Camera offline | Frigate or a camera stops reporting | Already in the [security check](security-check.md) |

Each camera has its own switch for each rule, and the Frigate zones that count, so a person on the sidewalk is not a person at your door.

## Fewer messages

- **Same thing, once.** A parked car or a person already told about on that camera in the last 30 minutes is not told again. Someone Frigate does not know is always told the first time.
- **Cooldown.** One message per camera every few minutes at most, and one across cameras for the same moment, such as a person walking past three cameras. Later ones update the same message quietly.
- **Quiet hours** apply, except person while away and person at an open or unlocked door.
- **Stop these**, **Less often**, and suggestions from what you do work as for other messages. See [How often BRAM tells you](how-often.md).

## The message

The picture Frigate saved, the camera, the time, who Frigate recognized, and the model's description if you chose one, such as "A delivery driver left a box on the porch and walked back to a white van." Tap it to open the event on BRAM's page.

## On BRAM's page and in Home Assistant

| Where | Shows |
|---|---|
| Home, **Looking at** | The latest event: picture, camera, who, and the description |
| Home, the brain | A **Cameras** system on the orbit, with a closer look listing each camera's last event |
| Findings | Each event told, with its story |
| Home Assistant | For each camera: **Last event** (a picture) and **Recognized people** (a sensor), for your own dashboards and automations |

## In Home Assistant

For each camera you turn on, BRAM's device in Home Assistant gets:

| Entity | Shows | Attributes |
|---|---|---|
| `image.bram_<camera>_last_event` | The picture of the latest event told or seen | `camera`, `at`, `summary` |
| `sensor.bram_<camera>_recognized_people` | Who Frigate recognized in the latest event, such as `Alex, Sam`, or `none` | `people` (a list), `unknown` (how many faces it did not know), `summary`, `label` (person, car, package), `at` |
| `sensor.bram_<camera>_last_event` | What happened, in a few words, such as `person at the front door` | `label`, `zones`, `at`, `told` (whether your phone was told) |

They change only when a new event comes in. Use them on your own dashboards and in your own automations; BRAM's messages do not depend on them.

### Example: a dashboard card

```yaml
type: picture-entity
entity: image.bram_front_door_last_event
name: Front door
show_state: false
```

Put the summary under it with a markdown card:

```yaml
type: markdown
content: >-
  {{ state_attr('image.bram_front_door_last_event', 'summary') }}
```

### Example: your own automation

Turn on the porch light when someone Frigate knows arrives after dark:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.bram_front_door_recognized_people
conditions:
  - condition: template
    value_template: "{{ state_attr('sensor.bram_front_door_recognized_people', 'people') | length > 0 }}"
  - condition: state
    entity_id: sun.sun
    state: below_horizon
actions:
  - action: light.turn_on
    target:
      entity_id: light.porch
```

This is your automation, not BRAM's: BRAM itself only reads cameras and sends messages.

## Ask a camera

In chat: "What is on the porch?" or "Is anyone in the backyard?" BRAM takes the camera's picture now and the model answers, saying it is a description. The scheduled check [blueprint](blueprints.md) can then ask, for example, "Is there a package on the porch?" every hour.

## Connect Frigate

On BRAM's page, **Settings > Cameras**:

1. Enter Frigate's address.
   - `http://HOST:5000` is Frigate's port with no login. Use it if BRAM's server is on the same trusted network.
   - `https://HOST:8971` is Frigate's login port. Make a Frigate user that can only view (Frigate, Settings, Users, role **viewer**) and enter its username and password. BRAM trusts Frigate's certificate the first time and refuses to connect if it changes, so the password only goes to your Frigate. If you renew Frigate's certificate, select **Connect** again.
2. Select **Connect** and enter your BRAM password.
3. Under **Which cameras BRAM watches**, turn on **Watch** for each camera.

BRAM checks Frigate every 10 seconds. A camera you add in Frigate shows up within 10 minutes. Each watched camera shows its latest event under Settings and in the **Cameras** card on Home. If Frigate stops getting a picture from a camera, it says so, and never treats it as nothing there. Turning a camera off drops its events and picture from BRAM. **Disconnect** forgets the address, login, and choices.

Only an address on your own network is accepted.

## Settings

On BRAM's page, **Settings > Cameras**:

| Setting | Detail | Default |
|---|---|---|
| Frigate address | Such as `http://HOST:5000`, or the login port `https://HOST:8971` with a Frigate user that can only view | None |
| Each camera | Watch events | Off |
| Each camera, coming | Which rules; which zones count; which doors it looks at | Off |
| Describe with the model | Per camera; sends the event's picture and a few frames to your model | Off |
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
| 2. Events | Each camera's latest event and picture on BRAM's page ✅; the Home Assistant picture and sensors per camera ⬜ | 🟡 |
| 3. Rules and messages | The rules above, with the picture in the message, same-thing-once, and cooldown | ⬜ |
| 4. Descriptions | The model describes events, per camera | ⬜ |
| 5. Ask a camera | Chat questions and scheduled checks about what a camera sees | ⬜ |
| 6. Camera blueprint | A blueprint for your own automations on camera events | ⬜ |
