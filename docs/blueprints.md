# Blueprints

Blueprints are automations you add in Home Assistant, where you can see, change, and turn them off. BRAM's blueprints ask BRAM a question and send the answer to your phone. BRAM only reads; the automation only sends a message. They need BRAM's assistant (**BRAM Assist**) and a model on the BRAM Server.

## Add one

Press the button, or in Home Assistant go to **Settings > Automations & scenes > Blueprints > Import blueprint** and paste the address. Then **Create automation** from it.

| Blueprint | Does | Address |
|---|---|---|
| **BRAM scheduled check** | Every so many minutes, asks a yes-or-no question, such as "Is any door or window open?", and tells your phone only when the answer is yes | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FimCharlieB%2FBram%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fbram%2Fscheduled_check.yaml) `https://github.com/imCharlieB/Bram/blob/main/blueprints/automation/bram/scheduled_check.yaml` |
| **BRAM house summary** | At a time you choose, asks how the home is doing and sends the answer | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FimCharlieB%2FBram%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fbram%2Fhouse_summary.yaml) `https://github.com/imCharlieB/Bram/blob/main/blueprints/automation/bram/house_summary.yaml` |

## Settings

| Setting | Scheduled check | House summary |
|---|---|---|
| Question | The question; BRAM is asked to start its answer with yes or no | What to ask, with a short default |
| When | **Every**: 5 to 1440 minutes, counted from midnight, so 60 means on each hour | **At**: a time of day |
| BRAM's assistant | Choose **BRAM Assist** | Same |
| Phone | Your phone's notify action, such as `notify.mobile_app_my_phone` | Same |

The scheduled check sends only when the answer's first word is yes. An answer that does not start with yes or no is not sent, so check one by running the automation once from its menu.

Answers come from the model, so word questions about what BRAM can see. These do not replace BRAM's own rules in [How BRAM watches your home](watching.md), which need no model.

Camera blueprints come with cameras; see the [plan](roadmap.md).
