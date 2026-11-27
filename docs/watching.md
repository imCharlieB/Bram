# How BRAM watches your home

BRAM watches in Home Assistant itself, using plain rules. No model decides what is an alert, and it keeps working if the BRAM Server, the model, or the internet is down, though a phone must be reachable to get the message.

## From a change to a message

```
A device changes, or a timer runs
  → Is it a device you shared?
  → Does a rule you turned on apply?
  → Has it lasted long enough?
  → Told already, stopped, quiet hours, or daily limit?
  → Message to your phones, with buttons
  → Remembered until it is over, so it is news again next time
```

## The rules

| Rule | Looks at | Waits | Says | Default |
|---|---|---|---|---|
| Leak | Leak sensor on | 0 | Water leak detected | On for shared sensors |
| Smoke | Smoke sensor on | 0 | Smoke detected. Check now | On for shared sensors |
| Carbon monoxide, gas | Sensor on | 0 | Detected. Get out and call for help | On for shared sensors |
| Heat | Sensor on | 0 | Dangerous heat detected | On for shared sensors |
| Safety, tamper | Sensor on | 0 | Safety problem detected | On for shared sensors |
| Silent safety sensor | Any of those unreachable | 5 min | Stopped reporting | On for shared sensors |
| Unlocked at night | Lock unlocked or open in night hours | 2 min | Unlocked, and it's night | Off |
| Open or unlocked while away | Lock or door, and everyone shared known away | 2 min | Open, and everyone I track is away | Off |
| Left open | Door, window, or garage open; each type can be turned off | Your minutes | Open for that long | Off |
| Open at night | Door, window, or garage open in night hours; the types chosen under Left open | 2 min | Open, and it's night | Off |
| Open while heating or cooling | Door, window, or garage open while a shared thermostat is heating or cooling | Left open minutes | Open while the thermostat is cooling | Off |
| Motion while away | Motion, and everyone shared known away. Once per sensor until someone is home | 0 | Motion while everyone I track is away | Off |
| Too hot, too cold | Temperature sensors and thermostats' own reading, past your limits | 30 min | Above or below your limit | Off |
| Near freezing | Temperature below your near-freezing limit | 15 min | Near freezing. Pipes may freeze | Off |
| Humid | Humidity sensor above your limit | 30 min | Humid, above your limit | Off |
| Offline | Lock or door unreachable | 5 min | I can't see it | Off |
| Server lost | BRAM Server disconnected | 3 min | Not answering | On |

## Two kinds of message

| | Safety | Everything else |
|---|---|---|
| Repeats | Up to 11 times, until acknowledged | Once each time it happens |
| Quiet hours | Ignored | Respected, except unlocked at night, open at night, open or unlocked while away, motion while away, and near freezing |
| Can be stopped | No, only acknowledged | Yes, with **Stop these** |
| Daily limit | None | 10 for notices, 20 for lock and door rules |
| If sending fails | Tried again every minute | Tried again |
| Also shown inside Home Assistant | Yes | No |

A leak that dries out keeps reminding until someone acknowledges it. A lock that is locked again simply ends.

## Unknown is not safe

If a device is unavailable, BRAM does not assume it is locked, closed, or dry. If any shared person's location is unknown, BRAM does not decide the house is empty. If no people are shared, the away rule never runs.

## Night hours

You set when night starts and ends, separately from quiet hours. Night decides when an unlocked lock or an open door matters; quiet hours decide when routine messages wait.

Friday and Saturday nights can have their own hours. BRAM can [suggest better hours](learning.md); nothing changes until you approve it.

If you have a helper or sensor that is on while someone is asleep, such as an `input_boolean` you turn on at bedtime, choose it under **Also night while any of these is on**. It is night while any of them is on, even before your hours start, as well as during your hours. If one is unavailable, only the hours count. This also covers a person at night on a [camera](cameras.md).

## What it does not do

It does not watch cameras, tell people apart, lock or close anything, or call anyone. It does not replace certified alarms.

## Turning it on

Safety alerts are on for every safety sensor you share. Everything else is off until you turn it on in **BRAM > Configure > Watching**:

| Page | Rules |
|---|---|
| **Locks, doors, and windows** | Unlocked at night, offline, left open, open at night, open while heating or cooling, while everyone is away, and night hours. See [Alerts and messages](messages.md#watching-locks-and-doors) |
| **Temperature and humidity** | Too hot, too cold, near freezing, and humid, with your limits in your home's unit, and sensors to leave out, such as outdoor ones |
| **Home Assistant and security** | [Problems with Home Assistant](problems.md) and the hourly [security check](security-check.md) |
| **3D printers** | [Printer messages](printers.md), for each printer you switch on |

Quick setup turns on unlocked at night, left open, and offline. Choose **Back** to return to the main settings. For a walkthrough, see [Using BRAM day to day](guide.md).
