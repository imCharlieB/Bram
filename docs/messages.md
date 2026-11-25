# Alerts and messages

## Who tells you what

| Event | Sent by | Where |
|---|---|---|
| Leak, smoke, gas, carbon monoxide, heat, safety, or tamper: at once, then up to 11 reminders until acknowledged, even in quiet hours | Home Assistant | HA app, and inside Home Assistant |
| Safety sensor silent for 5 minutes | Home Assistant | HA app |
| Lock and door watching, if turned on | Home Assistant | HA app |
| BRAM Server lost for 3 minutes | Home Assistant | HA app |
| Home Assistant lost for 3 minutes: reminders until acknowledged or it returns | BRAM Server | Telegram, ntfy |
| A monitor not answering, or back | BRAM Server | Telegram, ntfy |

Home alerts do not need the server, a model, or the internet connection between them, but your phone still needs to be reachable. Only safety sensors you chose in BRAM's options are covered. Safety alerts use fixed wording; personality is not used in alerts.

Home Assistant and each of Telegram and ntfy send at most 10 routine messages a day. Safety alerts are not limited by that.

## Home Assistant app

1. Install the Home Assistant app on your phone and allow notifications.
2. **Settings > Devices & services > BRAM > Configure > Phone alerts and quiet hours**. Choose your phones.
3. Set quiet hours if you want them. They apply only to Home Assistant's messages and never to safety alerts.
4. On BRAM's device page, press **Send test message**.

Safety alerts have **Acknowledge**. Silent-sensor messages have **Stop these**.

**Fallback (off by default):** a leak or smoke alert nobody answers for 5 minutes can also go to Telegram and ntfy. It needs the BRAM Server to be connected.

## Who gets what

| List | Gets |
|---|---|
| Phones that get everything | Safety alerts, lock and door messages, notices, daily summary |
| Phones that get safety alerts only | Leak, smoke, gas, carbon monoxide, heat, and other safety alerts |

Sharing a **person** with BRAM sends that person nothing. Anyone who gets a safety alert can acknowledge it for everyone. Telegram goes to the one linked account, and ntfy to whoever subscribes to its topic.

## Daily summary

In **Phone alerts and quiet hours**, set **Daily summary at**. Once a day it lists what is open, not locked, or cannot be seen, who is home, and low batteries. It is sent at that time even in quiet hours, uses fixed wording, and needs no server. Leave it empty for none.

## Watching locks and doors

**BRAM > Configure > What BRAM watches for.** For problems with Home Assistant, see [Problems](problems.md). The lock and door rules are off until you turn them on, and cover only the locks, doors, windows, and garage doors BRAM can see.

| Choice | Tells you when | In quiet hours |
|---|---|---|
| Unlocked at night | A lock has been unlocked for 2 minutes during your night hours | Yes |
| Open or unlocked while away | It has been so for 2 minutes and everyone BRAM can see is away | Yes |
| Left open | It has been open as long as you set | After they end |
| Offline | It has been unreachable for 5 minutes | After they end |

Three or more routine messages at once become one, without a button. Night and away messages are never grouped.

You are told once each time, at most 20 times a day. **Stop these** stops one message for one device; undo it with **Allow stopped messages** on the device page.

**Away** counts only people BRAM can see. Add everyone who lives there, or it may call the house empty when it is not. If anyone's location is unknown, BRAM does not call the house empty.

## Telegram

Optional. Messages pass through Telegram's servers and are not end-to-end encrypted.

1. In Telegram, message **@BotFather**, send `/newbot`, and follow its questions. Copy the token and keep it private.
2. On BRAM's **Messages** page, paste the token, check **Turned on**, and **Save**.
3. Press **Link my account**, open the link, and press **Start** within 10 minutes.
4. Press **Send test**.

Only the linked account is answered. If the token leaks, use `/revoke` in @BotFather and save the new one. The token is stored in the server's data folder.

## ntfy

Optional, and not needed if you use Telegram. It runs beside BRAM and works at home or over a VPN; away from home it delivers when you reconnect. Traffic to it is not encrypted.

1. On BRAM's **Messages** page, check **Turned on**. Leave **Address BRAM uses** as `http://ntfy:80`. Set **Address your phone uses** to `http://SERVER:2586`. **Save**.
2. Install the free **ntfy** app (Play Store or F-Droid; no account needed) and allow notifications and instant delivery. If messages arrive late, set its battery use to Unrestricted.
3. Scan the QR code on BRAM's page, or open the page on your phone and tap the link. If neither opens ntfy, add a subscription in the app, choose another server, and enter the address and topic shown.
4. Press **Send test**.

Treat the topic like a password: anyone on your network who knows it can read your alerts. **New secret topic** replaces it. The server refuses everything except BRAM's randomly named topics. iPhones need extra ntfy setup for instant alerts.

## Monitors

See [Monitors](monitors.md).

## What buttons and replies can do

Buttons can acknowledge, snooze, or stop a routine message. Safety alerts can only be acknowledged. Typed text is never a command, even in Telegram chat, and nothing here can approve or control anything. Undo **Stop these** from Telegram or ntfy on the **Messages** page. Undo **Stop these** from the HA app with **Allow stopped messages** on BRAM's device page.

## Try it

- Stop the BRAM container for 4 minutes. Home Assistant should tell you, and again when it is back.
- Stop Home Assistant for 4 minutes. Telegram and ntfy should tell you.

## Problems

| Problem | Try |
|---|---|
| No phone in the list | Sign in to the Home Assistant app, then reload BRAM's options |
| HA test message fails | Allow notifications for the app; choose a phone in BRAM's options |
| Telegram says it refused | Check the token, and that the server has internet access |
| Nothing after linking Telegram | Press **Start** in the chat; links last 10 minutes |
| ntfy test is Sent but nothing arrives | Check the phone can reach port 2586 and that the topic matches exactly |
| ntfy buttons do nothing | The phone must be able to reach **Address your phone uses** |
| A monitor is not answering but the thing is up | Check its type and the reason shown; remove it and add it again with the right type |
| ntfy suggests WebSockets | Optional; you can enable or dismiss it |
| Ntfy or monitor address refused | Only addresses on your own network are accepted |
