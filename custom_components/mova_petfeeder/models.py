"""Data models and pure helpers for the Mova cloud API (no Home Assistant import)."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from .const import (
    ACTION_FEED_AIID,
    ACTION_FEED_PIID,
    ACTION_FEED_SIID,
    PROP_FOOD_LEVEL,
    PROP_PORTION_SIZE,
    PROP_SCHEDULE,
    PROP_SCHEDULE_ON,
    PROP_SOUND_ON,
    SALT,
    TOKEN_MARGIN,
)

_LOGGER = logging.getLogger(__name__)

DAYS_ALL = 0xFF
_SLOT_LEN = 10  # 5 bytes per slot, in hex characters


class MovaError(Exception):
    """Base error for the Mova cloud."""


class MovaAuthError(MovaError):
    """Credentials refused or session cannot be renewed."""


class MovaConnectionError(MovaError):
    """Network error, timeout, HTTP 5xx or invalid JSON."""


class MovaApiError(MovaError):
    """The cloud answered with an application error code."""

    def __init__(self, code: Any, detail: str = "") -> None:
        super().__init__(detail or f"code={code}")
        self.code = code


class MovaCommandError(MovaError):
    """The device rejected a command."""


def config_error_key(err: Exception | None, devices: Any = None) -> str | None:
    """Map a login/list outcome to a config flow error key (None = success)."""
    if err is None:
        return None if devices else "no_devices"
    if isinstance(err, MovaAuthError):
        return "invalid_auth"
    if isinstance(err, MovaConnectionError):
        return "cannot_connect"
    if isinstance(err, MovaApiError):
        return "api_error"
    return "unknown"


@dataclass(frozen=True, slots=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: float  # time.monotonic() based
    uid: str | None


@dataclass(frozen=True, slots=True)
class MovaDevice:
    did: str
    model: str
    name: str
    mac: str | None
    firmware: str | None
    online: bool
    bind_domain: str


@dataclass(frozen=True, slots=True)
class PropValue:
    value: str | None  # None: key does not exist on the device
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class ScheduleSlot:
    hour: int
    minute: int
    portions: int
    enabled: bool  # byte 5 (assumption: 01 = active)
    days_raw: int = DAYS_ALL  # byte 1, not decoded, kept as is

    @property
    def time(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"


@dataclass(frozen=True, slots=True)
class FeederState:
    device: MovaDevice
    food_level_g: int | None
    schedule_enabled: bool | None
    sound_enabled: bool | None
    portion_size: int | None
    schedule: tuple[ScheduleSlot, ...] | None  # None if not decodable
    raw: dict[str, PropValue]


def key(prop: tuple[int, int]) -> str:
    """Return the "siid.piid" key of a property."""
    return f"{prop[0]}.{prop[1]}"


def hash_password(password: str) -> str:
    """Return the password hash expected by the login endpoint."""
    return hashlib.md5((password + SALT).encode("utf-8")).hexdigest()  # noqa: S324


def parse_token(payload: Any, now: float | None = None) -> TokenSet:
    """Parse an oauth/token response."""
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise MovaAuthError("no access_token in login response")
    now = time.monotonic() if now is None else now
    try:
        expires_in = int(payload.get("expires_in") or 7200)
    except (TypeError, ValueError):
        expires_in = 7200
    return TokenSet(
        access_token=str(payload["access_token"]),
        refresh_token=payload.get("refresh_token") or None,
        expires_at=now + expires_in - TOKEN_MARGIN,
        uid=payload.get("uid"),
    )


def parse_devices(payload: dict[str, Any]) -> list[MovaDevice]:
    """Parse a listV2 response, keeping feeders only."""
    data = payload.get("data") or {}
    records = (data.get("page") or {}).get("records") or []
    devices = []
    for rec in records:
        model = str(rec.get("model") or "")
        if "feeder" not in model or not rec.get("did"):
            continue
        devices.append(
            MovaDevice(
                did=str(rec["did"]),
                model=model,
                name=rec.get("customName") or model,
                mac=rec.get("mac") or None,
                firmware=rec.get("ver") or None,
                online=bool(rec.get("online")),
                bind_domain=str(rec.get("bindDomain") or ""),
            )
        )
    return devices


def parse_props(payload: dict[str, Any]) -> dict[str, PropValue]:
    """Parse an iotstatus/props response."""
    props: dict[str, PropValue] = {}
    for entry in payload.get("data") or []:
        if not isinstance(entry, dict) or "key" not in entry:
            continue
        value = entry.get("value")
        stamp = entry.get("updateDate")
        updated_at = None
        if isinstance(stamp, int | float):
            updated_at = datetime.fromtimestamp(stamp / 1000, UTC)
        props[str(entry["key"])] = PropValue(
            None if value is None else str(value), updated_at
        )
    return props


def _int(props: dict[str, PropValue], prop: tuple[int, int]) -> int | None:
    entry = props.get(key(prop))
    if entry is None or entry.value is None:
        return None
    try:
        return int(entry.value)
    except ValueError:
        _LOGGER.debug("Invalid value for property %s", key(prop))
        return None


def _bool(props: dict[str, PropValue], prop: tuple[int, int]) -> bool | None:
    value = _int(props, prop)
    return None if value is None else value != 0


def build_state(device: MovaDevice, props: dict[str, PropValue]) -> FeederState:
    """Build a feeder snapshot; an invalid value only blanks its own field."""
    schedule = None
    entry = props.get(key(PROP_SCHEDULE))
    if entry is not None and entry.value is not None:
        try:
            schedule = decode_schedule(entry.value)
        except ValueError:
            _LOGGER.debug("Undecodable schedule (length %d)", len(entry.value))
    return FeederState(
        device=device,
        food_level_g=_int(props, PROP_FOOD_LEVEL),
        schedule_enabled=_bool(props, PROP_SCHEDULE_ON),
        sound_enabled=_bool(props, PROP_SOUND_ON),
        portion_size=_int(props, PROP_PORTION_SIZE),
        schedule=schedule,
        raw=props,
    )


def decode_schedule(hex_str: str) -> tuple[ScheduleSlot, ...]:
    """Decode property 3.6: 5 bytes per slot (days, hour, minute, portions, enabled)."""
    s = hex_str.strip()
    if len(s) % _SLOT_LEN:
        raise ValueError("schedule length is not a multiple of 10")
    raw = bytes.fromhex(s)
    slots = []
    for i in range(0, len(raw), 5):
        days, hour, minute, portions, enabled = raw[i : i + 5]
        if hour > 23 or minute > 59:
            raise ValueError("invalid schedule time")
        slots.append(ScheduleSlot(hour, minute, portions, enabled != 0, days))
    return tuple(slots)


def encode_schedule(slots: tuple[ScheduleSlot, ...] | list[ScheduleSlot]) -> str:
    """Encode slots to property 3.6 (upper-case hex)."""
    return "".join(
        f"{s.days_raw:02X}{s.hour:02X}{s.minute:02X}{s.portions:02X}{int(s.enabled):02X}"
        for s in slots
    )


def upsert_slot(
    slots: tuple[ScheduleSlot, ...], slot: ScheduleSlot
) -> tuple[ScheduleSlot, ...]:
    """Replace the slot at the same time (keeping its days byte) or append it."""
    for i, old in enumerate(slots):
        if (old.hour, old.minute) == (slot.hour, slot.minute):
            new = replace(slot, days_raw=old.days_raw)
            return slots[:i] + (new,) + slots[i + 1 :]
    return (*slots, slot)


def remove_slot(
    slots: tuple[ScheduleSlot, ...], hour: int, minute: int
) -> tuple[ScheduleSlot, ...]:
    """Remove the slot at hour:minute; raise ValueError if there is none."""
    kept = tuple(s for s in slots if (s.hour, s.minute) != (hour, minute))
    if len(kept) == len(slots):
        raise ValueError("no slot at this time")
    return kept


def next_feed(
    slots: tuple[ScheduleSlot, ...] | None,
    now: datetime,
) -> datetime | None:
    """Return the next scheduled feeding, or None if unknown.

    Slots are assumed to run every day (days byte 0xFF, the only value seen);
    any other days byte gives None since it is not decoded yet.
    Property 3.2 (schedule_enabled) is ignored: its meaning is unconfirmed
    (0 on the real device while slots are active).
    """
    if not slots:
        return None
    if any(s.days_raw != DAYS_ALL for s in slots):
        return None
    candidates = []
    for s in slots:
        if not s.enabled:
            continue
        when = now.replace(hour=s.hour, minute=s.minute, second=0, microsecond=0)
        if when <= now:
            when += timedelta(days=1)
        candidates.append(when)
    return min(candidates, default=None)


def build_feed_params(did: str, portions: int) -> dict[str, Any]:
    """Build the params of the manual feed action."""
    return {
        "did": did,
        "siid": ACTION_FEED_SIID,
        "aiid": ACTION_FEED_AIID,
        "in": [{"piid": ACTION_FEED_PIID, "value": portions}],
    }


def build_set_props(
    did: str, values: list[tuple[int, int, Any]]
) -> list[dict[str, Any]]:
    """Build the params of set_properties."""
    return [
        {"did": did, "siid": siid, "piid": piid, "value": value}
        for siid, piid, value in values
    ]


def check_command_result(data: Any) -> None:
    """Raise MovaCommandError unless every result of a sendCommand has code 0."""
    result = data.get("result") if isinstance(data, dict) else None
    items = result if isinstance(result, list) else [result]
    if not items or any(not isinstance(i, dict) or i.get("code") != 0 for i in items):
        codes = [i.get("code") if isinstance(i, dict) else None for i in items]
        raise MovaCommandError(f"command rejected, codes={codes}")


def safe_detail(payload: Any) -> str:
    """Return a log-safe summary of a response: code and start of msg only."""
    if not isinstance(payload, dict):
        return f"unexpected {type(payload).__name__}"
    return f"code={payload.get('code')} msg={str(payload.get('msg'))[:100]}"
