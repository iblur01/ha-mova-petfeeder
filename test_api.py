#!/usr/bin/env python3
"""Local integration test — no HA required."""
import sys, types, json, logging

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

# Stub HA modules so api.py can import
for mod in ["homeassistant", "homeassistant.const", "homeassistant.components"]:
    sys.modules[mod] = types.ModuleType(mod)

# Stub .const relative import
PROPS = dict(
    PROP_ONLINE=(2,1), PROP_STATUS=(2,2), PROP_SCHEDULE_ON=(3,2),
    PROP_SOUND_ON=(3,3), PROP_PORTION_SIZE=(3,4), PROP_MAX_FEEDINGS=(3,5),
    PROP_SCHEDULE=(3,6), PROP_FEEDINGS_TODAY=(5,1),
    ACTION_FEED_SIID=3, ACTION_FEED_AIID=1, ACTION_FEED_PIID=1,
    FROM_FIELD="I13bd2b", DOMAIN="mova_petfeeder",
)
const_mod = types.ModuleType("mova_petfeeder.const")
const_mod.__dict__.update(PROPS)
pkg = types.ModuleType("mova_petfeeder")
pkg.__path__ = ["custom_components/mova_petfeeder"]
sys.modules["mova_petfeeder"] = pkg
sys.modules["mova_petfeeder.const"] = const_mod

# Now import api using importlib
import importlib.util
spec = importlib.util.spec_from_file_location(
    "mova_petfeeder.api",
    "custom_components/mova_petfeeder/api.py",
    submodule_search_locations=[],
)
api_mod = importlib.util.module_from_spec(spec)
api_mod.__package__ = "mova_petfeeder"
sys.modules["mova_petfeeder.api"] = api_mod
spec.loader.exec_module(api_mod)

MovaCloudAPI = api_mod.MovaCloudAPI
MovaFeeder   = api_mod.MovaFeeder

with open("/Users/theo/dev/home/dreame-vacuum/.mova_credentials.json") as f:
    c = json.load(f)

api = MovaCloudAPI(c["email"], c["password"], c["country"])
print("Logging in...")
assert api.login(), "Login failed"
print(f"OK  uid={api.uid}")

devices = api.get_feeders()
print(f"Found {len(devices)} feeder(s)\n")

for d in devices:
    feeder = MovaFeeder(api, d)
    print(f"  {feeder.name} ({feeder.model})  did={feeder.did}")
    feeder.update()
    print(f"  available     : {feeder.available}")
    print(f"  online        : {feeder.online}")
    print(f"  schedule_on   : {feeder.schedule_enabled}")
    print(f"  sound_on      : {feeder.sound_enabled}")
    print(f"  portion_size  : {feeder.portion_size}")
    print(f"  feedings_today: {feeder.feedings_today}")
    print(f"  schedule_hex  : {feeder.schedule_hex}")
