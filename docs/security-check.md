# Security check

Looks at Home Assistant's own settings, and at what Home Assistant already knows about your network and radios. It reads only, changes nothing, and scans nothing. **A clean result does not mean your home is secure.**

## Turn it on

In **Settings > Devices & services > BRAM > Configure**:

| Where | Setting | Does |
|---|---|---|
| Server access | Security check | Lets you ask "Is my home secure?" |
| Watching > Home Assistant and security | Run the security check every 10 minutes | Checks every 10 minutes and messages your phones once about anything new |

Both are off by default. The check first learns what is already there, so only later changes are messages. Quiet hours hold everything except new accounts, new tokens, and an unencrypted outside address.

## What it checks

| Check | Reported when |
|---|---|
| New accounts and tokens | An administrator or long-lived token appears (the regular check only) |
| New device on your network | A device BRAM has not seen before gets a network address. Urgent if everyone BRAM can see is away (the regular check only). See below |
| New paired device | A new Zigbee, Z-Wave, Matter, Thread, or HomeKit device is paired, including Zigbee2MQTT (the regular check only) |
| Z-Wave locks | A Z-Wave lock was paired without S2 security; pair it again with S2 |
| Router | The router integration has a firmware update waiting, or its guest Wi-Fi switch is on |
| Apps | A Home Assistant app runs with protection mode off, or opens ports on the host |
| Administrators | More than two |
| Old tokens | Made more than 90 days ago. Home Assistant does not record whether they are used, so check before deleting |
| Failed sign-ins | Home Assistant is showing a failed sign-in notice |
| Sign-in bypass | Trusted networks skip the password |
| Voice assistants | A lock, alarm, garage, door, or gate is exposed to Assist, Alexa, or Google |
| Webhooks | An automation can be started from the internet |
| Offline devices | A lock, alarm, garage, door, gate, or camera has been offline for 30 minutes. Cameras on 3D printers are left out |
| Zigbee joining | A bridge's permit-join switch is on |
| Outside address | Uses plain http |
| UPnP | The UPnP integration is set up, which does not prove the router allows it |
| Updates | Home Assistant's own updates are waiting |

## Devices on your network

BRAM uses two sources, whatever router you have:

- **Home Assistant's own network discovery**, which notices any device that asks your network for an address. It is on in a normal Home Assistant. It sees the part of the network Home Assistant is on; a device on another network or VLAN, or with a fixed address, may not show.
- **A router integration's device list**, if you have one with device tracking, such as UniFi, FRITZ!Box, eero, Netgear, or OPNsense from HACS.

The first look learns every device already there. After that, each new one is told once, with its name, or its address if it has no name. Coming: connecting BRAM to an OPNsense router directly, with a read-only key, to see every device.

## What it does not check

Home Assistant Cloud remote access, passwords, and two-factor sign-in. If a check fails to run, or has nothing to look at, it is listed in the answer.

Account names and token ids never leave Home Assistant. Findings can name devices.
