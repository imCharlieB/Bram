# Security check

Looks at Home Assistant's own settings. It reads only, changes nothing, and scans nothing on your network. **A clean result does not mean your home is secure.**

## Turn it on

In **Settings > Devices & services > BRAM > Configure**:

| Where | Setting | Does |
|---|---|---|
| Server access | Security check of Home Assistant | Lets you ask "Is my home secure?" |
| Watching | The security check finds something new | Checks every hour and messages your phones once |

Both are off by default. The hourly check first learns what is already there, so only later changes are messages. Quiet hours hold everything except new accounts, new tokens, and an unencrypted outside address.

## What it checks

| Check | Reported when |
|---|---|
| New accounts and tokens | An administrator or long-lived token appears (hourly check only) |
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

## What it does not check

Your router and network, Home Assistant Cloud remote access, Z-Wave security levels, app ports, passwords, and two-factor sign-in. If a check fails to run, it is listed here too in the answer.

Account names and token ids never leave Home Assistant. Findings can name devices.
