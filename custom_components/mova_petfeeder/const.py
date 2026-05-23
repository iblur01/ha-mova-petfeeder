from homeassistant.const import Platform

DOMAIN = "mova_petfeeder"
SCAN_INTERVAL = 60

CONF_COUNTRY = "country"
COUNTRIES = ["eu", "cn", "us", "ru", "tw", "sg", "in"]

PLATFORMS = [Platform.BUTTON, Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

# MiOT property map (siid, piid)
PROP_ONLINE          = (2, 1)
PROP_STATUS          = (2, 2)
PROP_SCHEDULE_ON     = (3, 2)
PROP_SOUND_ON        = (3, 3)
PROP_PORTION_SIZE    = (3, 4)
PROP_MAX_FEEDINGS    = (3, 5)
PROP_SCHEDULE        = (3, 6)
PROP_FEEDINGS_TODAY  = (5, 1)

# MiOT action: manual feed
# params = {did, siid:3, aiid:1, in:[{piid:1, value:portions}]}
ACTION_FEED_SIID = 3
ACTION_FEED_AIID = 1
ACTION_FEED_PIID = 1

FROM_FIELD = "I13bd2b"
