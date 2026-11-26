# Devices

BRAM sees only the devices you choose. Choosing one does not let BRAM control it.

## A device's other readings

For a shared thermostat, fan, water heater, valve, vacuum, mower, or humidifier, BRAM also reads the other sensors on the same device, such as hot water left or compressor health. Select it on Home to see them; chat knows them too. Unknown values and text that is not meant to be read are left out.

## Renamed in Home Assistant

If you change an entity's ID in Home Assistant, BRAM follows it.

## Deleted in Home Assistant

An entity you delete in Home Assistant is dropped from what BRAM watches, and noted in Findings. One that was already gone when BRAM started is listed in Findings for you to remove.

## Turned off in Home Assistant

An entity you disable in Home Assistant is no longer watched or shown, even if it is shared, and comes back if you enable it again. Findings lists each one, so a safety sensor is not dropped without you knowing.

## Names

BRAM uses the names you see in Home Assistant. A name a device gave itself with a serial number in it, such as `H2D_0947AJ612800457`, is shown as its model, or its room and type, instead: **H2D**, **Master Bedroom presence**. To choose a name, rename the device or entity in Home Assistant.

## BRAM's suggestions

**Configure > BRAM's suggestions** lists what matters most and BRAM cannot see yet: people, locks and doors, safety sensors, and a motion sensor for each area without one. Remove what you do not want, and **Submit**. Nothing is shared until you do. These come from simple rules, not a model.

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
| Safety sensors | Moisture, smoke, carbon monoxide, gas, heat, safety, and tamper sensors | leak or dry; detected or clear |
| Motion | Motion, occupancy, presence, and moving sensors | detected, clear |
| Lights | `light` | on, off |
| Switches and fans | `switch`, `fan` | on, off |
| Media players and speakers | `media_player` | on, off or idle |
| Voice assistants | `assist_satellite` | in use, idle |
| Thermostats, temperature, humidity | `climate`, temperature and humidity sensors | The mode and readings |
| Anything else | Other sensors, weather, vacuums, water heaters, alarm panels, updates, and more; choose one by one | Its state as Home Assistant shows it; no alerts |

"How long" restarts when Home Assistant restarts. BRAM also sees, for shared devices only: their room, how long they have been that way, brightness, position, battery, what a media player is playing and how loud, what a thermostat is doing, and the picture Home Assistant shows for a person or media player. It never gets a person's coordinates, or pictures from outside Home Assistant. Pictures are kept in memory only.

 History covers everything here except thermostats and readings. Anything else, or a state it does not recognize, is *unknown*.

## Location

| What | Where it comes from |
|---|---|
| A device's room and floor | Its area in Home Assistant; set areas and floors there |
| Whether a room is occupied | The motion and presence sensors in that area. Clear only if all of them say so |
| The room a person is in | Found by itself: room sensors on their devices, or a sensor with their name whose value is one of your areas, such as *Alex Room*. **Configure > Fix a person's room** overrides it |
| A named place, such as Work | The person's zone in Home Assistant |

Coordinates are never shared. If a room is not known, BRAM says only home or away. On the command deck, press **by type** to arrange the house by room.

## What to add first

1. **Everyone who lives there.** Otherwise "away" is wrong.
2. **Outside doors and locks**, for [watching](watching.md).
3. **Safety sensors**, for alerts.
4. **Motion sensors and lights**, so chat answers well and future learning has something to learn from.

## The device page

**BRAM Server** shows the connection. Each chosen device has a line with what the server believes. *Unavailable* means the server is not connected.

**Visit** opens BRAM's page. **Mood** changes BRAM's [personality](personality.md).

| Button | Does |
|---|---|
| Send test message | Sends to your chosen phones |
| Allow stopped messages | Undoes every **Stop these** |
