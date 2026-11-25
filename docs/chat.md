# Chat

Type to BRAM on its home page. It uses the model and personality from **Settings**.

| It can | It cannot |
|---|---|
| Answer about the entities you shared, your monitors, and recent alerts | Control, unlock, or approve anything |
| Answer general questions from the model's own knowledge | Search the internet, see cameras, or set reminders |
| Keep up with the current conversation | Remember it later |

- **Check important answers.** Models make mistakes. Under an answer BRAM lists what the matching sensors actually say. *Unknown* means it cannot tell.
- **"Anyone home"** covers only people you shared. It is not proof the house is empty.
- **Nothing is saved to disk.** A chat is forgotten when you clear it, sign out, leave it for 30 minutes, or restart the server. The last 12 messages are kept in mind.
- **Stays on your network.** The model must be on your own network.
- While a leak or smoke sensor is triggered, BRAM drops its personality and answers plainly.
- It answers one question at a time, and shares your model with anything else using it.
- It is not an emergency service and cannot call one.

## In Telegram

Off by default, because answers about your home pass through Telegram, which is not end-to-end encrypted. On the **Messages** page, set up Telegram, check **Let me chat with BRAM here**, and **Save**. Only the linked account is answered.

## Problems

| Problem | Try |
|---|---|
| Choose a model first | **Settings > Model** |
| Still thinking | Wait for the last answer |
| Ollama request failed | Check that Ollama is running and reachable |
| It cannot see a device | Add it in BRAM's options in Home Assistant |
