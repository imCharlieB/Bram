# BRAM Hard Rules

Status: **APPROVED 2026-11-24**, A4, A5, and A9 changed by the owner 2026-11-25. Changes need owner approval.

A rule is hard only if code enforces it and an automated test proves it. Prompt wording never counts as enforcement. Where [SPEC.md](SPEC.md) and this file disagree, this file wins. A failing rule test blocks the release.

**Terms**
- **Gate**: code in the Home Assistant integration that decides whether an action runs.
- **Server**: the BRAM Server process (`bram-core`).
- **Owner**: the person who administers this BRAM installation.
- **Tier 1**: low-risk, reversible comfort actions. **Tier 2**: alerts and messages. **Tier 3**: actions needing approval. **Blocked**: never run by BRAM.

## A. Control

| ID | Rule | Enforced by | Proven by |
|---|---|---|---|
| A1 | The model only requests actions. It never calls Home Assistant directly. | The model process has no HA credentials; the gate is the only path | No code path from model output to a service call except the gate |
| A2 | Denied by default. Only allowlisted entity + action + parameter combinations can run. New devices start blocked. | Gate allowlist | Every unlisted combination is refused |
| A3 | Unlock, open a door/garage/gate, disarm, and disable a camera or alarm are always Tier 3 or Blocked. The owner cannot lower them. | Built-in floor in the gate | Attempts to configure a lower tier fail |
| A4 | Approval covers one exact action on one device, by an authorized person, by a tap on their own signed-in phone. The owner may also require a PIN, per device; it is off by default. It expires quickly and works once. | Gate approval record | Altered, reused, expired, and wrong-person approvals fail |
| A5 | If a PIN is used, the model never sees it. PINs are stored as salted hashes, and wrong attempts lock out. | Approval handled outside the conversation | PIN absent from prompts, memory, and logs |
| A6 | Voice, face, location, or a conversational "yes" never approves Tier 3. | Gate accepts only approval records | Each alone is refused |
| A7 | No side doors. Scripts, scenes, automations, groups, and toggles get the highest tier of anything they can reach. If unknown, they are blocked. | Gate target resolver | Nested and templated targets are refused or raised |
| A8 | BRAM cannot call generic services, shell, MQTT publish, or restart, and cannot edit Home Assistant configuration. Sole exception: A9. | Not in the gate's vocabulary | Such requests are refused |
| A9 | BRAM may draft an automation, but installs it only after the owner sees the exact final content and approves it on their phone. It may contain only Tier 1 actions and notifications. Later edits need approval again. | Automation validator in the gate | Tier 3, templated-service, and changed-after-approval drafts fail |
| A10 | BRAM cannot change its own rules, tiers, allowlist, approvals, or code. | No such tool; settings are owner-only | Requests fail |
| A11 | BRAM never disables smoke, CO, gas, or leak alarms, and never erases its audit log. | Blocked list; append-only log interface | Requests fail |
| A12 | Rate limits, value bounds, and loop detection apply per device. | Gate | Excess, out-of-range, and looping requests stop |
| A13 | The owner's off switch works without the model or the server. | Switch in the integration | Works with both offline |
| A14 | BRAM does not unlock while nobody is confirmed home, even with approval, unless the owner enables that exact lock. | Gate | Away and unknown both refuse |
| A15 | BRAM cannot trigger an external automation to avoid approval. | Gate (see A7) | Attempt is refused |

## B. Truth

| ID | Rule | Enforced by | Proven by |
|---|---|---|---|
| B1 | Read live state before acting and confirm it after. Report success only on confirmation. | Gate result states | Device that ignores a command is reported as unconfirmed |
| B2 | Missing, stale, unknown, or unavailable never means safe, locked, closed, or empty. | World model has an explicit unknown | Every safety condition tested with unknown inputs |
| B3 | Told facts, observations, and guesses are stored separately with source and time. | Memory schema | A guess cannot be stored as a fact |
| B4 | BRAM says so when its model is offline or a check could not run. | Fixed-text responses | Model-off test |

## C. Safety alerts

| ID | Rule | Enforced by | Proven by |
|---|---|---|---|
| C1 | Code detects safety events and sends them with fixed text. No model is involved. | Safety engine | All alerts delivered with the model off |
| C2 | Critical alerts also run inside Home Assistant if the server is down. | Integration | Alerts delivered with the server off |
| C3 | No model output, memory, habit, quiet hour, cap, or "stop telling me" can cancel, delay, or downgrade a safety alert. Only the owner, in settings. | Separate delivery path | Each suppressor attempted |
| C4 | Safety alerts repeat and escalate until acknowledged, within configured limits. | Delivery engine | Unacknowledged alert escalates and then stops at its limit |
| C5 | BRAM never claims to have called emergency services and is not a substitute for certified alarms. | No such tool; disclosure in setup | Setup and text review |
| C6 | A model description may add detail after an alert. It cannot hold the alert back. | Alert sent before the model call | Slow and failing model tests |

## D. Untrusted content

| ID | Rule | Enforced by | Proven by |
|---|---|---|---|
| D1 | Only an authorized person's message can be a command. Text in images, notifications, device names, web pages, tool results, or memories is data. | Action requests carry the originating person and message; the gate requires one, except for allowlisted Tier 1 initiatives | Injection test set |
| D2 | Web search and external tools are off by default. Once untrusted content is read in a conversation, that conversation cannot request an action until a new message from an authorized person. | Conversation taint flag | Injection through search results fails |
| D3 | External tools cannot act on the home except through the gate. | Tool adapter permissions | Bypass attempts fail |
| D4 | A model can never be the safety mechanism. | All of the above | Full test set passes with a deliberately malicious fake model |

## E. People and privacy

| ID | Rule | Enforced by | Proven by |
|---|---|---|---|
| E1 | Nothing goes to a cloud service until the owner enables that provider. No silent cloud fallback. | Provider settings | Local model down produces no outside traffic |
| E2 | Camera images to a model are off by default, per camera, and cloud images are a separate switch. | Image broker | Disabled camera never leaves |
| E3 | Secrets, PINs, tokens, and biometric templates never go to any model. | Redaction before the adapter | Planted secrets never appear |
| E4 | Personal messages never play on shared speakers. Nothing crosses people or houses without consent. | Delivery policy; person and house on every record | Cross-person and cross-house reads fail |
| E5 | Outreach, face ID, and voice ID are opt-in per person. Guests and children are never enrolled by default. | Consent records | No consent means no contact or enrollment |
| E6 | Face and voice ID can personalize but never authorize. | See A6 | See A6 |
| E7 | People can see, correct, and delete their own memories. | Memory UI and API | Deleted memory is gone from search and index |
| E8 | Non-safety outreach obeys quiet hours, daily caps, and "stop telling me that." | Outreach policy | Each limit tested |
| E9 | No telemetry. Diagnostics are exported manually and redacted. | No telemetry code | Network and export tests |
| E10 | Memory is optional, per installation and per person. With it off, BRAM stores no conversations, facts, observations, or habits, and all control, outreach, and safety features that do not need them still work. Turning it off offers to delete what exists. Permissions, settings, and the audit log are not memory and remain. | Storage interface with a no-memory implementation; audit entries hold no conversation text | Whole test set, except memory-dependent features, passes with memory off and nothing personal is written |

## F. Failure, learning, and change

| ID | Rule | Enforced by | Proven by |
|---|---|---|---|
| F1 | If anything is uncertain, actions stop and safety alerts continue. | Gate and safety engine defaults | Fault tests |
| F2 | Action requests expire and are never replayed after a reconnect or restart. | Request IDs and expiry | Reconnect test |
| F3 | Every decision is logged: trigger, reason, approver, result. | Audit log | Every action has a complete record |
| F4 | Learned habits are proposals with evidence and expiry. They take effect after owner approval and never change permissions or safety alerts. | Proposal state machine | Unapproved habit has no effect |
| F5 | Safe out of the box: log-only, nothing controllable, no cloud, no cameras. | Defaults | Fresh-install test |
| F6 | Capabilities advance one stage at a time, with owner approval: log-only, messages, Tier 1, Tier 3. | Stage setting in the integration | Stages cannot be skipped |
| F7 | A model must pass BRAM's test set on this installation before it can request actions. A changed model, prompt, or quantization must pass again. | Model digest + prompt version check | Swapped model loses action rights |
| F8 | Updates never loosen permissions or enable features without owner approval. | Settings migration | Upgrade tests |
| F9 | Any hard-rule test failure blocks the release. | CI | CI configuration |

## G. Connections and training

| ID | Rule | Enforced by | Proven by |
|---|---|---|---|
| G1 | Integration and server authenticate each other, and their traffic is encrypted. | Pairing at setup | Unpaired peers are refused |
| G2 | BRAM never exposes the model server to the internet. Setup warns when it has no login, because other devices on the network may reach it. | Setup check | Check test |
| G3 | Safety features never depend on the model's machine. | See C1 and C2 | See C1 and C2 |
| G4 | The trainer teaches skill, not facts: no live states, routines, PINs, biometrics, or private conversations. | Dataset filter and owner review | Planted private data is rejected |
| G5 | Training starts only with owner approval of the dataset and the run. | Trainer API | Unapproved run refused |
| G6 | A trained model gets no extra trust, must beat the current model on unseen tests with zero safety regressions, and the old model stays available for rollback. | F7 plus promotion check | Worse or less safe model is rejected |

## Known limits

- BRAM cannot stop Home Assistant users, dashboards, other automations, or Assist sentence triggers from acting outside BRAM.
- A compromised Home Assistant can bypass the gate, because the gate runs inside it.
- On installations where the server shares the Home Assistant machine, BRAM cannot report that machine's failure. Setup must say so.
