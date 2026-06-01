#!/usr/bin/env python3
"""Reproduce the FP10 polling test protocol for the Mova pet feeder.

Compares the cloud-cache read path (iotstatus/props) the integration uses
against a direct sendCommand get_properties path, and checks whether the
direct path has the same constant-id response correlation bug as the FP10.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import types
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
CREDS = REPO.parent / "dreame-vacuum" / ".mova_credentials.json"

# Stub homeassistant so const.py/api.py import without a full HA install.
for _haname in ("homeassistant", "homeassistant.const"):
    _ha = types.ModuleType(_haname)
    sys.modules.setdefault(_haname, _ha)
class _PlatformMeta(type):
    def __getattr__(cls, name):  # any Platform.X resolves to its name
        return name


sys.modules["homeassistant.const"].Platform = _PlatformMeta("Platform", (), {})

# Load api.py without running the package __init__ (it imports homeassistant).
PKG_DIR = REPO / "custom_components" / "mova_petfeeder"
pkg = types.ModuleType("mova_petfeeder")
pkg.__path__ = [str(PKG_DIR)]
sys.modules["mova_petfeeder"] = pkg
for _name in ("const", "api"):
    _spec = importlib.util.spec_from_file_location(f"mova_petfeeder.{_name}", PKG_DIR / f"{_name}.py")
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[f"mova_petfeeder.{_name}"] = _m
    _spec.loader.exec_module(_m)
mod = sys.modules["mova_petfeeder.api"]

POLL_PROPS = [(2, 1), (2, 2), (3, 2), (3, 3), (3, 4), (3, 6), (5, 1), (4, 2)]
NAMES = {
    (2, 1): "online", (2, 2): "status", (3, 2): "schedule_on", (3, 3): "sound_on",
    (3, 4): "portion_size", (3, 6): "schedule", (5, 1): "feedings_today", (4, 2): "food_level",
}
N = len(POLL_PROPS)

creds = json.loads(CREDS.read_text())
api = mod.MovaCloudAPI(
    os.environ.get("MOVA_USER", creds["email"]),
    os.environ.get("MOVA_PASS", creds["password"]),
    creds.get("country", "eu"),
)
if not api.login():
    print("login FAILED")
    sys.exit(1)
print("login OK")

feeders = api.get_feeders()
if not feeders:
    print("no feeder found")
    sys.exit(1)
dev = feeders[0]
did = dev["did"]
bind = dev.get("bindDomain", "")
print(f"feeder did={did} model={dev.get('model')} bind={bind}\n")


def direct_batch(unique_id: bool):
    """sendCommand get_properties for all props in one call."""
    url = mod._cmd_url(api._base, bind)
    cmd_id = api._next_id_counter() if unique_id else 1
    params = [{"did": did, "siid": s, "piid": p} for s, p in POLL_PROPS]
    payload = {"did": did, "id": cmd_id,
               "data": {"did": did, "id": cmd_id, "method": "get_properties",
                        "params": params, "from": mod.FROM_FIELD}}
    try:
        resp = requests.post(url, headers=api._headers_api(),
                             data=json.dumps(payload, separators=(",", ":")), timeout=15).json()
    except Exception as e:
        return {}, f"ERR {e}"
    got = {}
    data = resp.get("data") or {}
    res = data.get("result")
    wanted = set(POLL_PROPS)
    if isinstance(res, list):
        for it in res:
            key = (it.get("siid"), it.get("piid"))
            if it.get("code", -1) == 0 and key in wanted:
                got[key] = it.get("value")
    return got, resp.get("code")


# unique id counter on the api instance
_uid = [1]
api._next_id_counter = lambda: (_uid.__setitem__(0, _uid[0] + 1) or _uid[0])

print("== A. CACHE PATH (iotstatus/props, what the integration uses) ==")
for r in range(6):
    t = time.time()
    got = api.get_properties_cached(did, POLL_PROPS)
    dt = time.time() - t
    miss = [NAMES[k] for k in POLL_PROPS if k not in got]
    print(f"  run {r+1}: {len(got)}/{N}  {dt:.2f}s  missing={miss}")
    if r == 0:
        print("   sample:", {NAMES[k]: got.get(k) for k in POLL_PROPS if k in got})

print("\n== B. DIRECT PATH, UNIQUE id ==")
for r in range(6):
    t = time.time()
    got, code = direct_batch(unique_id=True)
    dt = time.time() - t
    miss = [NAMES[k] for k in POLL_PROPS if k not in got]
    print(f"  run {r+1}: {len(got)}/{N}  {dt:.2f}s  code={code}  missing={miss}")

print("\n== C. DIRECT PATH, CONSTANT id=1 (mismatch check, per-prop) ==")
total = match = mismatch = empty = 0
for s, p in POLL_PROPS:
    for _ in range(6):
        url = mod._cmd_url(api._base, bind)
        payload = {"did": did, "id": 1,
                   "data": {"did": did, "id": 1, "method": "get_properties",
                            "params": [{"did": did, "siid": s, "piid": p}], "from": mod.FROM_FIELD}}
        try:
            resp = requests.post(url, headers=api._headers_api(),
                                 data=json.dumps(payload, separators=(",", ":")), timeout=15).json()
        except Exception:
            empty += 1
            total += 1
            continue
        total += 1
        res = (resp.get("data") or {}).get("result")
        if not isinstance(res, list) or not res:
            empty += 1
            continue
        it = res[0]
        if (it.get("siid"), it.get("piid")) != (s, p):
            mismatch += 1
        elif it.get("code", -1) == 0:
            match += 1
print(f"  total={total} match={match} mismatch={mismatch} empty/err={empty}")
