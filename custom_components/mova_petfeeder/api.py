"""Async client for the MOVAhome cloud (Dreame-compatible API)."""

from __future__ import annotations

import asyncio
import itertools
import logging
import random
import time
from typing import Any

import aiohttp

from .const import (
    APP_AUTH,
    FROM_FIELD,
    REQUEST_TIMEOUT,
    RLC,
    TENANT_ID,
    USER_AGENT,
)
from .models import (
    MovaApiError,
    MovaAuthError,
    MovaCommandError,
    MovaConnectionError,
    MovaDevice,
    MovaError,
    PropValue,
    TokenSet,
    check_command_result,
    parse_devices,
    parse_props,
    parse_token,
    safe_detail,
)

__all__ = [
    "MovaApiError",
    "MovaAuthError",
    "MovaClient",
    "MovaCommandError",
    "MovaConnectionError",
    "MovaError",
]

_LOGGER = logging.getLogger(__name__)

_AUTH_STATUSES = (400, 401, 403)
_TOKEN_PATH = "/dreame-auth/oauth/token"
_LIST_PATH = "/dreame-user-iot/iotuserbind/device/listV2"
_PROPS_PATH = "/dreame-user-iot/iotstatus/props"


def _base_url(country: str) -> str:
    prefix = "" if country == "cn" else f"{country}."
    return f"https://{prefix}iot.mova-tech.com:13267"


class MovaClient:
    """MOVAhome cloud client. `session` is any object with an aiohttp-like post()."""

    def __init__(
        self, session: Any, username: str, password_hash: str, country: str
    ) -> None:
        self._session = session
        self._username = username
        self._password_hash = password_hash
        self._base = _base_url(country)
        self._tokens: TokenSet | None = None
        self._lock = asyncio.Lock()
        # Single-threaded event loop: no lock needed around the counter.
        self._ids = itertools.count(random.randint(1000, 90000))

    @property
    def token_expires_in(self) -> float | None:
        """Seconds before the access token is renewed, None if not logged in."""
        if self._tokens is None:
            return None
        return round(self._tokens.expires_at - time.monotonic())

    async def _raw_post(
        self, url: str, headers: dict[str, str], **kwargs: Any
    ) -> tuple[int, dict[str, Any]]:
        """POST and return (status, json). Auth statuses return an empty payload."""
        try:
            async with self._session.post(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                **kwargs,
            ) as resp:
                status = resp.status
                if status in _AUTH_STATUSES:
                    return status, {}
                if status >= 500:
                    raise MovaConnectionError(f"HTTP {status}")
                if status >= 400:
                    raise MovaApiError(status, f"HTTP {status}")
                try:
                    payload = await resp.json(content_type=None)
                except ValueError as err:
                    raise MovaConnectionError("invalid JSON") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise MovaConnectionError(type(err).__name__) from err
        if not isinstance(payload, dict):
            raise MovaConnectionError("unexpected JSON")
        return status, payload

    def _auth_headers(self) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Authorization": APP_AUTH,
            "Tenant-Id": TENANT_ID,
            "Dreame-Rlc": RLC,
        }

    def _api_headers(self, token: str) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Dreame-Auth": token,
            "Dreame-Rlc": RLC,
        }

    async def _token_request(self, form: dict[str, str]) -> None:
        status, payload = await self._raw_post(
            f"{self._base}{_TOKEN_PATH}", self._auth_headers(), data=form
        )
        if status in _AUTH_STATUSES:
            raise MovaAuthError(f"{form['grant_type']} refused (HTTP {status})")
        self._tokens = parse_token(payload)

    async def _login(self) -> None:
        # aiohttp url-encodes the form, so "+" or "&" in the email are safe.
        await self._token_request(
            {
                "platform": "IOS",
                "scope": "all",
                "grant_type": "password",
                "username": self._username,
                "password": self._password_hash,
                "type": "account",
            }
        )
        _LOGGER.debug("Mova login succeeded")

    async def _refresh(self, refresh_token: str) -> None:
        # ASSUMPTION: grant taken from the Dreame app, never tested on Mova.
        await self._token_request(
            {
                "platform": "IOS",
                "scope": "all",
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )
        _LOGGER.debug("Mova token refreshed")

    async def login(self) -> None:
        """Force a full login (config flow)."""
        async with self._lock:
            await self._login()

    async def _ensure_token(self, stale: str | None = None) -> str:
        """Return a valid access token; `stale` is a token the cloud just refused."""
        async with self._lock:
            tokens = self._tokens
            if (
                tokens is not None
                and tokens.access_token != stale
                and time.monotonic() < tokens.expires_at
            ):
                return tokens.access_token
            if tokens is not None and tokens.refresh_token and stale is None:
                try:
                    await self._refresh(tokens.refresh_token)
                except MovaError as err:
                    _LOGGER.debug(
                        "Token refresh failed (%s), full login", type(err).__name__
                    )
                else:
                    return self._tokens.access_token
            await self._login()
            return self._tokens.access_token

    async def _post(self, path: str, body: Any = None) -> dict[str, Any]:
        """Authenticated POST; one re-login on HTTP 401."""
        url = f"{self._base}{path}"
        kwargs = {} if body is None else {"json": body}
        token = await self._ensure_token()
        status, payload = await self._raw_post(url, self._api_headers(token), **kwargs)
        if status == 401:
            _LOGGER.debug("HTTP 401, logging in again")
            token = await self._ensure_token(stale=token)
            status, payload = await self._raw_post(
                url, self._api_headers(token), **kwargs
            )
            if status == 401:
                raise MovaAuthError("HTTP 401 after a new login")
        if status in _AUTH_STATUSES:
            raise MovaApiError(status, f"HTTP {status}")
        if payload.get("code") != 0:
            raise MovaApiError(payload.get("code"), safe_detail(payload))
        return payload

    async def list_devices(self) -> list[MovaDevice]:
        """Return the feeders bound to the account."""
        return parse_devices(await self._post(_LIST_PATH))

    async def get_props(self, did: str, keys: tuple[str, ...]) -> dict[str, PropValue]:
        """Read properties from the cloud cache (works while the device is offline)."""
        payload = await self._post(_PROPS_PATH, {"did": did, "keys": ",".join(keys)})
        return parse_props(payload)

    async def _send(self, device: MovaDevice, method: str, params: Any) -> None:
        prefix = device.bind_domain.split(".")[0]
        if not prefix:
            raise MovaCommandError("device has no bindDomain")
        cmd_id = next(self._ids)
        payload = await self._post(
            f"/dreame-iot-com-{prefix}/device/sendCommand",
            {
                "did": device.did,
                "id": cmd_id,
                "data": {
                    "did": device.did,
                    "id": cmd_id,
                    "method": method,
                    "params": params,
                    "from": FROM_FIELD,
                },
            },
        )
        check_command_result(payload.get("data"))

    async def set_properties(
        self, device: MovaDevice, params: list[dict[str, Any]]
    ) -> None:
        """Write properties; raise MovaCommandError if the device refuses."""
        await self._send(device, "set_properties", params)

    async def action(self, device: MovaDevice, params: dict[str, Any]) -> None:
        """Run a MiOT action; raise MovaCommandError if the device refuses."""
        await self._send(device, "action", params)
