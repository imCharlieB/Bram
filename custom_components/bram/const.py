"""Constants."""
DOMAIN = "bram"
CONF_CODE = "code"
CONF_FINGERPRINT = "fingerprint"
CONF_HOUSE_ID = "house_id"
CONF_ENTITIES = "entities"
CONF_PHONES = "phones"
CONF_QUIET_FROM = "quiet_from"
CONF_QUIET_TO = "quiet_to"
CONF_ESCALATE = "escalate"
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
ICON = {
    "person": "mdi:account-eye", "lock": "mdi:lock", "leak": "mdi:water-alert",
    "smoke": "mdi:smoke-detector", "opening": "mdi:door", "motion": "mdi:motion-sensor",
    "light": "mdi:lightbulb",
}
DEFAULT_PORT = 8765
