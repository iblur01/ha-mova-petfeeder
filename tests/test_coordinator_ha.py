"""Home Assistant level tests (FakeClient). Skipped when HA is not installed."""

from __future__ import annotations

import inspect
import json
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace

from fakes import ROOT, FakeClient, fixture

try:
    import homeassistant  # noqa: F401
except ImportError:  # pragma: no cover - plain Python test environment
    HA_AVAILABLE = False
else:
    HA_AVAILABLE = True
    sys.path.insert(0, str(ROOT))
    from homeassistant.config_entries import ConfigEntry, ConfigEntryState
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import (
        ConfigEntryAuthFailed,
        ConfigEntryNotReady,
        HomeAssistantError,
        ServiceValidationError,
    )
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from custom_components.mova_petfeeder import (
        async_migrate_entry,
        remove_obsolete_entities,
    )
    from custom_components.mova_petfeeder.const import (
        CONF_ENABLE_SCHEDULE_WRITE,
        CONF_PASSWORD_HASH,
        DOMAIN,
    )
    from custom_components.mova_petfeeder.coordinator import MovaCoordinator
    from custom_components.mova_petfeeder.diagnostics import (
        async_get_config_entry_diagnostics,
    )
    from custom_components.mova_petfeeder.models import (
        MovaAuthError,
        MovaConnectionError,
        ScheduleSlot,
        hash_password,
        parse_devices,
        parse_props,
    )

ONLINE_DID = "-1000000001"
OFFLINE_DID = "-1000000002"


def _entry(state=None, version: int = 2, data=None, options=None) -> ConfigEntry:
    kwargs = {
        "domain": DOMAIN,
        "data": data or {"username": "user@example.com", CONF_PASSWORD_HASH: "h", "country": "eu"},
        "options": options or {},
        "source": "user",
        "title": "Mova (user@example.com)",
        "unique_id": None if version == 1 else "user@example.com",
        "version": version,
        "minor_version": 1,
        "discovery_keys": {},
        "subentries_data": None,
        "state": state,
    }
    if state is None:
        del kwargs["state"]
    # Keep only the arguments this HA version accepts.
    params = inspect.signature(ConfigEntry).parameters
    return ConfigEntry(**{k: v for k, v in kwargs.items() if k in params})


@unittest.skipUnless(HA_AVAILABLE, "Home Assistant is not installed")
class CoordinatorHATest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.config_dir = tempfile.mkdtemp(prefix="mova-test-")
        self.hass = HomeAssistant(self.config_dir)
        self.client = FakeClient(
            parse_devices(fixture("listv2.json")), parse_props(fixture("props.json"))
        )

    async def asyncTearDown(self) -> None:
        await self.hass.async_stop(force=True)
        shutil.rmtree(self.config_dir, ignore_errors=True)

    def _coordinator(self, options=None, state=None) -> MovaCoordinator:
        entry = _entry(state or ConfigEntryState.LOADED, options=options)
        self.coordinator = MovaCoordinator(self.hass, entry, self.client)
        self.addAsyncCleanup(self.coordinator.async_shutdown)
        return self.coordinator

    async def test_first_refresh_auth_error_triggers_reauth(self) -> None:
        coordinator = self._coordinator(state=ConfigEntryState.SETUP_IN_PROGRESS)
        self.client.error = MovaAuthError("refused")
        with self.assertRaises(ConfigEntryAuthFailed):
            await coordinator.async_config_entry_first_refresh()

    async def test_first_refresh_connection_error_not_ready(self) -> None:
        coordinator = self._coordinator(state=ConfigEntryState.SETUP_IN_PROGRESS)
        self.client.error = MovaConnectionError("timeout")
        with self.assertRaises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()

    async def test_three_failures_tolerance(self) -> None:
        coordinator = self._coordinator()
        await coordinator.async_refresh()
        data = coordinator.data
        self.client.error = MovaConnectionError("timeout")
        for _ in range(2):
            await coordinator.async_refresh()
            self.assertTrue(coordinator.last_update_success)
            self.assertIs(coordinator.data, data)
        await coordinator.async_refresh()
        self.assertFalse(coordinator.last_update_success)
        self.client.error = None
        await coordinator.async_refresh()
        self.assertTrue(coordinator.last_update_success)
        self.assertEqual(coordinator.failures, 0)

    async def test_feed(self) -> None:
        coordinator = self._coordinator()
        await coordinator.async_refresh()
        with self.assertRaises(HomeAssistantError):
            await coordinator.async_feed(OFFLINE_DID, 1)
        with self.assertRaises(ServiceValidationError):
            await coordinator.async_feed(ONLINE_DID, 0)
        async with coordinator._locks[ONLINE_DID]:
            with self.assertRaises(HomeAssistantError):
                await coordinator.async_feed(ONLINE_DID, 1)
        self.assertEqual(self.client.commands, [])

        await coordinator.async_feed(ONLINE_DID, 2)
        self.assertEqual(self.client.commands[0][0], "action")
        self.assertEqual(self.client.commands[0][1]["in"], [{"piid": 1, "value": 2}])
        self.assertIsNotNone(coordinator._unsub_refresh)

    async def test_failed_command_schedules_no_refresh(self) -> None:
        coordinator = self._coordinator()
        await coordinator.async_refresh()
        self.client.command_error = MovaConnectionError("timeout")
        with self.assertRaises(HomeAssistantError):
            await coordinator.async_feed(ONLINE_DID, 1)
        self.assertIsNone(coordinator._unsub_refresh)

    async def test_schedule_write_refused_without_option(self) -> None:
        coordinator = self._coordinator()
        await coordinator.async_refresh()
        with self.assertRaises(ServiceValidationError):
            await coordinator.async_update_schedule(ONLINE_DID, lambda old: old)
        self.assertEqual(self.client.commands, [])

    async def test_schedule_write_with_option(self) -> None:
        coordinator = self._coordinator(options={CONF_ENABLE_SCHEDULE_WRITE: True})
        await coordinator.async_refresh()
        await coordinator.async_update_schedule(
            ONLINE_DID, lambda old: (*old, ScheduleSlot(20, 0, 2, True))
        )
        params = self.client.commands[0][1]
        self.assertEqual(params[0]["value"], "FF08000301FF0C000301FF12000501FF14000201")
        self.assertEqual(len(coordinator.data[ONLINE_DID].schedule), 4)

    async def test_remove_obsolete_entities(self) -> None:
        for registry_module in (dr, er):  # HA >= 2026: setup avant load
            if hasattr(registry_module, "async_setup"):
                registry_module.async_setup(self.hass)
        await dr.async_load(self.hass)
        await er.async_load(self.hass)
        entry = _entry(ConfigEntryState.LOADED)
        # HA >= 2026 : le registre vérifie que l'entrée existe
        self.hass.config_entries = SimpleNamespace(
            async_get_entry=lambda entry_id: entry if entry_id == entry.entry_id else None
        )
        registry = er.async_get(self.hass)
        for suffix in ("_portion_size_sensor", "_manual_portions", "_portion_size", "_feed"):
            registry.async_get_or_create(
                "sensor", DOMAIN, f"aabbccddeeff{suffix}", config_entry=entry
            )
        remove_obsolete_entities(self.hass, entry)
        left = {e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
        self.assertEqual(left, {"aabbccddeeff_portion_size", "aabbccddeeff_feed"})

    async def test_diagnostics_redacted(self) -> None:
        coordinator = self._coordinator()
        await coordinator.async_refresh()
        coordinator.config_entry.runtime_data = coordinator
        diag = await async_get_config_entry_diagnostics(self.hass, coordinator.config_entry)
        text = json.dumps(diag, default=str)
        for secret in (ONLINE_DID, "AA:BB:CC:DD:EE:FF", "example.invalid", "user@example.com"):
            self.assertNotIn(secret, text)
        self.assertEqual(diag["entry"]["data"][CONF_PASSWORD_HASH], "**REDACTED**")
        self.assertEqual(diag["feeders"][0]["raw"]["4.1"]["value"], "92")


@unittest.skipUnless(HA_AVAILABLE, "Home Assistant is not installed")
class MigrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_v1_to_v2_hashes_password_offline(self) -> None:
        entry = _entry(
            version=1, data={"username": "User@Example.com", "password": "pw", "country": "eu"}
        )
        updates = {}
        hass = SimpleNamespace(
            config_entries=SimpleNamespace(
                async_update_entry=lambda e, **kw: updates.update(kw)
            )
        )
        self.assertTrue(await async_migrate_entry(hass, entry))
        self.assertEqual(updates["version"], 2)
        self.assertEqual(updates["unique_id"], "user@example.com")
        self.assertNotIn("password", updates["data"])
        self.assertEqual(updates["data"][CONF_PASSWORD_HASH], hash_password("pw"))


if __name__ == "__main__":
    unittest.main()
