"""Tests for the moon_phase plugin."""

from __future__ import annotations

import datetime
import json
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

import plugins.moon_phase as moon
from plugins.moon_phase import MoonPhasePlugin

UTC = datetime.timezone.utc

MANIFEST = json.loads("""
{
    "id": "moon_phase",
    "name": "Moon Phase",
    "version": "0.1.0",
    "settings_schema": {"type": "object", "properties": {}, "required": []}
}
""")

# Real USNO primary phases (UT), from
# https://aa.usno.navy.mil/api/moon/phases/year?year=2026
USNO_2026 = [
    ("2026-01-03 10:03", "Full Moon"), ("2026-01-10 15:48", "Last Quarter"),
    ("2026-01-18 19:52", "New Moon"),
    ("2026-09-04 07:51", "Last Quarter"), ("2026-09-11 03:27", "New Moon"),
    ("2026-09-18 20:44", "First Quarter"), ("2026-09-26 16:49", "Full Moon"),
    ("2026-10-03 13:25", "Last Quarter"), ("2026-10-10 15:50", "New Moon"),
    ("2026-10-18 16:12", "First Quarter"), ("2026-10-26 04:12", "Full Moon"),
    ("2026-11-01 20:28", "Last Quarter"), ("2026-11-09 07:02", "New Moon"),
    ("2026-11-17 11:48", "First Quarter"), ("2026-11-24 14:53", "Full Moon"),
    ("2026-12-01 06:08", "Last Quarter"), ("2026-12-09 00:52", "New Moon"),
    ("2026-12-17 05:42", "First Quarter"), ("2026-12-24 01:28", "Full Moon"),
    ("2026-12-30 18:59", "Last Quarter"),
]


def _utc(text: str) -> datetime.datetime:
    return datetime.datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


@pytest.fixture
def plugin():
    return MoonPhasePlugin(MANIFEST)


def _fetch_on(plugin, day: datetime.date, hour: int = 12):
    now = datetime.datetime(day.year, day.month, day.day, hour, tzinfo=UTC)
    with patch.object(moon, "_today", return_value=day), \
            patch.object(moon, "_utcnow", return_value=now):
        return plugin.fetch_data()


class TestPhaseEvents:

    @pytest.mark.parametrize("when,name", USNO_2026)
    def test_phase_time_matches_usno_within_two_minutes(self, when, name):
        expected = _utc(when)
        events = moon.phase_events(expected.date(), expected.date())
        assert [n for _, n in events] == [name]
        assert abs((events[0][0] - expected).total_seconds()) <= 120

    def test_year_2026_has_the_same_50_phases_usno_lists(self):
        events = moon.phase_events(datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))
        assert len(events) == 50

    def test_events_cycle_through_the_four_phases_in_order(self):
        names = [n for _, n in moon.phase_events(datetime.date(2026, 1, 1),
                                                 datetime.date(2026, 12, 31))]
        order = ["New Moon", "First Quarter", "Full Moon", "Last Quarter"]
        for prev, cur in zip(names, names[1:]):
            assert order.index(cur) == (order.index(prev) + 1) % 4


class TestIllumination:

    def test_full_moon_is_fully_lit(self):
        assert moon.illumination_percent(_utc("2026-11-24 14:53")) > 99.5

    def test_new_moon_is_dark(self):
        assert moon.illumination_percent(_utc("2026-12-09 00:52")) < 0.5

    def test_first_quarter_is_half_lit(self):
        assert 48 <= moon.illumination_percent(_utc("2026-11-17 11:48")) <= 52


class TestFetchData:

    def test_plugin_id(self, plugin):
        assert plugin.plugin_id == "moon_phase"

    def test_manifest_valid(self):
        manifest_path = Path(__file__).parent.parent / "manifest.json"
        m = json.loads(manifest_path.read_text())
        for field in ("id", "name", "version"):
            assert field in m

    def test_works_with_no_network(self, plugin):
        """Regression: USNO read timeouts made the plugin show Unavailable."""
        def refuse(*args, **kwargs):
            raise OSError("network disabled in test")

        with patch.object(socket.socket, "connect", refuse), \
                patch.object(socket, "create_connection", refuse):
            result = plugin.fetch_data()

        assert result.available is True
        assert result.error is None

    def test_returns_all_variables(self, plugin):
        result = _fetch_on(plugin, datetime.date(2026, 11, 26))
        assert set(result.data) == {"phase", "illumination", "next_full_moon"}

    def test_between_phase_name(self, plugin):
        assert _fetch_on(plugin, datetime.date(2026, 11, 26)).data["phase"] == "Waning Gibbous"

    def test_quarter_name_on_event_day(self, plugin):
        assert _fetch_on(plugin, datetime.date(2026, 11, 17)).data["phase"] == "First Quarter"

    def test_quarter_name_kept_one_day_after_ut_event(self, plugin):
        """Issue #727: a UT event date can be a day behind the user's local date."""
        assert _fetch_on(plugin, datetime.date(2026, 11, 25)).data["phase"] == "Full Moon"

    def test_illumination_is_rounded_percent_at_current_moment(self, plugin):
        result = _fetch_on(plugin, datetime.date(2026, 11, 24), hour=15)
        assert result.data["illumination"] == 100

    def test_next_full_moon_two_days_after_full_moon(self, plugin):
        result = _fetch_on(plugin, datetime.date(2026, 11, 26))
        assert result.data["next_full_moon"] == "2026-12-24"

    def test_next_full_moon_never_blank_across_a_lunar_cycle(self, plugin):
        first = datetime.date(2026, 10, 26)
        for offset in range(30):
            day = first + datetime.timedelta(days=offset)
            next_full = _fetch_on(plugin, day).data["next_full_moon"]
            assert datetime.date.fromisoformat(next_full) > day, f"bad next_full_moon on {day}"

    def test_unexpected_error_reports_unavailable(self, plugin):
        with patch.object(moon, "phase_events", side_effect=RuntimeError("boom")):
            result = plugin.fetch_data()
        assert result.available is False
        assert result.error == "boom"
