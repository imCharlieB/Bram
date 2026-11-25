# Chat

Type to BRAM on its home page. It uses the model and personality from **Settings**.

| It can | It cannot |
|---|---|
| Answer about the entities you shared, your monitors, and recent alerts | Control, unlock, or approve anything |
| Answer general questions from the model's own knowledge | Search the internet, see cameras, or set reminders |
| Keep up with the current conversation | Remember it later |

- BRAM [finds problems](problems.md) by itself; chat is for asking about them.
- **It can look things up if you let it.** In **BRAM > Configure > What BRAM may look into**:

| Turn on | Ask | It reads |
|---|---|---|
| History | "When was the back door last opened?" "How often did the garage open this week?" | 10 days of one to three devices named in the question, only devices BRAM can see |
| Problems | "Any errors in Home Assistant?" "Any low batteries?" | Grouped errors and warnings, failed integrations, open repairs, low batteries, updates |
| [BRAM's own history](history.md) | "How long did the AC run each day?" | Heating and cooling runs, and thermostats against room sensors, 7 days |
| Security check | "Is my home secure?" "Is anything exposed?" | See [Security check](security-check.md) |

  Lengths of time are worked out by code and shown under the answer, because models are bad at arithmetic. Use the device's name in a history question. Causes it suggests for a problem are guesses, and it fixes nothing.

- **Check important answers.** Models make mistakes. Under an answer BRAM lists what the matching sensors actually say. *Unknown* means it cannot tell.
- **"Anyone home"** covers only people you shared. It is not proof the house is empty.
- **Nothing is saved to disk.** A chat is forgotten when you clear it, sign out, leave it for 30 minutes, or restart the server. The last 12 messages are kept in mind.
- **Stays on your network.** The model must be on your own network.
- It answers one question at a time, and shares your model with anything else using it.
- It is not an emergency service and cannot call one.

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
