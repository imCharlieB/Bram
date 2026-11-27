# Blueprints

Blueprints are automations you add in Home Assistant, where you can see, change, and turn them off. BRAM's blueprints ask BRAM a question and send the answer to your phone. BRAM only reads; the automation only sends a message. They need BRAM's assistant (**BRAM Assist**) and a model on the BRAM Server.

## Use one

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

## Settings

| Setting | Scheduled check | House summary |
|---|---|---|
| Question | The question; BRAM is asked to start its answer with yes or no | What to ask, with a short default |
| When | **Every**: 5 to 1440 minutes, counted from midnight, so 60 means on each hour | **At**: a time of day |
| BRAM's assistant | Choose **BRAM Assist** | Same |
| Phone | Your phone's notify action, such as `notify.mobile_app_my_phone` | Same |

The scheduled check sends only when the answer's first word is yes. An answer that does not start with yes or no is not sent, so try a new check once with **Run actions** from the automation's menu.

Answers come from the model, so word questions about what BRAM can see. These do not replace BRAM's own rules in [How BRAM watches your home](watching.md), which need no model.

## Updates

They are kept in your Home Assistant folder under `blueprints/automation/bram`. A BRAM update replaces a blueprint only if you have not changed it. If you edited one, yours stays, and the new version is not added; delete your copy and restart Home Assistant to get it. Automations made from a blueprint pick up its changes on their own.

Camera blueprints come with cameras; see the [plan](roadmap.md).
