# History and trends

BRAM can remember what your shared devices did, in its own database. Off until you turn it on: **History > Keep history** on BRAM's page.

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

If **History of the devices BRAM can see** is on in Home Assistant, BRAM brings in the hourly averages Home Assistant already keeps for those sensors. Heating and cooling runs have no past to bring in.

## Two sensors in one room

BRAM compares each thermostat's own sensor with other temperature sensors in the same Home Assistant area, at the same moments. Share both, and put both in the area.

## Ask

"How long did the AC run each day?" "Is the bedroom thermostat reading right?" Answers list the measured numbers below.

## Space

At the limit, the oldest 5-minute readings are removed; their hourly ones stay. The page shows the size.

## Turn off or delete

Turning it off stops recording and keeps what is there. **Delete all history** removes it. Removing a home deletes its history. Space already used is reused, and the file may not shrink.
