# Findings

Everything BRAM found and what became of it, on BRAM's page under **Findings**.

| Comes from | Examples |
|---|---|
| Safety and silent sensors | Leak, smoke, a sensor that stopped reporting |
| Locks and doors | Unlocked at night, left open, offline |
| [Problems](problems.md), if turned on | Failed integrations, repeating errors, batteries, offline devices, automations, backups |
| [Security check](security-check.md), if its hourly check is on | New token, failed sign-in, offline camera |
| [Monitors](monitors.md) and connection | A monitor not answering, Home Assistant not answering |
| Messages | Daily summary |

Each finding is one line, however often it happens: first and last time, how many times, whether you were told, acknowledged, or stopped it, and when it was over. **Story** shows each step, including messages to your phones.

- **Ignore** only moves a finding off the list. It never stops an alert; use **Stop these** for that.
- Home Assistant keeps up to 500 notes while the server is away and sends them when it is back. Alerts never wait for this.
- Something that ended while Home Assistant was off is closed as *No longer seen*, up to two hours after it starts.
- Locks and doors are recorded only if their rule is on, and wait the rule's time first.
- Chat knows what is open.
- Findings are kept until the home is removed. They are not history and do not need **Keep history**.

