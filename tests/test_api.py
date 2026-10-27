"""Tests for MovaClient with a FakeSession (no network, no sendCommand)."""

from __future__ import annotations

import asyncio
import logging
import time
import unittest

from fakes import FakeResponse, FakeSession, fixture, load

api = load("api")
models = load("models")

TOKEN = "/dreame-auth/oauth/token"
LIST = "/iotuserbind/device/listV2"
PROPS = "/iotstatus/props"
PASSWORD_HASH = "0123456789abcdef0123456789abcdef"


def login(n: int) -> dict:
    return {**fixture("login.json"), "access_token": f"fake-access-token-{n}"}


def make(routes: dict) -> tuple[api.MovaClient, FakeSession]:
    session = FakeSession(routes)
    return api.MovaClient(session, "user+tag@example.com", PASSWORD_HASH, "eu"), session


class ClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_login_form_and_base_url(self) -> None:
        client, session = make({TOKEN: [login(1)], LIST: [fixture("listv2.json")]})
        devices = await client.list_devices()
        self.assertEqual(len(devices), 2)
        url, kwargs = session.calls[0]
        self.assertTrue(url.startswith("https://eu.iot.mova-tech.com:13267/"))
        # A dict: aiohttp url-encodes it, so "+" survives.
        self.assertIsInstance(kwargs["data"], dict)
        self.assertEqual(kwargs["data"]["username"], "user+tag@example.com")
        self.assertEqual(kwargs["data"]["grant_type"], "password")
        self.assertEqual(kwargs["timeout"].total, 15)
        self.assertEqual(session.calls[1][1]["headers"]["Dreame-Auth"], "fake-access-token-1")

    async def test_login_refused(self) -> None:
        for answer in (FakeResponse(401), FakeResponse(400), {"error": "bad"}):
            client, _ = make({TOKEN: [answer]})
            with self.assertRaises(api.MovaAuthError):
                await client.login()

    async def test_401_relogin_once_then_retry(self) -> None:
        client, session = make(
            {TOKEN: [login(1), login(2)], LIST: [FakeResponse(401), fixture("listv2.json")]}
        )
        await client.list_devices()
        self.assertEqual(session.count(TOKEN), 2)
        self.assertEqual(session.calls[-1][1]["headers"]["Dreame-Auth"], "fake-access-token-2")

    async def test_second_401_is_auth_error(self) -> None:
        client, session = make(
            {TOKEN: [login(1), login(2)], LIST: [FakeResponse(401), FakeResponse(401)]}
        )
        with self.assertRaises(api.MovaAuthError):
            await client.list_devices()
        self.assertEqual(session.count(TOKEN), 2)

    async def test_api_code_is_not_a_relogin(self) -> None:
        client, session = make({TOKEN: [login(1)], PROPS: [fixture("api_error.json")]})
        with self.assertRaises(api.MovaApiError) as ctx:
            await client.get_props("did", ("4.1",))
        self.assertEqual(ctx.exception.code, 80001)
        self.assertEqual(session.count(TOKEN), 1)
        self.assertEqual(session.calls[1][1]["json"], {"did": "did", "keys": "4.1"})

    async def test_expired_token_is_refreshed(self) -> None:
        client, session = make({TOKEN: [login(1), login(2)], LIST: [fixture("listv2.json")] * 2})
        await client.list_devices()
        client._tokens = models.TokenSet("fake-access-token-1", "fake-refresh-token-1", time.monotonic() - 1, None)
        await client.list_devices()
        refresh = session.calls[2][1]["data"]
        self.assertEqual(refresh["grant_type"], "refresh_token")
        self.assertEqual(refresh["refresh_token"], "fake-refresh-token-1")
        self.assertEqual(session.calls[3][1]["headers"]["Dreame-Auth"], "fake-access-token-2")

    async def test_failed_refresh_falls_back_to_login(self) -> None:
        client, session = make(
            {TOKEN: [FakeResponse(400), login(3)], LIST: [fixture("listv2.json")]}
        )
        client._tokens = models.TokenSet("old", "fake-refresh-token-1", time.monotonic() - 1, None)
        await client.list_devices()
        grants = [kw["data"]["grant_type"] for url, kw in session.calls if url.endswith(TOKEN)]
        self.assertEqual(grants, ["refresh_token", "password"])

    async def test_connection_errors(self) -> None:
        cases = (
            TimeoutError(),
            FakeResponse(200, text="<html>not json"),
            FakeResponse(502),
            api.aiohttp.ClientError("boom"),
        )
        for answer in cases:
            client, _ = make({TOKEN: [answer]})
            with self.assertRaises(api.MovaConnectionError, msg=repr(answer)):
                await client.list_devices()

    async def test_logs_have_no_secret(self) -> None:
        client, _ = make(
            {
                TOKEN: [login(1), login(2)],
                LIST: [FakeResponse(401), fixture("listv2.json")],
                PROPS: [fixture("api_error.json")],
            }
        )
        with self.assertLogs("mova_petfeeder_under_test", level=logging.DEBUG) as logs:
            await client.list_devices()
            with self.assertRaises(api.MovaApiError):
                await client.get_props("did", ("4.1",))
            logging.getLogger("mova_petfeeder_under_test.api").debug("end")
        text = "\n".join(logs.output)
        for secret in ("fake-access-token", "fake-refresh-token", PASSWORD_HASH, "user+tag"):
            self.assertNotIn(secret, text)

    async def test_concurrent_calls_login_once(self) -> None:
        client, session = make({TOKEN: [login(1)], LIST: [fixture("listv2.json")] * 2})
        await asyncio.gather(client.list_devices(), client.list_devices())
        self.assertEqual(session.count(TOKEN), 1)

    async def test_send_command_url_is_never_hit_by_reads(self) -> None:
        client, session = make({TOKEN: [login(1)], LIST: [fixture("listv2.json")]})
        await client.list_devices()
        self.assertEqual(session.count("sendCommand"), 0)


if __name__ == "__main__":
    unittest.main()
