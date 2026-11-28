# Chat and voice

Talking with BRAM: chat, memory, voice, its personality, and blueprints.

On this page: [Chat](#chat) · [Voice](#voice) · [Personality](#personality) · [Blueprints](#blueprints)

## Chat

Type to BRAM on its home page. It uses the model and personality from **Settings**.

| It can | It cannot |
|---|---|
| Answer about the entities you shared, your monitors, and recent alerts | Control, unlock, or approve anything |
| Answer general questions from the model's own knowledge | Search the internet, see cameras, or set reminders |
| Keep up with the current conversation | Remember it later |

- BRAM [finds problems](watching.md#problems-with-home-assistant) by itself; chat is for asking about them.
- **It can look things up if you let it.** In **BRAM > Configure > Server access**:

| Turn on | Ask | It reads |
|---|---|---|
| **History of shared devices** | "When was the back door last opened?" "How often did the garage open this week?" | 10 days of one to three devices named in the question, only devices BRAM can see |
| **Cameras** | "Is anyone on the porch?" "What's in the driveway?" | The camera's picture now, for cameras with Describe on. See [Cameras](cameras.md#ask-a-camera) |
| **Home Assistant problems** | "Any errors in Home Assistant?" "Any low batteries?" | Grouped errors and warnings, failed integrations, open repairs, low batteries, updates |
| **Security check** | "Is my home secure?" "Is anything exposed?" | See [Security check](watching.md#security-check) |

  [BRAM's own history](guide.md#history-and-trends) is separate: press **Start keeping history** on BRAM's **History** page. Then you can ask "How long did the AC run each day?" and it reads heating and cooling runs, and thermostats against room sensors, for 7 days.

  Lengths of time are worked out by code and shown under the answer, because models are bad at arithmetic. Use the device's name in a history question. Causes it suggests for a problem are guesses, and it fixes nothing.

- **Check important answers.** Models make mistakes. Under an answer BRAM lists what the matching sensors actually say. *Unknown* means it cannot tell.
- **"Anyone home"** covers only people you shared. It is not proof the house is empty.
- **Nothing is saved to disk.** A chat is forgotten when you clear it, sign out, leave it for 30 minutes, or restart the server. The last 12 messages are kept in mind.
- **Stays on your network.** The model must be on your own network.
- It answers one question at a time, and shares your model with anything else using it.
- It is not an emergency service and cannot call one.

### What to ask

| Ask | Needs |
|---|---|
| "Is the back door locked?" "Who is home?" "What's on?" | The device shared |
| "When was the garage last opened?" | **History of shared devices**, under **Server access** |
| "Any errors in Home Assistant?" "Low batteries?" | **Home Assistant problems**, under **Server access** |
| "How is the print going?" | **Watch 3D printers** on, and the printer switched on, under **Watching > 3D printers** |
| "Is my home secure?" | **Security check**, under **Server access** |
| "How long did the AC run each day?" "Is the bedroom thermostat reading right?" | **Keep history** on, on BRAM's History page |
| "Delete hall motion readings older than 90 days" | **Keep history** on. You confirm the list on the page |

### Memory

Off until you turn it on, on BRAM's page: **Settings > Memory**, then **Turn on** and your password. Then, in chat on BRAM's page, Assist, or Telegram:

| Say | BRAM |
|---|---|
| "Remember that the neighbor's name is Joe." | Keeps it: "I'll remember that: the neighbor's name is Joe." |
| "What do you remember?" or "What do you remember about Joe?" | Lists what it remembers |
| "Forget about Joe." | Forgets each memory with those words |

Other ways work too: "Bram, remember that...", "Can you remember...", "Please remember...", "Don't forget that...", "Keep in mind...". These are handled by BRAM itself, not your model, and it only remembers what someone asks it to. If your model ever says it will remember something that BRAM did not keep, a note under its answer says it was not saved. When you ask anything else, the memories that fit go to your model with your question, as information and never as orders: "Remember to unlock the door" cannot unlock anything. Each memory notes who said it, from BRAM's login name or the Home Assistant user who asked in Assist.

Your conversation also carries over: what you said on BRAM's page continues in Assist and Telegram, and after the server restarts. A conversation untouched for a week is let go. **Clear** on Home clears it.

**Each person decides for themselves.** Saying "Don't remember me" turns memory off for whoever says it, and forgets what BRAM kept from them; "You can remember me" turns it back on. **Settings > Memory** lists everyone memory holds something for, each with **Remember** to turn on or off. When you correct BRAM, such as "No, my sister is Ann", it reminds you that "Remember that..." keeps it; it does not keep it by itself.

Everything remembered is listed under **Settings > Memory**, each with **Change** and **Delete**. You can add one there too. **Forget everything** deletes all of it. Turning memory off asks whether to forget everything too; if you keep it, it stays unused until memory is on again. Camera lessons are kept separately, under **Settings > Cameras**.

### In Telegram

Off by default, because answers about your home pass through Telegram, which is not end-to-end encrypted. On the **Messages** page, set up Telegram, check **Let me chat with BRAM here**, and **Save**. Only the linked account is answered.

#### Voice notes

With Telegram chat on and [hearing](chat.md#voice) set up, send a voice note of up to 30 seconds. BRAM shows what it heard. The recording passes through Telegram, then is turned into text on your network and not stored.

### In Home Assistant's Assist

**Settings > Voice assistants**: add an assistant, or open one, and choose **BRAM Assist** as its conversation agent. Your other choices, such as how it hears and speaks, stay the same. Choose the old agent to go back.

- It answers only about that home, and not about monitors or other homes.
- **Anyone who can use that assistant can ask** who is home and what is locked.
- It uses the personality you set in BRAM.
- BRAM cannot control anything. If the assistant has **Prefer handling commands locally** on, Home Assistant itself still handles commands such as turning on a light.

### Problems

| Problem | Try |
|---|---|
| Choose a model first | **Settings > Model** |
| Still thinking | Wait for the last answer |
| Ollama request failed | Check that Ollama is running and reachable |
| It cannot see a device | Add it in BRAM's options in Home Assistant |

## Voice

Optional. Hold a button to talk to BRAM on its home page, and let it read its answers aloud. It uses Whisper to hear and Piper to speak, through the Wyoming protocol that Home Assistant also uses. Everything stays on your network.

### Choose where they run

| You have | Do this |
|---|---|
| Nothing yet, and want one stack | Use `compose.full.yaml` instead of `compose.yaml` |
| Nothing yet, and want a separate stack | Add a stack from `compose.voice.yaml` |
| Whisper or Piper already, with Wyoming | Use their addresses; add nothing |

In Portainer these are the **Compose path** of a **Repository** stack from `https://github.com/imCharlieB/Bram`.

#### Moving to the full stack in Portainer

Your data is in a volume named after the stack, such as `bram_bram-data`.

1. Under **Volumes**, note the name ending in `bram-data`. The part before `_bram-data` must be the new stack's name.
2. Delete the stack, but **not its volumes**. Check that the volume is still listed.
3. Add a stack with the same name and the path `compose.full.yaml`. Deploy.
4. Sign in with your existing login. If you see **Welcome to BRAM**, the old volume did not attach: do not create a login; check the stack's name.

A separate voice stack avoids all of this.

Their models are downloaded on first start, so allow a few minutes. Optional stack settings (environment variables):

| Setting | Meaning | Default |
|---|---|---|
| `BRAM_WHISPER_MODEL` | Bigger hears better but slower: `tiny-int8`, `base-int8`, `small-int8` | `base-int8` |
| `BRAM_WHISPER_LANGUAGE` | Language you speak | `en` |
| `BRAM_PIPER_VOICE` | Voice | `en_US-lessac-medium` |

### Set it up

1. On BRAM's page, go to **Settings > Voice** and press **Set up voice**. BRAM looks beside itself and on its own machine.
2. Choose a voice and press **Listen**. A cloud means it is downloaded the first time.
3. Press **Turn on voice**.
4. Use **Test speaking** and **Hold and talk to test hearing**.

If nothing is found, the page shows how to add them. If they run on another machine, open **Advanced**, enter their addresses, and press **Use these addresses**.

### Use it

On the home page, hold **Hold to talk** (or hold Space or Enter on it), speak, and let go. To hear answers, press **Speak answers**, the round switch in the dock along the bottom; it lights up when on, and this browser remembers it. Your browser asks for the microphone the first time.

- BRAM listens only while you hold the button, for up to 30 seconds.
- Sound is not stored. What you said is handled like typed text.
- A voice never approves anything.
- A close microphone works far better than one across a room with a TV on.

Home Assistant can use the same Whisper and Piper: add the **Wyoming Protocol** integration twice, with ports 10300 and 10200. A small Whisper model may hear worse than Home Assistant Cloud across a room, so compare before switching.

### Security

Wyoming has no login or encryption. Keep ports 10300 and 10200 on your own network and never forward them.

### Problems

| Problem | Try |
|---|---|
| No microphone button | Set up Hearing in Settings |
| Microphone was not allowed | Allow it in the browser for BRAM's page; use `https` |
| The speech server did not answer | Wait for the first download; check the address and port |
| Slow or wrong words | Try another `BRAM_WHISPER_MODEL`; move closer |

## Personality

Choose a mode on BRAM's home page under **Mood**, in **Settings > Personality**, or with **Mood** on BRAM's device page in Home Assistant, where automations can change it too. It applies everywhere BRAM talks: its page, Assist, and Telegram.

| Mode | Garage open for 40 minutes |
|---|---|
| Professional | "The garage door has been open for 40 minutes." |
| Friendly | "Just so you know, the garage door's been open for 40 minutes now." |
| Dry | "The garage door has been open for 40 minutes. Bold strategy." |
| Minimal | "Garage door open. 40 minutes." |
| Unhinged | "That damn garage door has been sitting wide open for 40 minutes, you absolute disaster." |
| Custom | However you describe it, in up to 500 characters |

These are examples; your model decides the words. **Try it** in Settings sends it one invented sentence.

- A mode changes wording only. It never changes facts, limits, permissions, or when BRAM speaks.
- Alerts use fixed wording in every mode.
- Unhinged swears and roasts you. It is told not to use slurs, threats, or sexual content about real people, and to leave others alone. How closely it listens depends on the model.
- Models sometimes add a detail that is not true. On BRAM's page, check the sensor readings under the answer.

## Blueprints

Blueprints are automations you add in Home Assistant, where you can see, change, and turn them off. BRAM's blueprints ask BRAM a question and send the answer to your phone. BRAM only reads; the automation only sends a message. They need BRAM's assistant (**BRAM Assist**) and a model on the BRAM Server.

### Use one

BRAM puts its blueprints in Home Assistant for you; there is nothing to import.

1. In Home Assistant, go to **Settings > Automations & scenes > Blueprints**.
2. Choose **BRAM scheduled check** or **BRAM house summary**.
3. Fill in the settings below and press **Save**.

Make as many automations from each as you like, such as one check for doors at night and another for the garage.

| Blueprint | Does |
|---|---|
| **BRAM scheduled check** | Every so many minutes, asks a yes-or-no question, such as "Is any door or window open?", and tells your phone only when the answer is yes |
| **BRAM house summary** | At a time you choose, asks how the home is doing and sends the answer |

If a blueprint is missing, restart Home Assistant once after updating BRAM.

### Settings

| Setting | Scheduled check | House summary |
|---|---|---|
| Question | The question; BRAM is asked to start its answer with yes or no | What to ask, with a short default |
| When | **Every**: 5 to 1440 minutes, counted from midnight, so 60 means on each hour | **At**: a time of day |
| BRAM's assistant | Choose **BRAM Assist** | Same |
| Phone | Your phone's notify action, such as `notify.mobile_app_my_phone` | Same |

The scheduled check sends only when the answer's first word is yes. An answer that does not start with yes or no is not sent, so try a new check once with **Run actions** from the automation's menu.

Answers come from the model, so word questions about what BRAM can see. These do not replace BRAM's own rules in [How BRAM watches your home](watching.md#how-bram-watches-your-home), which need no model.

### Updates

They are kept in your Home Assistant folder under `blueprints/automation/bram`. A BRAM update replaces a blueprint only if you have not changed it. If you edited one, yours stays, and the new version is not added; delete your copy and restart Home Assistant to get it. Automations made from a blueprint pick up its changes on their own.

Camera blueprints come with cameras; see the [plan](roadmap.md).
