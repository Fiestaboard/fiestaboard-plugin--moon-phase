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

# Six phases starting ~30 days before 2026-05-09, bracketing that date correctly.
# Last Quarter on Apr 28 (past) + New Moon on May 10 (future) → Waning Crescent on May 9.
SAMPLE_RESPONSE = json.loads("""
{
    "phasedata": [
        {"phase": "First Quarter", "year": 2026, "month": 4, "day": 13, "time": "09:00"},
        {"phase": "Full Moon",     "year": 2026, "month": 4, "day": 20, "time": "12:00"},
        {"phase": "Last Quarter",  "year": 2026, "month": 4, "day": 28, "time": "09:00"},
        {"phase": "New Moon",      "year": 2026, "month": 5, "day": 10, "time": "06:00"},
        {"phase": "First Quarter", "year": 2026, "month": 5, "day": 17, "time": "09:00"},
        {"phase": "Full Moon",     "year": 2026, "month": 5, "day": 25, "time": "12:00"}
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
    def test_phase_waning_crescent_before_new_moon(self, mock_dt, mock_get, configured_plugin):
        """Regression: issue #727 — day before New Moon must not report 'New Moon, 0%'."""
        import datetime as real_datetime
        # Pin today to May 9, 2026 (the date in the bug report)
        mock_dt.date.today.return_value = real_datetime.date(2026, 5, 9)
        mock_dt.date.side_effect = lambda *a, **kw: real_datetime.date(*a, **kw)
        mock_dt.timedelta = real_datetime.timedelta

        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_RESPONSE
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = configured_plugin.fetch_data()

        assert result.available is True
        assert result.data["phase"] == "Waning Crescent"
        # Last Quarter (50%) → New Moon (0%) over 12 days; on day 11 → ~4%
        assert result.data["illumination"] < 15
        assert result.data["next_full_moon"] == "2026-05-25"

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

