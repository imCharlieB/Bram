# BRAM's Home page

Home is your look into what BRAM sees and what it is doing. It is not a dashboard of every device: Home Assistant has those.

In the middle is BRAM's brain, a knot of light threads. When something happens, it takes on that system's color for a few seconds: green for people, warm yellow for lights, amber for doors and locks, red for safety, sky blue for climate, violet for printers. Everything BRAM watches orbits it: Home Assistant, people, security, safety, climate, lights, printers, your monitors, your router, cameras, your model, messages, and learning, each with a short reading. One that is down turns red. When something happens in one of them, it flashes and a pulse runs into the brain. A card saying what happened, with its room on a tab (not for motion ending), appears in one of four places around the brain, stays a few seconds, and goes.

The version also shows next to BRAM's name at the top of every page. The title on Home shows what is running: the BRAM Server's version, and BRAM's in each connected Home Assistant. It turns amber when they differ in features, such as 0.40 and 0.41; update both. A fix on one side only, such as 0.40.3 and 0.40.4, is fine.

Along the bottom is the command bar: Findings, History, and Messages on the left, Mood, Settings, and Log on the right, and the chat box in the middle, with **Send**, and with [voice](voice.md) set up, **Hold to talk** (the microphone) and **Speak answers** (the speaker) as icons inside it.

## Alerts over the brain

When something needs you, a window opens over the brain, like a screen in a command center: see-through, with cut corners, a glowing edge, and its label on a tab. The newest is open; older ones fold down to their title, and clicking a title opens that one:

| Window | When | Closes |
|---|---|---|
| Red | A safety alarm, a safety alert, a finding that matters most, or Home Assistant not connected | Only when you close it with **×**, or when it is over |
| Amber | Another alert or finding that needs you, or a person on a camera | After 30 seconds |
| Cyan | Another camera event, or a monitor answering again | After 15 seconds |

A camera window opens only for an event BRAM told your phone about, or held for quiet hours, under your [camera messages](cameras.md#what-it-tells-you). Every other event only updates **Looking at**. A camera window asks **Does it matter?**: see [Teach BRAM a camera](cameras.md#teach-bram-a-camera).

A finding's window has the same **Story**, **Stop these**, **Less often**, and **Hide** as under **Needs you**. A camera's window shows Frigate's picture. Windows open only for what is new while the page is open; what was already there is listed under **Needs you**. At most three are open at once. Cameras share one window: a new camera event replaces the last one, so several cameras at once never pile up.

While something needs you, rings keep going out from the brain: red and often for safety and the most important findings, amber now and then for the rest. While BRAM is thinking about a chat answer, arcs sweep around the brain.

Inside the brain a geodesic sphere turns, and around it rings of glowing dots ripple; when BRAM speaks they wave with its voice. When it answers you, its name forms in the middle from dots, then scatters. Every few seconds a line draws out from the brain to one of your room readings, such as **LIVING ROOM 74°**. Moving between pages, the panels fold into a line and the new ones unfold one after another; with reduced motion set on your device, they simply appear.

Under the brain is what BRAM is saying, written out as it says it, and what it is doing now: **Watching**, **Listening**, **Thinking**, or **Speaking**. The ring around the brain moves with its voice. With [voice](voice.md) on, the ring follows the real sound, both when BRAM speaks and while you hold to talk.

Screens down both sides each have a tab. Point at one, or tab into it, and it lights up.

| Screen | Shows |
|---|---|
| **Today** | The date and time |
| **House** | Your rooms, taken from Home Assistant's areas. A room lights up when someone moves there, turns amber when a door or window in it is open, and shows who is in it |
| **System** | How much BRAM can see, how much is shut and locked, nights learned, and messages sent today. Below that, each link to Home Assistant and your monitors, and why one is down |
| **Monitors** | Each of your [monitors](monitors.md): up, down with why, or checking. **Manage** opens them. A monitor going down opens a red window; coming back, a cyan one |
| **3D printers** | Only while a print is running or paused: progress, time left, file, and nozzle, bed, and chamber temperatures against target. See [3D printers](printers.md) |
| **Watching** | What is counting down: a door left open with the minutes until you are told, a print until it finishes, and when night starts. Each says why |
| **Looking at** | With [cameras](cameras.md) connected, the latest picture from the cameras BRAM watches, and each camera's last event. Without them, how to connect Frigate |
| **Climate** | Outside temperature, from a weather entity you share with BRAM, such as Pirate Weather's, or else from temperature sensors in your yard or on your porch; the last 24 hours inside and outside; and how long each thermostat has run today. Needs [Keep history](history.md). Without a weather entity, it says to share one |
| **Needs you** | Safety alarms, open alerts, and open [findings](findings.md) that matter, each with what to do. A finding has **Story**, which opens it under Findings; **Stop these** and **Less often** when your phone was given them (see [How often BRAM tells you](how-often.md)); and **Hide**, which takes it off the list until it happens again but does not change what is sent to your phone. Hidden findings are under **Findings > Show > Hidden** |
| **I noticed** | Patterns: a room sensor that reads warmer or cooler than its thermostat over the week, how many nights are learned, and things not reporting |
| **What I did** | What BRAM told your phone, held back, or was told to stop today, and why something was held. See [How often BRAM tells you](how-often.md) |

Screens with nothing to show stay hidden. When a side has more than fits, scroll it. Click a screen's tab to fold it down to just the tab, and again to open it; this browser remembers which are folded.

With history off, **Climate** has **Turn on history**, which goes to the History page.

## A closer look

Click a system on the orbit, or the House, System, 3D printers, Climate, or What I did screen, and its detail opens over the brain. It stays up to date while open. **Escape** or **Close** puts it away.

![Home with the Climate closer look open over the brain](images/home-closer.jpg)

| Click | Shows |
|---|---|
| **People** | Each person and where they are |
| **Security** | Every lock, door, and window, open and unlocked first |
| **Safety** | Every leak, smoke, CO, gas, and heat sensor |
| **Climate** | Each thermostat: what it is doing, now and set temperatures, and how long it ran today; then the rooms' own sensors |
| **Lights** | Every light, those on first |
| **Printers** | Every printer, printing or not |
| **Home Assistant** | Whether it is linked, and anything shared that is not reporting |
| **Messages** | Everything told, held back, or stopped since yesterday, and why |
| **Learning** | How many nights are learned, and what happens at 14 |
| **House** | Each room, what is happening there, and everything in it |
| **System** | Everything BRAM depends on, and whether it answers |

Along the bottom: Findings, History, Messages, Mood, Settings, and Log, with the box to talk to BRAM in the middle. Its answers appear under the brain, with the readings they were based on.

The page refreshes every five seconds. With your system set to reduce motion, nothing moves. On a narrow screen the side screens stack under the brain. **Profile > Look** switches to the plain look.
