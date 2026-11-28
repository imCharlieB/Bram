# Chat

Type to BRAM on its home page. It uses the model and personality from **Settings**.

| It can | It cannot |
|---|---|
| Answer about the entities you shared, your monitors, and recent alerts | Control, unlock, or approve anything |
| Answer general questions from the model's own knowledge | Search the internet, see cameras, or set reminders |
| Keep up with the current conversation | Remember it later |

- BRAM [finds problems](problems.md) by itself; chat is for asking about them.
- **It can look things up if you let it.** In **BRAM > Configure > Server access**:

| Turn on | Ask | It reads |
|---|---|---|
| **History of shared devices** | "When was the back door last opened?" "How often did the garage open this week?" | 10 days of one to three devices named in the question, only devices BRAM can see |
| **Cameras** | "Is anyone on the porch?" "What's in the driveway?" | The camera's picture now, for cameras with Describe on. See [Cameras](cameras.md#ask-a-camera) |
| **Home Assistant problems** | "Any errors in Home Assistant?" "Any low batteries?" | Grouped errors and warnings, failed integrations, open repairs, low batteries, updates |
| **Security check** | "Is my home secure?" "Is anything exposed?" | See [Security check](security-check.md) |

  [BRAM's own history](history.md) is separate: press **Start keeping history** on BRAM's **History** page. Then you can ask "How long did the AC run each day?" and it reads heating and cooling runs, and thermostats against room sensors, for 7 days.

  Lengths of time are worked out by code and shown under the answer, because models are bad at arithmetic. Use the device's name in a history question. Causes it suggests for a problem are guesses, and it fixes nothing.

- **Check important answers.** Models make mistakes. Under an answer BRAM lists what the matching sensors actually say. *Unknown* means it cannot tell.
- **"Anyone home"** covers only people you shared. It is not proof the house is empty.
- **Nothing is saved to disk.** A chat is forgotten when you clear it, sign out, leave it for 30 minutes, or restart the server. The last 12 messages are kept in mind.
- **Stays on your network.** The model must be on your own network.
- It answers one question at a time, and shares your model with anything else using it.
- It is not an emergency service and cannot call one.

## What to ask

| Ask | Needs |
|---|---|
| "Is the back door locked?" "Who is home?" "What's on?" | The device shared |
| "When was the garage last opened?" | **History of shared devices**, under **Server access** |
| "Any errors in Home Assistant?" "Low batteries?" | **Home Assistant problems**, under **Server access** |
| "How is the print going?" | **Watch 3D printers** on, and the printer switched on, under **Watching > 3D printers** |
| "Is my home secure?" | **Security check**, under **Server access** |
| "How long did the AC run each day?" "Is the bedroom thermostat reading right?" | **Keep history** on, on BRAM's History page |
| "Delete hall motion readings older than 90 days" | **Keep history** on. You confirm the list on the page |

## Memory

Off until you turn it on, on BRAM's page: **Settings > Memory**, then **Turn on** and your password. Then, in chat on BRAM's page, Assist, or Telegram:

| Say | BRAM |
|---|---|
| "Remember that the neighbor's name is Joe." | Keeps it: "I'll remember that: the neighbor's name is Joe." |
| "What do you remember?" or "What do you remember about Joe?" | Lists what it remembers |
| "Forget about Joe." | Forgets each memory with those words |

Other ways work too: "Bram, remember that...", "Can you remember...", "Please remember...", "Don't forget that...", "Keep in mind...". These are handled by BRAM itself, not your model, and it only remembers what someone asks it to. If your model ever says it will remember something that BRAM did not keep, a note under its answer says it was not saved. When you ask anything else, the memories that fit go to your model with your question, as information and never as orders: "Remember to unlock the door" cannot unlock anything. Each memory notes who said it, from BRAM's login name or the Home Assistant user who asked in Assist.

Your conversation also carries over: what you said on BRAM's page continues in Assist and Telegram, and after the server restarts. A conversation untouched for a week is let go. **Clear** on Home clears it.

Everything remembered is listed under **Settings > Memory**, each with **Change** and **Delete**. You can add one there too. **Forget everything** deletes all of it. Turning memory off asks whether to forget everything too; if you keep it, it stays unused until memory is on again. Camera lessons are kept separately, under **Settings > Cameras**.

## In Telegram

Off by default, because answers about your home pass through Telegram, which is not end-to-end encrypted. On the **Messages** page, set up Telegram, check **Let me chat with BRAM here**, and **Save**. Only the linked account is answered.

### Voice notes

With Telegram chat on and [hearing](voice.md) set up, send a voice note of up to 30 seconds. BRAM shows what it heard. The recording passes through Telegram, then is turned into text on your network and not stored.

## In Home Assistant's Assist

**Settings > Voice assistants**: add an assistant, or open one, and choose **BRAM Assist** as its conversation agent. Your other choices, such as how it hears and speaks, stay the same. Choose the old agent to go back.

- It answers only about that home, and not about monitors or other homes.
- **Anyone who can use that assistant can ask** who is home and what is locked.
- It uses the personality you set in BRAM.
- BRAM cannot control anything. If the assistant has **Prefer handling commands locally** on, Home Assistant itself still handles commands such as turning on a light.

## Problems

| Problem | Try |
|---|---|
| Choose a model first | **Settings > Model** |
| Still thinking | Wait for the last answer |
| Ollama request failed | Check that Ollama is running and reachable |
| It cannot see a device | Add it in BRAM's options in Home Assistant |
