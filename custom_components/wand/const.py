"""Constants for the Wand integration."""

DOMAIN = "wand"

STORAGE_KEY = "wand.config"
STORAGE_VERSION = 1

PANEL_URL_PATH = "wand"
PANEL_TITLE = "Wand"
PANEL_ICON = "mdi:magic-staff"
STATIC_URL = "/wand_static"

FLOORPLAN_DIR = "wand"
FLOORPLAN_MAX_BYTES = 10 * 1024 * 1024
FLOORPLAN_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}

# Event the watch app fired before this integration existed; still honoured.
EVENT_LEGACY_SPELL = "wand_spell"
# Event fired after every successful cast, for user automations.
EVENT_CAST = "wand_cast"

SUPPORTED_DOMAINS = (
    "light",
    "switch",
    "fan",
    "media_player",
    "cover",
    "climate",
)
