# Findings

Everything BRAM found and what became of it, on BRAM's page under **Findings**.

| Comes from | Examples |
|---|---|
| Safety and silent sensors | Leak, smoke, a sensor that stopped reporting |
| Locks, doors, windows, and motion | Unlocked at night, left open, open at night, open while heating or cooling, open or motion while everyone is away, offline |
| Temperature and humidity | Too hot, too cold, near freezing, humid |
| [Learning](learning.md) | A suggestion waiting, and how it was answered |
| [Problems](problems.md), if turned on | Failed integrations, repeating errors, batteries, offline devices, automations, backups |
| [3D printers](printers.md), if turned on | Finished, failed, paused, heater left on |
| [Security check](security-check.md), if its regular check is on | New token, new device on your network, failed sign-in, offline camera |
| [Monitors](monitors.md) and connection | A monitor not answering, Home Assistant not answering |
| Messages | Daily summary |

Each finding is one line, however often it happens: first and last time, how many times, whether you were told, acknowledged, or stopped it, and when it was over. **Story** shows each step, including messages to your phones.

- **Hide** takes a finding off the list, and off Needs you on Home, until it happens again; then it is back. Hidden ones are under **Show > Hidden**, with **Show again**. Hide never stops a message to your phone; use **Stop these** for that. Hiding the same one again and again leads BRAM to suggest fewer messages about it; see [How often BRAM tells you](how-often.md#suggestions-from-what-you-do).
- **Stop these** and **Less often** appear beside a finding whose phone message had them. See [How often BRAM tells you](how-often.md).
- Home Assistant keeps up to 500 notes while the server is away and sends them when it is back. Alerts never wait for this.
- Something that ended while Home Assistant was off is closed as *No longer seen*, up to two hours after it starts.
- Locks and doors are recorded only if their rule is on, and wait the rule's time first.
- Chat knows what is open.
- Findings are kept until the home is removed. They are not history and do not need **Keep history**.

