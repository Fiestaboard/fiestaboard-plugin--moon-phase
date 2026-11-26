"""Tests for the moon_phase plugin."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from plugins.moon_phase import MoonPhasePlugin
from src.plugins.base import PluginResult

MANIFEST = json.loads("""
{
    "id": "moon_phase",
    "name": "Moon Phase",
    "version": "0.1.0",
    "settings_schema": {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "title": "Enabled",
                "default": false
            },
            "refresh_seconds": {
                "type": "integer",
                "title": "Refresh Interval (seconds)",
                "description": "How often to fetch moon phase data.",
                "default": 3600,
                "minimum": 3600
            }
        },
        "required": []
    }
}
""")

# Seven phases from 35 days before 2026-05-09 (= 2026-04-04).
# Last Quarter on May 8 at 23:00 UT simulates a UTC-offset case: the event
# falls on May 9 in the user's local timezone but USNO records it as May 8.
# New Moon on Apr 17 anchors the cosine illumination formula.
SAMPLE_RESPONSE = json.loads("""
{
    "phasedata": [
        {"phase": "New Moon",      "year": 2026, "month": 4, "day": 17, "time": "12:00"},
        {"phase": "First Quarter", "year": 2026, "month": 4, "day": 24, "time": "09:00"},
        {"phase": "Full Moon",     "year": 2026, "month": 5, "day":  1, "time": "12:00"},
        {"phase": "Last Quarter",  "year": 2026, "month": 5, "day":  8, "time": "23:00"},
        {"phase": "New Moon",      "year": 2026, "month": 5, "day": 16, "time": "06:00"},
        {"phase": "First Quarter", "year": 2026, "month": 5, "day": 23, "time": "09:00"},
        {"phase": "Full Moon",     "year": 2026, "month": 5, "day": 30, "time": "12:00"}
    ]
}
""")


@pytest.fixture
def plugin():
    return MoonPhasePlugin(MANIFEST)


@pytest.fixture
def configured_plugin():
    p = MoonPhasePlugin(MANIFEST)
    p.config = json.loads("""
{}
""")
    return p


class TestMoonPhasePlugin:

    def test_plugin_id(self, plugin):
        assert plugin.plugin_id == "moon_phase"

    def test_manifest_valid(self):
        manifest_path = Path(__file__).parent.parent / "manifest.json"
        with open(manifest_path) as f:
            m = json.load(f)
        for field in ("id", "name", "version"):
            assert field in m

    @patch("plugins.moon_phase.requests.get")
    def test_fetch_data_success(self, mock_get, configured_plugin):
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_RESPONSE
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = configured_plugin.fetch_data()

        assert result.available is True
        assert result.error is None
        assert result.data is not None
        assert "phase" in result.data, "missing variable: phase"
        assert "illumination" in result.data, "missing variable: illumination"
        assert "next_full_moon" in result.data, "missing variable: next_full_moon"

    @patch("plugins.moon_phase.requests.get")
    @patch("plugins.moon_phase.datetime")
    def test_phase_last_quarter_with_usno_utc_offset(self, mock_dt, mock_get, configured_plugin):
        """Regression: issue #727 — USNO UTC date one day behind local date must still
        report the quarter-phase name, not the between-phase name."""
        import datetime as real_datetime
        # Pin today to May 9, 2026 (the date in the bug report).
        # SAMPLE_RESPONSE has Last Quarter on May 8 at 23:00 UT, which is May 9
        # in many western timezones — the ±1-day tolerance must catch this.
        mock_dt.date.today.return_value = real_datetime.date(2026, 5, 9)
        mock_dt.date.side_effect = lambda *a, **kw: real_datetime.date(*a, **kw)
        mock_dt.timedelta = real_datetime.timedelta

        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_RESPONSE
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = configured_plugin.fetch_data()

        assert result.available is True
        assert result.data["phase"] == "Last Quarter"
        # cos formula: 22 days since New Moon Apr 17 → ~52%, close to real 51%
        assert 45 <= result.data["illumination"] <= 55
        assert result.data["next_full_moon"] == "2026-05-30"

    @patch("plugins.moon_phase.requests.get")
    def test_fetch_data_network_error(self, mock_get, configured_plugin):
        import requests as req_mod
        mock_get.side_effect = req_mod.exceptions.ConnectionError("network down")

        result = configured_plugin.fetch_data()

        assert result.available is False
        assert result.error is not None

    @patch("plugins.moon_phase.requests.get")
    def test_fetch_data_bad_json(self, mock_get, configured_plugin):
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("bad json")
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = configured_plugin.fetch_data()

        assert result.available is False



# Real USNO primary phases, 2026-09-04 .. 2026-12-30 (from
# https://aa.usno.navy.mil/api/moon/phases/year?year=2026).
_USNO_2026_PHASES = [
    (9, 4, "Last Quarter"), (9, 11, "New Moon"), (9, 18, "First Quarter"),
    (9, 26, "Full Moon"), (10, 3, "Last Quarter"), (10, 10, "New Moon"),
    (10, 18, "First Quarter"), (10, 26, "Full Moon"), (11, 1, "Last Quarter"),
    (11, 9, "New Moon"), (11, 17, "First Quarter"), (11, 24, "Full Moon"),
    (12, 1, "Last Quarter"), (12, 9, "New Moon"), (12, 17, "First Quarter"),
    (12, 24, "Full Moon"), (12, 30, "Last Quarter"),
]


def _fake_usno_get(url, params, **kwargs):
    """Answer like USNO's /phases/date: the first `nump` phases on or after `date`."""
    import datetime as real_datetime
    start = real_datetime.date.fromisoformat(params["date"])
    entries = [
        {"phase": name, "year": 2026, "month": m, "day": d, "time": "12:00"}
        for m, d, name in _USNO_2026_PHASES
        if real_datetime.date(2026, m, d) >= start
    ][: params["nump"]]
    response = Mock()
    response.json.return_value = {"phasedata": entries}
    response.raise_for_status = Mock()
    return response


def _fetch_on(plugin, day):
    import datetime as real_datetime
    with patch("plugins.moon_phase.requests.get", side_effect=_fake_usno_get), \
            patch("plugins.moon_phase.datetime") as mock_dt:
        mock_dt.date.today.return_value = day
        mock_dt.date.side_effect = lambda *a, **kw: real_datetime.date(*a, **kw)
        mock_dt.timedelta = real_datetime.timedelta
        return plugin.fetch_data()


class TestNextFullMoon:

    def test_next_full_moon_found_two_days_after_full_moon(self, configured_plugin):
        """Regression: two days after the 2026-11-24 Full Moon the API window
        ended before the next Full Moon, so next_full_moon came back blank."""
        import datetime as real_datetime
        result = _fetch_on(configured_plugin, real_datetime.date(2026, 11, 26))

        assert result.available is True
        assert result.data["next_full_moon"] == "2026-12-24"

    def test_next_full_moon_never_blank_across_a_lunar_cycle(self, configured_plugin):
        import datetime as real_datetime
        first = real_datetime.date(2026, 10, 26)
        for offset in range(30):
            day = first + real_datetime.timedelta(days=offset)
            result = _fetch_on(configured_plugin, day)
            next_full = result.data["next_full_moon"]
            assert next_full, f"next_full_moon blank on {day}"
            assert real_datetime.date.fromisoformat(next_full) > day
