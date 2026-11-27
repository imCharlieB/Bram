# History and trends

BRAM can remember what your shared devices did, in its own database. Off until you turn it on: while it is off, the History page on BRAM's page starts with **Start keeping history**. Press it and enter your password. **Keep history** below it turns it off again.

It records as things happen: each reading every minute, and each change when it happens. Nothing from before you turned it on is recorded, except the past readings below.

Without it, BRAM has no trends, no climate graph on Home, and nothing to learn from. [Learning](learning.md) reads its quiet nights and door times from this history, so it needs **Keep history** on.

## What it keeps

| Kind | Detail |
|---|---|
| Readings | Every shared sensor with a number, thermostats' current temperature, and weather: sampled each minute, kept as low, average, and high for every 5 minutes and every hour |
| Heating and cooling | Each run: start, end, action, mode, preset, fan, what it was set to, inside and outside temperature. Changing the setting starts a new line |
| Changes | Doors, locks, motion, people, lights, and other on or off devices |

- A device that is unknown or disconnected is recorded as unknown, never as its last value.
- Outside temperature comes from a shared weather entity.
- Run times need a thermostat that reports what it is doing. Some report only their mode; BRAM cannot tell when those run.
- A run BRAM did not see all of is marked **not all seen**.

## Past readings

If **History of shared devices** is on in Home Assistant, under **BRAM > Configure > Server access**, BRAM brings in the hourly averages Home Assistant already keeps for those sensors. Heating and cooling runs have no past to bring in.

## Two sensors in one room

BRAM compares each thermostat's own sensor with other temperature sensors in the same Home Assistant area, at the same moments. Share both, and put both in the area.

## Ask

"How long did the AC run each day?" "Is the bedroom thermostat reading right?" Answers list the measured numbers below.

## Space

At 80% of the limit BRAM asks you what to remove, by Telegram or ntfy if set up, and in [Findings](findings.md). At the limit, if you have not answered, the oldest 5-minute readings are removed; their hourly ones stay, and you are told. Nothing else goes without you.

## Clean up

**History > Clean up** lists every device with its size, biggest first. Choose devices, what to do, and how old, and press **Make the list**. BRAM shows exactly how many entries would go. Nothing changes until you press **Confirm** and enter your password, within 10 minutes.

| Choice | Does |
|---|---|
| Shorten to hourly | Removes 5-minute readings and keeps hourly ones |
| Delete | Removes readings, hours, changes, and runs |
| Stop keeping | Records nothing more for that device; keeps what is there |
| Keep again | Undoes Stop keeping |

Or ask in chat: "delete hall motion readings older than 90 days", "shorten attic readings older than a year", "stop keeping the garage sensor", "delete motion data before June". Chat only makes the list; you still confirm it on the page. If a device or date is unclear, no list is made. Sizes by device are close estimates.

The log, findings, and Home Assistant's own history are not touched.

## Turn off or delete

Turning it off stops recording and keeps what is there. **Delete all history** removes it. Removing a home deletes its history. Space already used is reused, and the file may not shrink.
