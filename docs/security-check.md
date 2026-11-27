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

> **Home Assistant only sees its own network.** If you split your home into networks or VLANs, such as one for cameras and one for smart devices, Home Assistant cannot see devices on the others, or devices with a fixed address. To see every network, [connect your router](#connect-your-router) to BRAM.

BRAM uses every source it has, whatever router you use:

- **Your router, connected to BRAM**: every device on every network and VLAN, and the router's firmware. OPNsense for now.
- **Home Assistant's own network discovery**, which notices any device on Home Assistant's network that asks for an address. It is on in a normal Home Assistant.
- **A router integration's device list** in Home Assistant, if you have one with device tracking, such as UniFi, FRITZ!Box, eero, or Netgear.

The first look learns every device already there. After that, each new one is told once, with its name and network, or its address if it has no name. If everyone BRAM can see is away, it is urgent.

## Connect your router

BRAM reads your router; it never changes it.

**OPNsense**

1. In OPNsense, **System > Access > Users**: add a user for BRAM. Give it only these privileges: **Diagnostics: ARP Table**, **Status: DHCP leases**, and **System: Firmware**. Without the leases privilege it still works, but devices have no names.
2. On that user, under **API keys**, select **+** to create a key. OPNsense downloads a file with the key and secret.
3. On BRAM's page, **Settings > Router**: enter the router's address, such as `https://192.168.1.1`, the key, and the secret, and select **Connect**. Enter your BRAM password.

BRAM trusts the router's certificate the first time and refuses to connect if it changes, so the key only goes to your router. It looks every 5 minutes. **Settings > Router** shows how many devices it sees, grouped by network, and whether a firmware update is waiting. **Disconnect** forgets the address and key. Only an address on your own network is accepted.

## What it does not check

Home Assistant Cloud remote access, passwords, and two-factor sign-in. If a check fails to run, or has nothing to look at, it is listed in the answer.

Account names and token ids never leave Home Assistant. Findings can name devices.
