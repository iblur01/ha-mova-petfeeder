"""Test doubles: no test may reach the network.

`load()` imports modules of the integration without running its
`__init__.py` (which needs Home Assistant). If aiohttp is not installed, a
minimal stand-in is registered: the client only uses `ClientError` and
`ClientTimeout`, and the session is always a FakeSession.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "custom_components" / "mova_petfeeder"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
_PKG = "mova_petfeeder_under_test"

try:
    import aiohttp  # noqa: F401

    AIOHTTP_STUB = False
except ImportError:  # pragma: no cover - depends on the environment
    AIOHTTP_STUB = True
    _stub = types.ModuleType("aiohttp")

    class ClientError(Exception):
        """Stand-in for aiohttp.ClientError."""

    class ClientTimeout:
        def __init__(self, total: float | None = None) -> None:
            self.total = total

    _stub.ClientError = ClientError
    _stub.ClientTimeout = ClientTimeout
    sys.modules["aiohttp"] = _stub


def load(name: str) -> types.ModuleType:
    """Import `name` from the integration package, skipping its __init__.py."""
    if _PKG not in sys.modules:
        pkg = types.ModuleType(_PKG)
        pkg.__path__ = [str(PKG_DIR)]
        sys.modules[_PKG] = pkg
    return importlib.import_module(f"{_PKG}.{name}")


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status: int = 200, payload: Any = None, text: str | None = None) -> None:
        self.status = status
        self._payload = payload
        self._text = text

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def json(self, content_type: str | None = None) -> Any:
        if self._text is not None:
            return json.loads(self._text)  # raises ValueError if invalid
        return self._payload


class FakeSession:
    """Answers POSTs from per-path queues; any other URL fails the test.

    A queue item is a FakeResponse, a JSON payload (status 200) or an exception
    instance to raise.
    """

    def __init__(self, routes: dict[str, list[Any]]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> _PendingPost:
        return _PendingPost(self, url, kwargs)

    def count(self, fragment: str) -> int:
        return sum(fragment in url for url, _ in self.calls)

    async def _answer(self, url: str, kwargs: dict[str, Any]) -> FakeResponse:
        path = next((p for p in self.routes if url.endswith(p)), None)
        if path is None:
            raise AssertionError(f"unexpected URL in test: {url}")
        if not self.routes[path]:
            raise AssertionError(f"no response left for {path}")
        self.calls.append((url, kwargs))
        await asyncio.sleep(0)  # let concurrent calls interleave
        item = self.routes[path].pop(0)
        if isinstance(item, BaseException):
            raise item
        return item if isinstance(item, FakeResponse) else FakeResponse(200, item)


class _PendingPost:
    def __init__(self, session: FakeSession, url: str, kwargs: dict[str, Any]) -> None:
        self._session, self._url, self._kwargs = session, url, kwargs
        self._resp: FakeResponse | None = None

    async def __aenter__(self) -> FakeResponse:
        self._resp = await self._session._answer(self._url, self._kwargs)
        return self._resp

    async def __aexit__(self, *exc: object) -> None:
        return None


class FakeClient:
    """Same public methods as MovaClient; records commands, never sends them."""

    def __init__(self, devices: list[Any], props: dict[str, Any]) -> None:
        self.devices = devices
        self.props = props
        self.error: Exception | None = None
        self.command_error: Exception | None = None
        self.commands: list[tuple[str, Any]] = []
        self.token_expires_in = 3600

    async def login(self) -> None:
        if self.error:
            raise self.error

    async def list_devices(self) -> list[Any]:
        if self.error:
            raise self.error
        return self.devices

    async def get_props(self, did: str, keys: tuple[str, ...]) -> dict[str, Any]:
        return self.props

    async def set_properties(self, device: Any, params: list[dict[str, Any]]) -> None:
        self.commands.append(("set_properties", params))
        if self.command_error:
            raise self.command_error

    async def action(self, device: Any, params: dict[str, Any]) -> None:
        self.commands.append(("action", params))
        if self.command_error:
            raise self.command_error
