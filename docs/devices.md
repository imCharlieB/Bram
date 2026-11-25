# Devices

BRAM sees only the devices you choose. Choosing one does not let BRAM control it.

## BRAM's suggestions

**Configure > BRAM's suggestions** lists what matters most and BRAM cannot see yet: people, locks and doors, leak and smoke sensors, and a motion sensor for each area without one. Remove what you do not want, and **Submit**. Nothing is shared until you do. These come from simple rules, not a model.

## Add devices quickly

**Settings > Devices & services > BRAM > Configure > Add devices quickly**

1. Choose types, such as locks and doors.
2. Choose areas, or leave empty for the whole home.
3. BRAM lists what it found. Remove what you do not want, and **Submit**.

It adds to what you already chose. It skips hidden devices, settings and health readings, and extra zones of the same presence sensor. Devices you add to Home Assistant later are not shared until you add them here.

## Choose one by one

**Configure > What BRAM can see** lists every choice by type. Remove one there to stop sharing it; its line disappears from BRAM's device page.

## What BRAM understands

| Type | Home Assistant devices | BRAM says |
|---|---|---|
| People | `person` | home, away |
| Locks | `lock` | locked, unlocked |
| Doors and windows | Door, window, opening, and garage door sensors; door, garage, gate, and window covers | open, closed |
| Leak and smoke | Moisture and smoke sensors | leak or dry, smoke or clear |
| Motion | Motion, occupancy, presence, and moving sensors | detected, clear |
| Lights | `light` | on, off |

Anything else, or a state it does not recognize, is *unknown*.

## What to add first

1. **Everyone who lives there.** Otherwise "away" is wrong.
2. **Outside doors and locks**, for [watching](watching.md).
3. **Leak and smoke sensors**, for alerts.
4. **Motion sensors and lights**, so chat answers well and future learning has something to learn from.

## The device page

**BRAM Server** shows the connection. Each chosen device has a line with what the server believes. *Unavailable* means the server is not connected.

| Button | Does |
|---|---|
| Send test message | Sends to your chosen phones |
| Allow stopped messages | Undoes every **Stop these** |
