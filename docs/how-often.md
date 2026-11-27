# How often BRAM tells you

BRAM tells your phone about what matters, without repeating what you already know. These rules are in code, the same for every kind of message, and no model decides them.

## Four grades

| Grade | Phone | Examples |
|---|---|---|
| **Urgent** | Repeats until someone acknowledges | Leak, smoke, carbon monoxide, gas, heat |
| **Each time** | Every time it happens | Door left open, print finished or paused, unlocked at night, open while everyone is away |
| **Once until fixed** | Once. Again only if it comes back after being fixed for a whole day | Integration failed, device offline, printer heater left on, sensor stopped reporting |
| **Reminder** | Once a month at most. Always on BRAM's page | Lubricate, clean, replace a filter, firmware or update available, refill, due for service |

## How a message gets its grade

1. **What kind of thing it is.** Safety alerts are always urgent. A door left open, or a print finishing, happens each time. A failure or something offline is once until fixed.
2. **What the words say.** Words about looking after something, such as *lubricate*, *clean*, *replace*, *filter*, *firmware*, *update available*, *refill*, *due*, or *service*, make it a reminder, whatever sent it. This is how a printer's "Threaded rods need lubrication" is told once and then left on the page.
3. **What you chose.** Nothing becomes quieter on its own. You decide with the buttons below.

## Same thing, or something new

- The same words from the same device are the same thing. Different words are new and told at once, such as a printer that reports a new problem.
- A problem that goes away and comes back within a day is the same event, so a flickering warning is told once.
- Something that happens each time, like a door left open, is told each time. Its own rule already waits for it to last, so a door that is opened and closed is not news.

## Your buttons

| Button | Does | Undo |
|---|---|---|
| **Acknowledge** | Stops an urgent alert repeating | |
| **Stop these** | No more of this message from this device | **Allow stopped messages** on BRAM's device page |
| **Less often** | At most once a day. Offered from the third time in a week | **Allow stopped messages** |

The phone shows the buttons when you expand the message: drag it down on Android, or press and hold it on iPhone.

**Stop these** and **Less often** also appear on BRAM's page, under **Needs you** on Home and beside the finding under **Findings**, for as long as the message is open. They are the same buttons the phone was given, and Home Assistant only accepts a button it offered for that message, once. **Acknowledge** is only on the phone, so nothing on BRAM's page or server can quiet a safety alert. Needs Home Assistant's BRAM and the server both on 0.33.0 or later.

BRAM never decides by itself that something told often is unimportant. A door left open every night may be exactly what you want to know.

## Suggestions from what you do

BRAM can ask instead. When, over two weeks, you **Hide** the same finding 3 times, or your phone is told about it 5 times and nothing is done (no button, no Hide), BRAM suggests fewer messages about it. Your phone gets one message, at most one a day, that opens the review page in the Home Assistant app. It shows the message and why, with **Stop these**, **Less often**, **Not now**, and **Never suggest this**. Nothing changes until an administrator answers there.

- Only routine messages: locks and doors, 3D printers, and Home Assistant problems. Never a safety alert or a silent safety sensor.
- Only the buttons your phone was really given for that message.
- Each is asked about at most once in 30 days, and never again after **Never suggest this**.
- Undo **Stop these** or **Less often** with **Allow stopped messages** on BRAM's device page.
- Needs Home Assistant's BRAM and the server both on 0.37.0 or later.

## Never held back

- Urgent alerts, which no quiet hours, limit, button, or grade can stop.
- Locks and doors unlocked or open at night or while everyone is away, motion while everyone is away, and near freezing: these ignore quiet hours, and **Less often** is not offered.

## Also limiting messages

- **Quiet hours** hold routine messages until they end.
- **Daily limits**: 10 notices, 20 lock and door messages, 8 problem messages, and 30 printer messages a day.
- **Grouping**: three or more routine messages at once arrive as one.

Everything held back is still in [Findings](findings.md), with its story.
