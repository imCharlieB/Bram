# Problems with Home Assistant

BRAM checks Home Assistant itself every 10 minutes, without being asked. Turn it on in **BRAM > Configure > Watching > Home Assistant and security** with **Watch Home Assistant for problems**, or in **Quick setup**. To ask chat about problems, also turn on **Home Assistant problems** under **Server access**. It reads only and fixes nothing yet.

| Finds | When |
|---|---|
| Integration failed to start, or keeps retrying | For 30 minutes |
| The same error repeating | 10 times within an hour |
| New repairs | As Home Assistant raises them |
| Low battery | Below 15%, until 20% |
| Phone battery | Below 20% at night and not charging |
| Device offline | Every part of it unavailable for 30 minutes |
| Whole integration offline | All of its devices, three or more |
| Stuck sensor | A temperature or humidity that has not changed in 2 days |
| Automation | Could not be loaded, or uses a device that does not exist |
| Backup | The last automatic one is more than 8 days old |
| Device reports trouble | Its own alert, error, alarm, or fault count is above 0, or its health reading is below 50% |
| Disk almost full, database over 10 GB | |
| Updates waiting | Listed in Findings only, no message |

## Messages

Each problem is told once, and again when it is fixed. Two or more at once are one message, and more than eight become a count, with the rest under [Findings](findings.md). At most eight messages a day. Quiet hours hold them. **Stop these** stops one; undo it with **Allow stopped messages**. A problem that comes and goes is told once a day at most.

## Left out

- Phones, media players, and 3D printers being off or away. Printers have [their own rules](printers.md).
- Shared leak, smoke, lock, and door sensors, which have [their own rules](watching.md).
- Backups Home Assistant has never made, since they may be made another way.
- For two hours after Home Assistant starts, nothing is called fixed, because not every check has had time to look.

Error text has passwords, tokens, accounts, and addresses removed before it leaves Home Assistant. Removal cannot catch everything. What is found is sent to the BRAM Server for Findings.
