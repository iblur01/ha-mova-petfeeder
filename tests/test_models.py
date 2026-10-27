"""Unit tests for the pure Mova models (stdlib only)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta, timezone

from fakes import fixture, load

models = load("models")
ScheduleSlot = models.ScheduleSlot

SAMPLE = "FF08000301FF0C000301FF12000501"


class ScheduleTest(unittest.TestCase):
    def test_decode_sample(self) -> None:
        slots = models.decode_schedule(SAMPLE)
        self.assertEqual(
            [(s.time, s.portions, s.enabled, s.days_raw) for s in slots],
            [("08:00", 3, True, 0xFF), ("12:00", 3, True, 0xFF), ("18:00", 5, True, 0xFF)],
        )

    def test_round_trip(self) -> None:
        self.assertEqual(models.encode_schedule(models.decode_schedule(SAMPLE)), SAMPLE)
        lower = SAMPLE.lower()
        self.assertEqual(models.encode_schedule(models.decode_schedule(lower)), SAMPLE)

    def test_no_ff_filter(self) -> None:
        slots = models.decode_schedule("7F08000301")
        self.assertEqual(slots[0].days_raw, 0x7F)

    def test_invalid_length(self) -> None:
        with self.assertRaises(ValueError):
            models.decode_schedule("FF0800030")
        with self.assertRaises(ValueError):
            models.decode_schedule("FF18000301")  # hour 24

    def test_empty(self) -> None:
        self.assertEqual(models.decode_schedule(""), ())

    def test_upsert_and_remove(self) -> None:
        slots = models.decode_schedule("7F08000301")
        new = models.upsert_slot(slots, ScheduleSlot(8, 0, 4, False))
        self.assertEqual(new, (ScheduleSlot(8, 0, 4, False, 0x7F),))
        new = models.upsert_slot(new, ScheduleSlot(9, 30, 2, True))
        self.assertEqual([s.time for s in new], ["08:00", "09:30"])
        self.assertEqual(models.remove_slot(new, 8, 0), (ScheduleSlot(9, 30, 2, True),))
        with self.assertRaises(ValueError):
            models.remove_slot(new, 7, 0)


class NextFeedTest(unittest.TestCase):
    slots = models.decode_schedule(SAMPLE)

    def test_same_day(self) -> None:
        now = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
        self.assertEqual(
            models.next_feed(self.slots, now), datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
        )

    def test_crosses_midnight(self) -> None:
        tz = timezone(timedelta(hours=1))
        now = datetime(2026, 12, 31, 18, 0, tzinfo=tz)  # 18:00 slot is not "next"
        self.assertEqual(
            models.next_feed(self.slots, now), datetime(2027, 1, 1, 8, 0, tzinfo=tz)
        )

    def test_unknown_days_gives_none(self) -> None:
        slots = (*self.slots, ScheduleSlot(20, 0, 1, True, 0x7F))
        now = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
        self.assertIsNone(models.next_feed(slots, now))

    def test_real_device_ignores_3_2(self) -> None:
        # Real data: 08:00 and 12:00 active, 18:00 disabled; 3.2 == 0 is ignored.
        slots = models.decode_schedule("FF08000301FF0C000301FF12000400")
        now = datetime(2026, 10, 27, 13, 0, tzinfo=UTC)
        self.assertEqual(
            models.next_feed(slots, now), datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
        )
        now = datetime(2026, 10, 27, 7, 0, tzinfo=UTC)
        self.assertEqual(
            models.next_feed(slots, now), datetime(2026, 10, 27, 8, 0, tzinfo=UTC)
        )

    def test_disabled(self) -> None:
        now = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
        self.assertIsNone(models.next_feed((), now))
        off = tuple(ScheduleSlot(s.hour, s.minute, s.portions, False) for s in self.slots)
        self.assertIsNone(models.next_feed(off, now))


class ParseTest(unittest.TestCase):
    def test_parse_devices(self) -> None:
        devices = models.parse_devices(fixture("listv2.json"))
        self.assertEqual(len(devices), 2)  # the vacuum is filtered out
        first, second = devices
        self.assertEqual(first.name, "mova.feeder.q2401")  # empty customName
        self.assertEqual(first.firmware, "1.6.10_1031")
        self.assertTrue(first.online)
        self.assertEqual(first.bind_domain.split(".")[0], "20000")
        self.assertIsNone(second.mac)  # empty MAC
        self.assertEqual(second.name, "Kitchen")
        self.assertFalse(second.online)
        self.assertEqual(models.parse_devices({"code": 0, "data": None}), [])

    def test_parse_props_nulls(self) -> None:
        props = models.parse_props(fixture("props_nulls.json"))
        self.assertIsNone(props["3.2"].value)
        self.assertIsNone(props["5.1"].value)
        self.assertIsNone(props["4.1"].updated_at)
        self.assertEqual(
            props["3.4"].updated_at, datetime.fromtimestamp(1761562800, UTC)
        )

    def test_build_state(self) -> None:
        device = models.parse_devices(fixture("listv2.json"))[0]
        state = models.build_state(device, models.parse_props(fixture("props.json")))
        self.assertEqual(state.food_level_g, 92)
        self.assertFalse(state.schedule_enabled)
        self.assertFalse(state.sound_enabled)
        self.assertEqual(state.portion_size, 5)
        self.assertEqual(len(state.schedule), 3)
        self.assertEqual(state.raw["4.3"].value, "9")

    def test_build_state_invalid_values(self) -> None:
        device = models.parse_devices(fixture("listv2.json"))[0]
        state = models.build_state(device, models.parse_props(fixture("props_nulls.json")))
        self.assertIsNone(state.sound_enabled)  # "abc"
        self.assertIsNone(state.schedule_enabled)  # null
        self.assertIsNone(state.schedule)  # bad length
        self.assertIsNone(state.food_level_g)
        self.assertEqual(state.portion_size, 5)  # other fields unaffected

    def test_parse_token(self) -> None:
        tokens = models.parse_token(fixture("login.json"), now=1000.0)
        self.assertEqual(tokens.expires_at, 1000.0 + 7200 - 300)
        self.assertEqual(tokens.refresh_token, "fake-refresh-token-1")
        with self.assertRaises(models.MovaAuthError):
            models.parse_token({"error": "invalid_grant"})


class CommandTest(unittest.TestCase):
    def test_check_command_result(self) -> None:
        models.check_command_result({"result": [{"code": 0}, {"code": 0}]})
        models.check_command_result({"result": {"code": 0}})
        for bad in (
            {"result": [{"code": 0}, {"code": -1}]},
            {"result": {"code": 1}},
            {"result": []},
            {},
            None,
        ):
            with self.assertRaises(models.MovaCommandError, msg=bad):
                models.check_command_result(bad)

    def test_builders(self) -> None:
        self.assertEqual(
            models.build_feed_params("d", 2),
            {"did": "d", "siid": 3, "aiid": 1, "in": [{"piid": 1, "value": 2}]},
        )
        self.assertEqual(
            models.build_set_props("d", [(3, 4, 6)]),
            [{"did": "d", "siid": 3, "piid": 4, "value": 6}],
        )

    def test_safe_detail_has_no_token(self) -> None:
        payload = {**fixture("login.json"), "code": 401, "msg": "x" * 300}
        detail = models.safe_detail(payload)
        self.assertNotIn("fake-access-token", detail)
        self.assertNotIn("fake-refresh-token", detail)
        self.assertLessEqual(len(detail), 120)
        self.assertEqual(models.safe_detail(fixture("api_error.json")), "code=80001 msg=device offline")

    def test_hash_password(self) -> None:
        self.assertRegex(models.hash_password("secret"), r"^[0-9a-f]{32}$")


if __name__ == "__main__":
    unittest.main()
