# Learning

BRAM can suggest better night hours and a better left-open time. Off by default, and it uses no model.

## Turn it on

**Settings > Devices & services > BRAM > Configure > Learning > Learning is on.** It needs motion sensors, doors, or locks that BRAM can see, and **Keep history** on BRAM's page (see [History](history.md)). The page shows how many nights it has found.

Learning reads BRAM's history, the one record of what happened in your home. It keeps no notes of its own. Nights recorded before you turned Learning on count too, so with two weeks of history the first suggestion can come the same day. Needs Home Assistant's BRAM and the server both on 0.34.0 or later.

## What it does

| Step | Detail |
|---|---|
| Reads | From history, each night from 6 PM to noon: the longest quiet stretch, 3 to 12 hours. Each day: how long doors stayed open. The last 60 days |
| Skips | Nights the server was not recording for at least nine tenths of, and nights with no clear quiet stretch |
| Waits | 14 nights, or 14 days and 20 openings |
| Suggests | Only a change of 30 minutes or more, or 10 minutes for left open, at most once every 30 days |

Sunday to Thursday and Friday to Saturday are worked out separately.

## Answer a suggestion

It appears in **Settings > System > Repairs**, with how many nights support it.

| Choice | Result |
|---|---|
| Approve | The hours change |
| Not now | Ignored; another may come in 30 days |
| Never suggest this | That kind is never suggested again |

An unanswered suggestion goes away after 30 days. A suggestion can change only the hours and left-open time. It cannot turn a rule off or touch safety alerts.

## On BRAM's page

**History > Learning**, and **Learned** on Home, show how many nights history has and any suggestion waiting. Approving stays in Home Assistant, because a suggestion changes when lock and door alerts apply, and those settings never depend on the server.

If the server is down, your alerts and night hours keep working in Home Assistant. Those nights are not recorded, so a suggestion comes a little later.

## Undo or start over

On the same **Learning** page in Home Assistant:

| Choice | Does |
|---|---|
| Undo the last change I approved | Puts back the hours you had before |
| Erase what BRAM has learned and start over | Counts only nights from today on, and forgets any waiting suggestion and your Never answers. History itself is kept; delete it under **History > Clean up**. Your current hours stay |

Turning learning off stops suggestions. History keeps recording while **Keep history** is on.
