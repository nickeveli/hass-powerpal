"""Constants for powerpal."""
# Base component constants
NAME = "Powerpal"
DOMAIN = "powerpal"
VERSION = "0.4.0"
ATTRIBUTION = "Data provided by https://readings.powerpal.net"
ISSUE_URL = "https://github.com/nickeveli/hass-powerpal/issues"

# Icons
ICON = "mdi:transmission-tower"

# Platforms
PLATFORMS = ["sensor"]

# Configuration and options
CONF_AUTH_KEY = "auth_key"
CONF_DEVICE_ID = "device_id"

# Services
SERVICE_BACKFILL = "backfill_history"
