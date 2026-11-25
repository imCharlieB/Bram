# Monitors

Monitors watch things outside Home Assistant, on your own network, and message you through Telegram or ntfy. Add them on BRAM's **Messages** page.

| Type | Address | Up when | Down when |
|---|---|---|---|
| Ollama | `http://HOST:11434` | It reports its version | Any error, or no answer |
| Frigate | `HOST:8971` or `HOST:5000` | It answers, or asks for a login | Server errors, or no answer |
| Computer or device | `HOST:PORT` | It accepts or refuses a connection | No answer |

- Checked when added, then every minute.
- You are told after three failures in a row, and again when it is back.
- The list shows the type and why it is not answering.
- Messages obey that channel's quiet hours and limit of 10 a day, and have **OK**, **Snooze 4 hours**, and **Stop these**.
- Only addresses on your own network are accepted. Nothing about your home is sent.
- Frigate's self-made certificate is accepted, because nothing private is sent to it.
- Up means it answered, not that everything in it works.

BRAM cannot report the failure of the machine it runs on. If Home Assistant runs elsewhere, it tells you that the BRAM Server is lost.

| Reason shown | Usually means |
|---|---|
| its certificate is not trusted | Wrong type; add Frigate as Frigate |
| could not connect | Off, or a wrong address or port |
| no reply in time | Blocked by a firewall, or asleep |
| it replied with error ... | Running, but not well |
