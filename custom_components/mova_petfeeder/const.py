"""Constants for the Mova Pet Feeder integration (no Home Assistant import)."""

DOMAIN = "mova_petfeeder"

CONF_COUNTRY = "country"
CONF_PASSWORD_HASH = "password_hash"
COUNTRIES = ["eu", "cn", "us", "ru", "tw", "sg", "in"]

# Options
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DEFAULT_PORTIONS = "default_portions"
CONF_ENABLE_SCHEDULE_WRITE = "enable_schedule_write"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 600
DEFAULT_PORTIONS = 1

# Bounds (manual portions and schedule limits are assumptions, see README)
MAX_MANUAL_PORTIONS = 10
MIN_PORTION_SIZE = 1
MAX_PORTION_SIZE = 50
MAX_SCHEDULE_PORTIONS = 10
MAX_SCHEDULE_SLOTS = 10

# Polling / commands
FAILURE_TOLERANCE = 3
REFRESH_DELAY = 10
REQUEST_TIMEOUT = 15
TOKEN_MARGIN = 300

# MOVAhome app constants
SALT = "RAylYC%fmSKp7%Tq"
USER_AGENT = "Mova_Smarthome/1.5.59 (iPhone; iOS 16.0; Scale/3.00)"
APP_AUTH = "Basic ZHJlYW1lX2FwcHYxOkFQXmR2QHpAU1FZVnhOODg="
TENANT_ID = "000002"
# Dreame-Rlc: still to be checked before a HACS release.
RLC = "1c80b3787b2266776bcdc481f37d8fa42ba10a30af81a6df-1"
FROM_FIELD = "I13bd2b"

# MiOT property map (siid, piid)
PROP_ONLINE = (2, 1)
PROP_STATUS = (2, 2)
PROP_SCHEDULE_ON = (3, 2)
PROP_SOUND_ON = (3, 3)
PROP_PORTION_SIZE = (3, 4)
PROP_MAX_FEEDINGS = (3, 5)
PROP_SCHEDULE = (3, 6)
# Food remaining in the bowl, in grams. Verified against the app (6 g, 11 g).
# Note: (4, 2) holds an unrelated value; (5, 1) does not exist on this model.
PROP_FOOD_LEVEL = (4, 1)

# Keys exposed as entities, and keys read only for diagnostics (same request).
ENTITY_KEYS = ("3.2", "3.3", "3.4", "3.6", "4.1")
DIAG_KEYS = ("2.1", "2.2", "2.3", "3.1", "3.5", "4.2", "4.3", "4.4", "5.2")
ALL_KEYS = ENTITY_KEYS + DIAG_KEYS

# MiOT action: manual feed
# params = {did, siid:3, aiid:1, in:[{piid:1, value:portions}]}
ACTION_FEED_SIID = 3
ACTION_FEED_AIID = 1
ACTION_FEED_PIID = 1
