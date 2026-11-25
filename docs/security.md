# Security

The rules BRAM must follow are in [Hard rules](../HARD_RULES.md), with what enforces each and how it is tested. This page explains the protections that exist today and their limits. BRAM has not had an outside security review.

## What BRAM can do

It can read the devices you chose, send messages, and talk. **It cannot control anything.** The integration's only service call is sending a notification to phones you chose.

## Protections

| Threat | Protection |
|---|---|
| Someone claims a new server | Setup closes after 15 minutes and works once. Until then, whoever opens the page first can claim it |
| Password guessing | 5 tries per address and 20 in all, then 15 minutes locked. Passwords are salted and hashed with scrypt |
| An unattended browser | Sensitive changes ask for the password again; sessions end after 30 idle minutes or 12 hours |
| A malicious website | Requests from other sites are refused; only the page's own scripts run |
| A stolen session cookie | Hidden from scripts and sent only over encryption; changing the password ends other sessions |
| A fake server or house | Certificate pinning and a secret token in each direction |
| A hijacked server | Can send the integration words and display values, nothing else |
| A tricked model | It has no tools, and device names and other text are marked as data |
| Data leaving home | Models, speech, and monitors must be on the local network. Telegram is the exception and is off by default |
| A stranger messaging the bot | Only the linked Telegram account is answered |
| Someone on the network reading ntfy | Topics are random and everything else is refused, but traffic is not encrypted |

## Limits

- Whoever controls the server's machine, its volume, or its backups controls BRAM.
- A compromised Home Assistant controls everything in it, with or without BRAM.
- The page's self-made certificate means a browser cannot tell it from an impostor on your network.
- Someone on your network can trigger the sign-in lockout. Open sessions keep working.
- Whisper, Piper, ntfy, and Ollama have no encryption or login here. Keep their ports on your own network.
- Anyone who can use a voice assistant set to BRAM can ask about that home.
- There is no second factor yet. One is required before BRAM can control anything.

## Reporting a problem

Please use [GitHub's private security report](https://github.com/imCharlieB/Bram/security/advisories/new) if it is available, rather than a public issue.
