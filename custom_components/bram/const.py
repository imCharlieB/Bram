"""Constants."""
DOMAIN = "bram"
CONF_CODE = "code"
CONF_FINGERPRINT = "fingerprint"
CONF_HOUSE_ID = "house_id"
CONF_ENTITIES = "entities"
# What "yes" and "no" mean for each kind BRAM understands.
MEANING = {
    "person": ("home", "away"),
    "lock": ("unlocked", "locked"),
    "leak": ("leak", "dry"),
    "smoke": ("smoke", "clear"),
    "opening": ("open", "closed"),
    "motion": ("detected", "clear"),
    "light": ("on", "off"),
}
DEFAULT_PORT = 8765
