# 3D printers

BRAM finds your printers by itself from the integration each one uses: Bambu Lab, Moonraker (Klipper), OctoPrint, PrusaLink, and others where they use the same names. Turn it on in **BRAM > Configure > 3D printers**, **What BRAM watches for**, or **Recommended setup**. **3D printers** has a switch for each printer found; turn off any you do not want watched. A new printer starts on.

**BRAM only watches.** It cannot start, pause, stop, or heat anything. It is not a fire alarm.

## Shown on Home

State, progress, time left, file, and the nozzle, bed, and chamber temperatures with their targets. A printer whose integration is unreachable shows **Off**.

## Messages

| Told when | After |
|---|---|
| Finished, failed, or stopped | At once |
| Paused | 1 minute |
| Reports a problem, such as a Bambu HMS error, with what it says | 1 minute |
| Stopped answering during a print | 5 minutes |
| Not printing, but a heater is still set and hot | 20 minutes |
| Printing, but the nozzle or bed is far below its target | 15 minutes |

- Out of filament usually shows as paused or as a problem.
- Off while idle is normal and never a message. Cooling down after a print is not a heater left on.
- Quiet hours hold messages until they end. **Stop these** stops one kind for one printer; undo it with **Allow stopped messages**.
- Some printers do not say how a print ended. Then 99% or more counts as finished, and less as stopped.
- The same printer connected through two integrations appears twice; disable one device in Home Assistant.

## Remembered

With **Keep history** on, each print is kept: printer, file, result, length, and filament weight if the printer reports it. See **History > 3D prints**. A print BRAM did not see start has no length.

## Ask

"How is the print going?" "How long is left?" "What did I print this week?"

## Not yet

Pictures, spotting failed prints by camera, power used, and pausing with a tap are in the [plan](roadmap.md#3d-printers).
