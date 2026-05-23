import hashlib
import json
import logging
import random
import requests
import string
from typing import Any

from .const import (
    ACTION_FEED_AIID,
    ACTION_FEED_PIID,
    ACTION_FEED_SIID,
    FROM_FIELD,
    PROP_FEEDINGS_TODAY,
    PROP_ONLINE,
    PROP_PORTION_SIZE,
    PROP_SCHEDULE,
    PROP_SCHEDULE_ON,
    PROP_SOUND_ON,
    PROP_STATUS,
)

_LOGGER = logging.getLogger(__name__)

_SALT = "RAylYC%fmSKp7%Tq"
_USER_AGENT = "Mova_Smarthome/1.5.59 (iPhone; iOS 16.0; Scale/3.00)"
_APP_AUTH = "Basic ZHJlYW1lX2FwcHYxOkFQXmR2QHpAU1FZVnhOODg="
_TENANT_ID = "000002"
_RLC = "1c80b3787b2266776bcdc481f37d8fa42ba10a30af81a6df-1"

_POLL_PROPS = [
    PROP_ONLINE,
    PROP_STATUS,
    PROP_SCHEDULE_ON,
    PROP_SOUND_ON,
    PROP_PORTION_SIZE,
    PROP_SCHEDULE,
    PROP_FEEDINGS_TODAY,
]


def _base_url(country: str) -> str:
    prefix = "" if country == "cn" else f"{country}."
    return f"https://{prefix}iot.mova-tech.com:13267"


def _cmd_url(base: str, bind_domain: str) -> str:
    prefix = bind_domain.split(".")[0]
    return f"{base}/dreame-iot-com-{prefix}/device/sendCommand"


class MovaCloudAPI:
    def __init__(self, username: str, password: str, country: str) -> None:
        self._username = username
        self._password = password
        self._country = country
        self._base = _base_url(country)
        self._token: str | None = None
        self._uid: str | None = None

    def _headers_auth(self) -> dict:
        return {
            "User-Agent": _USER_AGENT,
            "Authorization": _APP_AUTH,
            "Tenant-Id": _TENANT_ID,
            "Dreame-Rlc": _RLC,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _headers_api(self) -> dict:
        return {
            "User-Agent": _USER_AGENT,
            "Dreame-Auth": self._token,
            "Dreame-Rlc": _RLC,
            "Content-Type": "application/json",
        }

    def login(self) -> bool:
        pwd_hash = hashlib.md5(
            (self._password + _SALT).encode("utf-8")
        ).hexdigest()
        body = (
            f"platform=IOS&scope=all&grant_type=password"
            f"&username={self._username}&password={pwd_hash}&type=account"
        )
        try:
            resp = requests.post(
                f"{self._base}/dreame-auth/oauth/token",
                data=body,
                headers=self._headers_auth(),
                timeout=15,
            ).json()
            if "access_token" not in resp:
                _LOGGER.error("Login failed: %s", resp)
                return False
            self._token = resp["access_token"]
            self._uid = resp["uid"]
            return True
        except Exception as exc:
            _LOGGER.error("Login exception: %s", exc)
            return False

    def get_feeders(self) -> list[dict]:
        try:
            resp = requests.post(
                f"{self._base}/dreame-user-iot/iotuserbind/device/listV2",
                headers=self._headers_api(),
                timeout=15,
            ).json()
            if resp.get("code") != 0:
                return []
            records = resp.get("data", {}).get("page", {}).get("records", [])
            return [d for d in records if "feeder" in d.get("model", "")]
        except Exception as exc:
            _LOGGER.error("get_feeders exception: %s", exc)
            return []

    def _send(self, did: str, bind_domain: str, method: str, params: Any, cmd_id: int) -> dict | None:
        url = _cmd_url(self._base, bind_domain)
        _LOGGER.debug("sendCommand url=%s method=%s", url, method)
        payload = {
            "did": did,
            "id": cmd_id,
            "data": {
                "did": did,
                "id": cmd_id,
                "method": method,
                "params": params,
                "from": FROM_FIELD,
            },
        }
        try:
            resp = requests.post(
                url,
                headers=self._headers_api(),
                data=json.dumps(payload, separators=(",", ":")),
                timeout=20,
            ).json()
            if resp.get("code") == 0 and resp.get("data"):
                return resp["data"]
            _LOGGER.warning("sendCommand failed code=%s msg=%s resp=%s", resp.get("code"), resp.get("msg"), resp)
        except Exception as exc:
            _LOGGER.error("sendCommand exception %s: %s", type(exc).__name__, exc)
        return None

    def get_properties_cached(self, did: str, props: list[tuple[int, int]]) -> dict[tuple, Any]:
        """Read properties from cloud cache — works even when device is offline."""
        keys = ",".join(f"{s}.{p}" for s, p in props)
        _LOGGER.debug("get_properties_cached did=%s keys=%s", did, keys)
        try:
            resp = requests.post(
                f"{self._base}/dreame-user-iot/iotstatus/props",
                headers=self._headers_api(),
                data=json.dumps({"did": did, "keys": keys}, separators=(",", ":")),
                timeout=15,
            ).json()
            _LOGGER.debug("get_properties_cached response: %s", resp)
            if resp.get("code") != 0:
                _LOGGER.warning("get_properties_cached failed code=%s msg=%s", resp.get("code"), resp.get("msg"))
                return {}
            result = {}
            for entry in resp.get("data") or []:
                try:
                    s, p = entry["key"].split(".")
                    result[(int(s), int(p))] = entry["value"]
                except (KeyError, ValueError, AttributeError):
                    pass
            return result
        except Exception as exc:
            _LOGGER.error("get_properties_cached exception %s: %s", type(exc).__name__, exc)
            return {}

    def set_property(self, did: str, bind_domain: str, siid: int, piid: int, value: Any, cmd_id: int = 1) -> bool:
        data = self._send(did, bind_domain, "set_properties",
                          [{"siid": siid, "piid": piid, "value": value}], cmd_id)
        if data and "result" in data:
            return data["result"][0].get("code", -1) == 0
        return False

    def action_feed(self, did: str, bind_domain: str, portions: int = 1, cmd_id: int = 1) -> bool:
        params = {
            "did": did,
            "siid": ACTION_FEED_SIID,
            "aiid": ACTION_FEED_AIID,
            "in": [{"piid": ACTION_FEED_PIID, "value": portions}],
        }
        data = self._send(did, bind_domain, "action", params, cmd_id)
        if data and "result" in data:
            return data["result"].get("code", -1) == 0
        return False

    @property
    def uid(self) -> str | None:
        return self._uid


class MovaFeeder:
    def __init__(self, api: MovaCloudAPI, device_info: dict) -> None:
        self._api = api
        self.did: str = device_info["did"]
        self.name: str = device_info.get("customName") or device_info.get("nickName") or device_info.get("model", "Mova Feeder")
        self.model: str = device_info.get("model", "")
        self.mac: str = device_info.get("mac", "")
        self.bind_domain: str = device_info.get("bindDomain", "")
        self._cmd_id = 1

        self.online: bool = False
        self.schedule_enabled: bool = True
        self.sound_enabled: bool = True
        self.portion_size: int = 1
        self.feedings_today: int = 0
        self.schedule_hex: str = ""
        self.available: bool = False

    def _next_id(self) -> int:
        self._cmd_id += 1
        return self._cmd_id

    def update(self) -> None:
        props = self._api.get_properties_cached(self.did, _POLL_PROPS)
        if not props:
            self.available = False
            return
        self.available = True
        self.online = int(props.get(PROP_ONLINE, 0)) != 0
        self.schedule_enabled = int(props.get(PROP_SCHEDULE_ON, 1)) != 0
        self.sound_enabled = int(props.get(PROP_SOUND_ON, 1)) != 0
        self.portion_size = int(props.get(PROP_PORTION_SIZE, 1))
        self.feedings_today = int(props.get(PROP_FEEDINGS_TODAY, 0))
        self.schedule_hex = str(props.get(PROP_SCHEDULE, ""))

    def feed(self, portions: int | None = None) -> bool:
        return self._api.action_feed(
            self.did, self.bind_domain,
            portions if portions is not None else self.portion_size,
            self._next_id(),
        )

    def set_schedule_enabled(self, enabled: bool) -> bool:
        return self._api.set_property(self.did, self.bind_domain, *PROP_SCHEDULE_ON, enabled, self._next_id())

    def set_sound_enabled(self, enabled: bool) -> bool:
        return self._api.set_property(self.did, self.bind_domain, *PROP_SOUND_ON, enabled, self._next_id())

    def set_portion_size(self, size: int) -> bool:
        return self._api.set_property(self.did, self.bind_domain, *PROP_PORTION_SIZE, size, self._next_id())

    @property
    def unique_id_prefix(self) -> str:
        return self.mac.replace(":", "").lower()
