# Learning

BRAM can suggest better night hours and a better left-open time. Off by default, and it uses no model.

## Turn it on

**Settings > Devices & services > BRAM > Configure > Learning > Suggest better hours.** It needs motion sensors, doors, or locks that BRAM can see. The page shows how many nights it has noted.

## What it does

| Step | Detail |
|---|---|
| Notes | Each night from 6 PM to noon: the longest quiet stretch, 3 to 12 hours. Each day: how long doors stayed open |
| Skips | Nights Home Assistant was not running for at least nine tenths of, and nights with no clear quiet stretch |
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

**History > Learning** shows how many nights are noted and any suggestion waiting. Approving stays in Home Assistant, because a suggestion changes when lock and door alerts apply, and those settings never depend on the server.

## Undo or start over

On the same **Learning** page in Home Assistant:

| Choice | Does |
|---|---|
| Undo the last change I approved | Puts back the hours you had before |
| Erase what BRAM has learned and start over | Forgets the nights noted, any waiting suggestion, and your Never answers. Your current hours stay |

Turning learning off stops noting new nights and keeps what was noted.

Summaries stay in Home Assistant for 60 days. A copy of each summary is kept in the BRAM Server's database until you delete everything learned or remove the home. Removing BRAM deletes Home Assistant's.
