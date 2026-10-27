"""Regression: the device list must be POSTed with a JSON body (local server only).

The Mova cloud answers HTTP 400, code 10003 ("unsupported media type") to a
POST without Content-Type. The server below mimics that on 127.0.0.1.
"""

from __future__ import annotations

import socket
import unittest

from fakes import AIOHTTP_STUB, fixture, load

api = load("api")

LIST = "/dreame-user-iot/iotuserbind/device/listV2"


@unittest.skipIf(AIOHTTP_STUB, "needs the real aiohttp")
class ListContentTypeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from aiohttp import ClientSession, TCPConnector, ThreadedResolver, web

        # The Home Assistant pytest plugin blocks socket creation (connections
        # stay limited to 127.0.0.1); allow it for this test only.
        self._socket = socket.socket
        try:
            import pytest_socket
        except ImportError:
            pass
        else:
            pytest_socket.enable_socket()

        async def token(request: web.Request) -> web.Response:
            return web.json_response(fixture("login.json"))

        async def devices(request: web.Request) -> web.Response:
            self.content_types.append(request.content_type)
            if request.content_type != "application/json":
                return web.json_response(
                    {"code": 10003, "success": False, "msg": "unsupported media type"},
                    status=400,
                )
            return web.json_response(fixture("listv2.json"))

        self.content_types: list[str] = []
        app = web.Application()
        app.router.add_post("/dreame-auth/oauth/token", token)
        app.router.add_post(LIST, devices)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        await web.TCPSite(self.runner, "127.0.0.1", 0).start()
        port = self.runner.addresses[0][1]
        # ThreadedResolver: with an IP host nothing is resolved, whereas the
        # aiodns resolver leaves a pycares shutdown thread behind.
        self.session = ClientSession(connector=TCPConnector(resolver=ThreadedResolver()))
        self.client = api.MovaClient(self.session, "user@example.com", "0" * 32, "eu")
        self.client._base = f"http://127.0.0.1:{port}"

    async def asyncTearDown(self) -> None:
        await self.session.close()
        await self.runner.cleanup()
        socket.socket = self._socket

    async def test_list_devices_sends_json_content_type(self) -> None:
        devices = await self.client.list_devices()
        self.assertEqual(len(devices), 2)
        self.assertEqual(self.content_types, ["application/json"])


if __name__ == "__main__":
    unittest.main()
