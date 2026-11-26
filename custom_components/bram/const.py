"""Constants."""
DOMAIN = "bram"
CONF_CODE = "code"
CONF_FINGERPRINT = "fingerprint"
CONF_HOUSE_ID = "house_id"
CONF_ENTITIES = "entities"
CONF_PHONES = "phones"
CONF_SAFETY_PHONES = "safety_phones"
CONF_QUIET_FROM = "quiet_from"
CONF_QUIET_TO = "quiet_to"
CONF_ESCALATE = "escalate"
CONF_DIGEST = "digest"
CONF_ROOMS = "rooms"
CONF_PROBLEMS = "share_problems"
CONF_HISTORY = "share_history"
CONF_LEARN = "learn"
CONF_WEEKEND_FROM = "weekend_night_from"
CONF_WEEKEND_TO = "weekend_night_to"
CONF_SECURITY = "share_security"
CONF_PRINTERS = "printers"
CONF_PRINTERS_OFF = "printers_off"
CONF_PROBLEM_WATCH = "problem_watch"
CONF_SECURITY_WATCH = "security_watch"
# What "yes" and "no" mean for each kind BRAM understands.
MEANING = {
    "person": ("home", "away"),
    "lock": ("unlocked", "locked"),
    "leak": ("leak", "dry"),
    "smoke": ("smoke", "clear"),
    "co": ("carbon monoxide", "clear"),
    "gas": ("gas", "clear"),
    "heat": ("too hot", "normal"),
    "hazard": ("problem", "clear"),
    "opening": ("open", "closed"),
    "motion": ("detected", "clear"),
    "light": ("on", "off"),
    "switch": ("on", "off"),
    "fan": ("on", "off"),
    "media": ("on", "off or idle"),
    "satellite": ("in use", "idle"),
    "valve": ("open", "closed"),
}
# Kinds that say something other than yes or no.
READINGS = ("climate", "temperature", "humidity", "appliance", "other")
# These alert until someone answers.
SAFETY = ("leak", "smoke", "co", "gas", "heat", "hazard")
# How BRAM's options group what it may see.
GROUPS = {
    "people": ("person",), "doors": ("lock", "opening"), "safety": SAFETY,
    "motion": ("motion",), "lights": ("light",), "switches": ("switch", "fan"),
    "media": ("media",), "voice": ("satellite",),
    "climate": ("climate", "temperature", "humidity"), "appliances": ("appliance", "valve"),
    "other": ("other",),
}
MOODS = {
    "professional": "Professional", "friendly": "Friendly", "dry": "Dry", "minimal": "Minimal",
    "unhinged": "Unhinged", "custom": "Custom",
}
ICON = {
    "person": "mdi:account-eye", "lock": "mdi:lock", "leak": "mdi:water-alert",
    "smoke": "mdi:smoke-detector", "co": "mdi:molecule-co", "gas": "mdi:gas-cylinder",
    "heat": "mdi:fire", "hazard": "mdi:alert", "other": "mdi:eye-outline",
    "opening": "mdi:door", "motion": "mdi:motion-sensor",
    "light": "mdi:lightbulb", "switch": "mdi:toggle-switch", "fan": "mdi:fan",
    "media": "mdi:speaker", "satellite": "mdi:account-voice", "climate": "mdi:thermostat",
    "temperature": "mdi:thermometer", "humidity": "mdi:water-percent",
    "appliance": "mdi:water-boiler", "valve": "mdi:valve",
}
DEFAULT_NIGHT_FROM, DEFAULT_NIGHT_TO = "22:00:00", "06:00:00"
DEFAULT_OPEN_MINUTES = 10
DEFAULT_DIGEST = "08:00:00"
DEFAULT_PORT = 8765
